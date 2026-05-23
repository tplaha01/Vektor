from __future__ import annotations

import argparse
import json
import secrets
import string
import time
from pathlib import Path

import boto3


def _password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits + "!#$%&*+-=?"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _default_vpc(ec2) -> str:
    response = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])
    vpcs = response.get("Vpcs") or []
    if not vpcs:
        raise RuntimeError("No default VPC found in this region.")
    return vpcs[0]["VpcId"]


def _subnets(ec2, vpc_id: str) -> list[str]:
    response = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}])
    subnets = [subnet["SubnetId"] for subnet in response.get("Subnets") or []]
    if len(subnets) < 2:
        raise RuntimeError("RDS needs at least two subnets in different availability zones.")
    return subnets


def _ensure_sg(ec2, *, vpc_id: str, name: str, description: str) -> str:
    existing = ec2.describe_security_groups(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "group-name", "Values": [name]},
        ]
    ).get("SecurityGroups") or []
    if existing:
        return existing[0]["GroupId"]
    return ec2.create_security_group(GroupName=name, Description=description, VpcId=vpc_id)["GroupId"]


def _authorize_ingress(ec2, *, group_id: str, permissions: list[dict]) -> None:
    try:
        ec2.authorize_security_group_ingress(GroupId=group_id, IpPermissions=permissions)
    except ec2.exceptions.ClientError as exc:
        if "InvalidPermission.Duplicate" not in str(exc):
            raise


def _ensure_subnet_group(rds, *, name: str, subnets: list[str]) -> None:
    try:
        rds.describe_db_subnet_groups(DBSubnetGroupName=name)
    except rds.exceptions.DBSubnetGroupNotFoundFault:
        rds.create_db_subnet_group(
            DBSubnetGroupName=name,
            DBSubnetGroupDescription="Vektor us-west-2 Postgres subnet group",
            SubnetIds=subnets,
        )


def _db_exists(rds, identifier: str) -> bool:
    try:
        rds.describe_db_instances(DBInstanceIdentifier=identifier)
        return True
    except rds.exceptions.DBInstanceNotFoundFault:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Vektor Postgres in AWS us-west-2.")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--db-identifier", default="vektor-postgres-us-west-2")
    parser.add_argument("--db-name", default="vektor")
    parser.add_argument("--db-user", default="vektor")
    parser.add_argument("--db-instance-class", default="db.t4g.micro")
    parser.add_argument("--allocated-storage", type=int, default=50)
    parser.add_argument("--backend-sg-name", default="vektor-backend-us-west-2")
    parser.add_argument("--db-sg-name", default="vektor-postgres-us-west-2")
    parser.add_argument("--output", default=".run/aws-us-west-2-postgres.json")
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region)
    ec2 = session.client("ec2")
    rds = session.client("rds")

    vpc_id = _default_vpc(ec2)
    subnet_ids = _subnets(ec2, vpc_id)
    backend_sg = _ensure_sg(
        ec2,
        vpc_id=vpc_id,
        name=args.backend_sg_name,
        description="Vektor backend HTTP/HTTPS/SSH",
    )
    db_sg = _ensure_sg(
        ec2,
        vpc_id=vpc_id,
        name=args.db_sg_name,
        description="Vektor Postgres access from backend security group",
    )
    _authorize_ingress(
        ec2,
        group_id=backend_sg,
        permissions=[
            {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
            {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
            {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
        ],
    )
    _authorize_ingress(
        ec2,
        group_id=db_sg,
        permissions=[
            {
                "IpProtocol": "tcp",
                "FromPort": 5432,
                "ToPort": 5432,
                "UserIdGroupPairs": [{"GroupId": backend_sg}],
            }
        ],
    )

    subnet_group = "vektor-postgres-us-west-2"
    _ensure_subnet_group(rds, name=subnet_group, subnets=subnet_ids)

    created = False
    password = _password()
    if not _db_exists(rds, args.db_identifier):
        rds.create_db_instance(
            DBInstanceIdentifier=args.db_identifier,
            AllocatedStorage=args.allocated_storage,
            DBInstanceClass=args.db_instance_class,
            Engine="postgres",
            DBName=args.db_name,
            MasterUsername=args.db_user,
            MasterUserPassword=password,
            VpcSecurityGroupIds=[db_sg],
            DBSubnetGroupName=subnet_group,
            PubliclyAccessible=False,
            MultiAZ=False,
            StorageEncrypted=True,
            BackupRetentionPeriod=7,
            DeletionProtection=True,
            AutoMinorVersionUpgrade=True,
            Tags=[{"Key": "Project", "Value": "Vektor"}, {"Key": "Role", "Value": "Postgres"}],
        )
        created = True
    else:
        password = "<existing-password-not-changed>"

    endpoint = None
    if args.wait:
        waiter = rds.get_waiter("db_instance_available")
        waiter.wait(DBInstanceIdentifier=args.db_identifier)
    while args.wait:
        instance = rds.describe_db_instances(DBInstanceIdentifier=args.db_identifier)["DBInstances"][0]
        endpoint = instance.get("Endpoint", {}).get("Address")
        if endpoint:
            break
        time.sleep(10)

    payload = {
        "region": args.region,
        "vpc_id": vpc_id,
        "subnet_ids": subnet_ids,
        "backend_security_group_id": backend_sg,
        "db_security_group_id": db_sg,
        "db_identifier": args.db_identifier,
        "db_name": args.db_name,
        "db_user": args.db_user,
        "db_password": password,
        "db_endpoint": endpoint,
        "database_url": (
            f"postgresql://{args.db_user}:{password}@{endpoint}:5432/{args.db_name}"
            if endpoint and not password.startswith("<")
            else None
        ),
        "created": created,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    if endpoint:
        print(f"postgres endpoint: {endpoint}")
    else:
        print("postgres creation started; rerun with --wait or check RDS for endpoint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
