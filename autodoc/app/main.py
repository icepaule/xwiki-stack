import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.scanners import docker_scanner, network_scanner, esxi_scanner, synology_scanner
from app.services import xwiki_writer, ollama_analyzer
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "autodoc"}


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
