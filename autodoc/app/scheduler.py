import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def _run_all_scans():
    """Run all scans and write results to XWiki."""
    from app.scanners import docker_scanner, network_scanner, esxi_scanner, synology_scanner
    from app.services import xwiki_writer, ollama_analyzer

    logger.info("Scheduled scan starting...")

    # Docker scan
    try:
        data = docker_scanner.scan()
        analysis = await ollama_analyzer.analyze("Docker", data)
        await xwiki_writer.write_docker_scan(data, analysis)
        logger.info("Docker scan complete")
    except Exception as e:
        logger.error("Docker scan failed: %s", e)

    # Network scan
    try:
        data = network_scanner.scan()
        analysis = await ollama_analyzer.analyze("Network", data)
        await xwiki_writer.write_network_scan(data, analysis)
        logger.info("Network scan complete")
    except Exception as e:
        logger.error("Network scan failed: %s", e)

    # ESXi scan
    try:
        data = esxi_scanner.scan()
        if "error" not in data:
            analysis = await ollama_analyzer.analyze("ESXi", data)
            await xwiki_writer.write_scan_result("ESXi", "ESXi", f"ESXi - {data.get('hostname', '')}", data, analysis)
            logger.info("ESXi scan complete")
    except Exception as e:
        logger.error("ESXi scan failed: %s", e)

    # Synology scan
    try:
        data = synology_scanner.scan()
        if "error" not in data:
            analysis = await ollama_analyzer.analyze("Synology", data)
            await xwiki_writer.write_scan_result("Synology", "Synology", f"Synology - {data.get('hostname', '')}", data, analysis)
            logger.info("Synology scan complete")
    except Exception as e:
        logger.error("Synology scan failed: %s", e)

    logger.info("Scheduled scan complete")


def start_scheduler():
    """Start the periodic scan scheduler."""
    interval = settings.scan_interval_hours
    scheduler.add_job(
        _run_all_scans,
        "interval",
        hours=interval,
        id="autodoc_scan",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: scans every %d hours", interval)


def stop_scheduler():
    """Stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
