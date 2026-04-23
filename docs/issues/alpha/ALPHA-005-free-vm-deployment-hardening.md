# ALPHA-005 Free VM Deployment Hardening

Status: open
Priority: critical
Depends on: `ALPHA-001`
Blocks: `ALPHA-006`

## Objective

Deploy the backend to a persistent free VM only after local reliability is proven, with enough supervision and recovery to run continuously in paper mode.

## Scope

- static public IP
- backend deployment
- supervised startup
- reboot recovery
- health checks
- remote logs
- backup rotation
- remote soak

## Work Items

- [ ] Provision the free VM with static public IP
- [ ] Install runtime dependencies and environment secrets correctly
- [ ] Add supervised service startup
- [ ] Add reboot recovery
- [ ] Add health check and restart policy
- [ ] Add backup rotation for DB and critical artifacts
- [ ] Add remote log collection / retention
- [ ] Run remote soak after local soak signoff

## Acceptance Criteria

- Backend starts automatically on reboot
- Health endpoint remains stable remotely
- Logs and backups are recoverable
- Remote runtime behaves no worse than local runtime
- OpenClaw remains usable from the laptop as CEO interface

## Verification Commands

```powershell
curl http://<vm-ip>:8000/health
curl http://<vm-ip>:8000/api/admin/ceo/command-help
```

## Deliverables

- deployed persistent backend
- remote service supervision
- backup and log retention plan
