import logging
from datetime import datetime, timezone

import nmap

from app.config import settings

logger = logging.getLogger(__name__)


def scan() -> dict:
    """Scan configured subnets using nmap."""
    scanner = nmap.PortScanner()
    subnets = [s.strip() for s in settings.scan_subnets.split(",")]
    all_hosts = []

    for subnet in subnets:
        logger.info("Scanning subnet: %s", subnet)
        try:
            scanner.scan(hosts=subnet, arguments="-sn -T4")
            for host in scanner.all_hosts():
                host_info = {
                    "ip": host,
                    "hostname": scanner[host].hostname() or "",
                    "state": scanner[host].state(),
                    "mac": "",
                    "vendor": "",
                }
                if "mac" in scanner[host].get("addresses", {}):
                    host_info["mac"] = scanner[host]["addresses"]["mac"]
                if scanner[host].get("vendor"):
                    mac = host_info["mac"]
                    host_info["vendor"] = scanner[host]["vendor"].get(mac, "")
                all_hosts.append(host_info)
        except Exception as e:
            logger.error("Failed to scan %s: %s", subnet, e)

    return {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "subnets": subnets,
        "hosts_found": len(all_hosts),
        "hosts": all_hosts,
    }
