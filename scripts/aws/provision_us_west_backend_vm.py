from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import boto3


def _latest_ubuntu_ami(ec2) -> str:
    images = ec2.describe_images(
        Owners=["099720109477"],
        Filters=[
            {"Name": "name", "Values": ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]},
            {"Name": "architecture", "Values": ["x86_64"]},
            {"Name": "virtualization-type", "Values": ["hvm"]},
            {"Name": "root-device-type", "Values": ["ebs"]},
        ],
    ).get("Images") or []
    if not images:
        raise RuntimeError("No Ubuntu 24.04 amd64 AMI found.")
    return sorted(images, key=lambda img: img["CreationDate"], reverse=True)[0]["ImageId"]


def _default_vpc(ec2) -> str:
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}]).get("Vpcs") or []
    if not vpcs:
        raise RuntimeError("No default VPC found.")
    return vpcs[0]["VpcId"]


def _first_public_subnet(ec2, vpc_id: str) -> str:
    subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]).get("Subnets") or []
    if not subnets:
        raise RuntimeError("No subnet found in default VPC.")
    return sorted(subnets, key=lambda item: item.get("AvailabilityZone", ""))[0]["SubnetId"]


def _ensure_key_pair(ec2, *, key_name: str, private_key_path: Path) -> None:
    try:
        ec2.describe_key_pairs(KeyNames=[key_name])
        return
    except ec2.exceptions.ClientError:
        pass
    public_key = subprocess.check_output(["ssh-keygen", "-y", "-f", str(private_key_path)], text=True).strip()
    ec2.import_key_pair(KeyName=key_name, PublicKeyMaterial=public_key.encode("utf-8"))


def _ensure_sg(ec2, *, vpc_id: str, name: str) -> str:
    groups = ec2.describe_security_groups(
        Filters=[{"Name": "vpc-id", "Values": [vpc_id]}, {"Name": "group-name", "Values": [name]}]
    ).get("SecurityGroups") or []
    if groups:
        return groups[0]["GroupId"]
    sg_id = ec2.create_security_group(
        GroupName=name,
        Description="Vektor us-west-2 backend HTTP HTTPS SSH",
        VpcId=vpc_id,
    )["GroupId"]
    try:
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
                {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
            ],
        )
    except ec2.exceptions.ClientError as exc:
        if "InvalidPermission.Duplicate" not in str(exc):
            raise
    return sg_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision a Vektor backend VM in AWS us-west-2.")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--key-name", default="vektor-us-west-2")
    parser.add_argument("--private-key-path", default=str(Path.home() / ".ssh" / "vektor-aws-us-east-1.pem"))
    parser.add_argument("--instance-type", default="t3.small")
    parser.add_argument("--security-group-name", default="vektor-backend-us-west-2")
    parser.add_argument("--output", default=".run/aws-us-west-2-backend-vm.json")
    args = parser.parse_args()

    private_key = Path(args.private_key_path).expanduser()
    if not private_key.exists():
        raise SystemExit(f"Private key not found: {private_key}")

    session = boto3.Session(region_name=args.region)
    ec2 = session.client("ec2")

    _ensure_key_pair(ec2, key_name=args.key_name, private_key_path=private_key)
    vpc_id = _default_vpc(ec2)
    subnet_id = _first_public_subnet(ec2, vpc_id)
    sg_id = _ensure_sg(ec2, vpc_id=vpc_id, name=args.security_group_name)
    image_id = _latest_ubuntu_ami(ec2)

    instance = ec2.run_instances(
        ImageId=image_id,
        InstanceType=args.instance_type,
        KeyName=args.key_name,
        MinCount=1,
        MaxCount=1,
        SubnetId=subnet_id,
        SecurityGroupIds=[sg_id],
        BlockDeviceMappings=[
            {
                "DeviceName": "/dev/sda1",
                "Ebs": {
                    "VolumeSize": 40,
                    "VolumeType": "gp3",
                    "DeleteOnTermination": True,
                    "Encrypted": True,
                },
            }
        ],
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": "vektor-backend-us-west-2"}, {"Key": "Project", "Value": "Vektor"}],
            }
        ],
    )["Instances"][0]
    instance_id = instance["InstanceId"]
    waiter = ec2.get_waiter("instance_running")
    waiter.wait(InstanceIds=[instance_id])

    allocation = ec2.allocate_address(Domain="vpc")
    ec2.associate_address(InstanceId=instance_id, AllocationId=allocation["AllocationId"])
    refreshed = ec2.describe_instances(InstanceIds=[instance_id])["Reservations"][0]["Instances"][0]
    payload = {
        "region": args.region,
        "instance_id": instance_id,
        "public_ip": allocation["PublicIp"],
        "elastic_ip_allocation_id": allocation["AllocationId"],
        "vpc_id": vpc_id,
        "subnet_id": subnet_id,
        "security_group_id": sg_id,
        "key_name": args.key_name,
        "ssh_user": "ubuntu",
        "private_key_path": str(private_key),
        "public_dns_name": refreshed.get("PublicDnsName"),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    print(f"ssh ubuntu@{allocation['PublicIp']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
