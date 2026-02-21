import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.scanners import docker_scanner, network_scanner, esxi_scanner, synology_scanner
from app.services import xwiki_writer, ollama_analyzer
from app.scheduler import start_scheduler, stop_scheduler, scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AutoDoc starting up")
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("AutoDoc shutting down")


app = FastAPI(
    title="AutoDoc",
    description="Infrastructure auto-discovery and documentation for XWiki",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── GUI ──────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def gui():
    return FileResponse(STATIC_DIR / "index.html")


# ── Health ───────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "autodoc"}


# ── Config API ───────────────────────────────────────

class ConfigUpdate(BaseModel):
    scan_subnets: str | None = None
    scan_interval_hours: int | None = None
    esxi_host: str | None = None
    synology_host: str | None = None


@app.get("/api/config")
async def get_config():
    """Return current runtime configuration."""
    return {
        "scan_subnets": settings.scan_subnets,
        "scan_interval_hours": settings.scan_interval_hours,
        "esxi_host": settings.esxi_host,
        "esxi_user": settings.esxi_user,
        "synology_host": settings.synology_host,
        "synology_user": settings.synology_user,
        "xwiki_url": settings.xwiki_url,
        "ollama_url": settings.ollama_url,
        "ollama_model": settings.ollama_model,
    }


@app.put("/api/config")
async def update_config(cfg: ConfigUpdate):
    """Update runtime configuration (non-persistent, resets on restart)."""
    changed = []
    if cfg.scan_subnets is not None:
        settings.scan_subnets = cfg.scan_subnets
        changed.append("scan_subnets")
    if cfg.scan_interval_hours is not None:
        settings.scan_interval_hours = cfg.scan_interval_hours
        # Reschedule
        stop_scheduler()
        start_scheduler()
        changed.append("scan_interval_hours")
    if cfg.esxi_host is not None:
        settings.esxi_host = cfg.esxi_host
        changed.append("esxi_host")
    if cfg.synology_host is not None:
        settings.synology_host = cfg.synology_host
        changed.append("synology_host")
    logger.info("Config updated: %s", changed)
    return {"status": "ok", "changed": changed}


# ── Scheduler API ────────────────────────────────────

@app.get("/api/scheduler")
async def scheduler_status():
    """Return scheduler status."""
    jobs = scheduler.get_jobs()
    next_run = None
    if jobs:
        next_run = str(jobs[0].next_run_time) if jobs[0].next_run_time else None
    return {
        "running": scheduler.running,
        "interval_hours": settings.scan_interval_hours,
        "next_run": next_run,
        "jobs": len(jobs),
    }


# ── Scan Endpoints ───────────────────────────────────

@app.post("/api/scan/docker")
async def scan_docker():
    """Run Docker scan and write to XWiki."""
    data = docker_scanner.scan()
    analysis = await ollama_analyzer.analyze("Docker", data)
    await xwiki_writer.write_docker_scan(data, analysis)
    return {"status": "ok", "containers": len(data.get("containers", []))}


@app.post("/api/scan/network")
async def scan_network():
    """Run network scan and write to XWiki."""
    data = network_scanner.scan()
    analysis = await ollama_analyzer.analyze("Network", data)
    await xwiki_writer.write_network_scan(data, analysis)
    return {"status": "ok", "hosts_found": data.get("hosts_found", 0)}


@app.post("/api/scan/esxi")
async def scan_esxi():
    """Run ESXi scan and write to XWiki."""
    data = esxi_scanner.scan()
    if "error" in data:
        return {"status": "error", "message": data["error"]}
    analysis = await ollama_analyzer.analyze("ESXi", data)
    await xwiki_writer.write_scan_result(
        "ESXi", "ESXi", f"ESXi - {data.get('hostname', '')}", data, analysis
    )
    return {"status": "ok", "vms": len(data.get("vms", []))}


@app.post("/api/scan/synology")
async def scan_synology():
    """Run Synology scan and write to XWiki."""
    data = synology_scanner.scan()
    if "error" in data:
        return {"status": "error", "message": data["error"]}
    analysis = await ollama_analyzer.analyze("Synology", data)
    await xwiki_writer.write_scan_result(
        "Synology", "Synology", f"Synology - {data.get('hostname', '')}", data, analysis
    )
    return {"status": "ok", "host": data.get("hostname", "")}


@app.post("/api/scan/all")
async def scan_all():
    """Run all scans."""
    results = {}
    for name, scan_fn in [
        ("docker", scan_docker),
        ("network", scan_network),
        ("esxi", scan_esxi),
        ("synology", scan_synology),
    ]:
        try:
            results[name] = await scan_fn()
        except Exception as e:
            results[name] = {"status": "error", "message": str(e)}
    return results
