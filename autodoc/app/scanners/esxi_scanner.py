import logging
from datetime import datetime, timezone

import paramiko

from app.config import settings

logger = logging.getLogger(__name__)


def _ssh_connect() -> paramiko.SSHClient:
    """Connect to ESXi via SSH with RSA key."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=settings.esxi_host,
        username=settings.esxi_user,
        key_filename=settings.esxi_ssh_key_path,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


def _run_cmd(client: paramiko.SSHClient, cmd: str) -> str:
    """Execute command and return stdout."""
    _, stdout, stderr = client.exec_command(cmd)
    output = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err:
        logger.warning("ESXi cmd '%s' stderr: %s", cmd, err.strip())
    return output.strip()


def scan() -> dict:
    """Scan ESXi host for VMs, datastores, and system info."""
    if not settings.esxi_host:
        return {"error": "ESXI_HOST not configured"}

    client = _ssh_connect()
    try:
        # System info
        hostname = _run_cmd(client, "hostname")
        version = _run_cmd(client, "vmware -v")

        # VMs
        vm_list_raw = _run_cmd(client, "vim-cmd vmsvc/getallvms")
        vms = _parse_vm_list(vm_list_raw)

        # Datastores
        ds_raw = _run_cmd(client, "esxcli storage filesystem list")
        datastores = _parse_datastores(ds_raw)

        # Network
        vswitch_raw = _run_cmd(client, "esxcli network vswitch standard list")
        nics_raw = _run_cmd(client, "esxcli network nic list")

        return {
            "scan_time": datetime.now(timezone.utc).isoformat(),
            "host": settings.esxi_host,
            "hostname": hostname,
            "version": version,
            "vms": vms,
            "datastores": datastores,
            "vswitches_raw": vswitch_raw,
            "nics_raw": nics_raw,
        }
    finally:
        client.close()


def _parse_vm_list(raw: str) -> list[dict]:
    """Parse vim-cmd vmsvc/getallvms output."""
    vms = []
    lines = raw.split("\n")
    for line in lines[1:]:  # skip header
        parts = line.split()
        if len(parts) >= 4:
            vmid = parts[0]
            name = parts[1]
            # File path is in brackets
            vms.append({"id": vmid, "name": name, "raw": line.strip()})
    return vms


def _parse_datastores(raw: str) -> list[dict]:
    """Parse esxcli storage filesystem list output."""
    datastores = []
    lines = raw.split("\n")
    header_found = False
    for line in lines:
        if "Mount Point" in line:
            header_found = True
            continue
        if line.startswith("---"):
            continue
        if header_found and line.strip():
            parts = line.split()
            if len(parts) >= 4:
                datastores.append({
                    "mount_point": parts[0],
                    "name": parts[-1] if not parts[-1].startswith("/") else "",
                    "raw": line.strip(),
                })
    return datastores
