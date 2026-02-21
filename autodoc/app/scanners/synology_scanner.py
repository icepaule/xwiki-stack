import logging
from datetime import datetime, timezone

import paramiko

from app.config import settings

logger = logging.getLogger(__name__)


def _ssh_connect() -> paramiko.SSHClient:
    """Connect to Synology via SSH with ed25519 key."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.Ed25519Key.from_private_key_file(settings.synology_ssh_key_path)
    client.connect(
        hostname=settings.synology_host,
        username=settings.synology_user,
        pkey=key,
        look_for_keys=False,
        allow_agent=False,
    )
    return client


def _run_cmd(client: paramiko.SSHClient, cmd: str) -> str:
    """Execute command and return stdout."""
    _, stdout, stderr = client.exec_command(cmd)
    output = stdout.read().decode("utf-8", errors="replace")
    return output.strip()


def scan() -> dict:
    """Scan Synology NAS for volumes, shares, and packages."""
    if not settings.synology_host:
        return {"error": "SYNOLOGY_HOST not configured"}

    client = _ssh_connect()
    try:
        hostname = _run_cmd(client, "hostname")
        dsm_version = _run_cmd(client, "cat /etc.defaults/VERSION 2>/dev/null | head -5")

        # Disk usage
        df_output = _run_cmd(client, "df -h")

        # Shared folders
        shares_raw = _run_cmd(client, "synoshare --enum ALL 2>/dev/null || ls /volume1 /volume2 2>/dev/null")

        # Installed packages
        packages_raw = _run_cmd(client, "synopkg list 2>/dev/null")
        packages_status = _run_cmd(client, "synopkg status_all 2>/dev/null || true")

        # Network
        network_raw = _run_cmd(client, "ip addr show 2>/dev/null || ifconfig")

        return {
            "scan_time": datetime.now(timezone.utc).isoformat(),
            "host": settings.synology_host,
            "hostname": hostname,
            "dsm_version": dsm_version,
            "disk_usage": df_output,
            "shares": shares_raw,
            "packages": packages_raw,
            "packages_status": packages_status,
            "network": network_raw,
        }
    finally:
        client.close()
