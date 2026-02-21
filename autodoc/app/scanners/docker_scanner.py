import logging
from datetime import datetime, timezone

import docker

logger = logging.getLogger(__name__)


def scan() -> dict:
    """Scan Docker environment via socket."""
    client = docker.DockerClient(base_url="unix:///var/run/docker.sock")

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
        "scan_time": datetime.now(timezone.utc).isoformat(),
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
