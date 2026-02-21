import logging
from datetime import datetime, timezone

import docker

from app.config import settings

logger = logging.getLogger(__name__)


def _scan_host(base_url: str) -> dict:
    """Scan a single Docker host and return structured results."""
    client = docker.DockerClient(base_url=base_url, timeout=15)

    containers = []
    for c in client.containers.list(all=True):
        ports = {}
        if c.ports:
            for container_port, bindings in c.ports.items():
                if bindings:
                    ports[container_port] = [b.get("HostPort", "") for b in bindings]
        containers.append({
            "name": c.name,
            "image": str(c.image.tags[0]) if c.image.tags else c.image.short_id,
            "status": c.status,
            "ports": ports,
            "created": c.attrs.get("Created", ""),
            "labels": dict(c.labels) if c.labels else {},
        })

    networks = []
    for n in client.networks.list():
        networks.append({
            "name": n.name,
            "driver": n.attrs.get("Driver", ""),
            "scope": n.attrs.get("Scope", ""),
            "containers": [c.name for c in (n.containers or [])],
        })

    volumes = []
    for v in client.volumes.list():
        volumes.append({
            "name": v.name,
            "driver": v.attrs.get("Driver", ""),
            "mountpoint": v.attrs.get("Mountpoint", ""),
        })

    info = client.info()

    return {
        "base_url": base_url,
        "host": {
            "hostname": info.get("Name", ""),
            "os": info.get("OperatingSystem", ""),
            "docker_version": info.get("ServerVersion", ""),
            "cpus": info.get("NCPU", 0),
            "memory_gb": round(info.get("MemTotal", 0) / 1024**3, 1),
        },
        "containers": containers,
        "networks": networks,
        "volumes": volumes,
    }


def _get_docker_hosts() -> list[str]:
    """Build list of Docker hosts to scan from config."""
    hosts = ["unix:///var/run/docker.sock"]
    if settings.docker_hosts:
        for h in settings.docker_hosts.split(","):
            h = h.strip()
            if h:
                hosts.append(h)
    return hosts


def scan() -> dict:
    """Scan all configured Docker hosts."""
    hosts = _get_docker_hosts()
    all_results = []
    total_containers = 0

    for base_url in hosts:
        try:
            result = _scan_host(base_url)
            total_containers += len(result["containers"])
            all_results.append(result)
            logger.info("Scanned %s: %d containers", base_url, len(result["containers"]))
        except Exception as e:
            logger.error("Failed to scan %s: %s", base_url, e)
            all_results.append({
                "base_url": base_url,
                "error": str(e),
                "host": {},
                "containers": [],
                "networks": [],
                "volumes": [],
            })

    return {
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "hosts_scanned": len(all_results),
        "total_containers": total_containers,
        "hosts": all_results,
    }
