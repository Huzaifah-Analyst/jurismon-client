"""JurisMon Crawler Orchestrator.

Sub-Task 1.4:
Coordinates concurrent crawling across all configured municipal sources,
enforcing isolated error boundaries, rate limiting, and progress metrics.
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field

from crawler.base import CrawlResult, DiscoveredDocument
from crawler.adapters import get_adapter
from crawler.session import SafeHTTPSession

logger = logging.getLogger("jurismon.orchestrator")


class OrchestratorRunSummary(BaseModel):
    """Execution metrics and health summary for a full ingestion crawl."""
    total_sources: int = 0
    succeeded_sources: int = 0
    failed_sources: int = 0
    total_documents_discovered: int = 0
    duration_seconds: float = 0.0
    results: List[CrawlResult] = []
    failed_source_details: List[Dict[str, str]] = []


class CrawlOrchestrator:
    """Manages concurrent execution across 50+ municipal websites."""

    def __init__(
        self,
        max_workers: Optional[int] = None,
        default_delay: Optional[float] = None,
    ):
        self.max_workers = (
            int(max_workers)
            if max_workers is not None
            else int(os.getenv("CRAWLER_CONCURRENCY", 3))
        )
        self.default_delay = (
            float(default_delay)
            if default_delay is not None
            else float(os.getenv("CRAWLER_DELAY_SECONDS", 1.5))
        )
        self.session = SafeHTTPSession(default_delay=self.default_delay)

    def crawl_single_source(self, source_config: Dict[str, Any]) -> CrawlResult:
        """Isolated execution for a single municipal entity."""
        adapter_type = source_config.get("adapter_type", "custom")
        adapter = get_adapter(adapter_type, session=self.session)
        return adapter.crawl(source_config)

    def run_all(self, sources: List[Dict[str, Any]]) -> OrchestratorRunSummary:
        """Executes crawl across all provided sources in a thread pool."""
        start_time = time.time()
        active_sources = [s for s in sources if s.get("is_active", True)]

        logger.info(f"Starting crawl orchestrator with {len(active_sources)} active sources (Workers: {self.max_workers})")

        results: List[CrawlResult] = []
        succeeded_count = 0
        failed_count = 0
        total_docs = 0
        failed_details: List[Dict[str, str]] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_source = {
                executor.submit(self.crawl_single_source, src): src for src in active_sources
            }

            for future in as_completed(future_to_source):
                src = future_to_source[future]
                src_name = src.get("name", "Unnamed")
                try:
                    res: CrawlResult = future.result()
                    results.append(res)

                    if res.success:
                        succeeded_count += 1
                        total_docs += len(res.documents)
                        logger.info(f"✓ [{res.source_name}] Completed - {len(res.documents)} docs found ({res.duration_seconds}s)")
                    else:
                        failed_count += 1
                        failed_details.append({
                            "source_id": res.source_id,
                            "source_name": res.source_name,
                            "error": res.error_message or "Unknown failure",
                        })
                        logger.warning(f"✗ [{res.source_name}] Failed: {res.error_message}")

                except Exception as exc:
                    failed_count += 1
                    error_str = f"Unhandled worker exception for {src_name}: {str(exc)}"
                    logger.error(error_str, exc_info=True)
                    failed_details.append({
                        "source_id": str(src.get("id", "")),
                        "source_name": src_name,
                        "error": str(exc),
                    })

        total_duration = round(time.time() - start_time, 2)
        logger.info(
            f"=== Crawl Ingestion Complete: {succeeded_count}/{len(active_sources)} succeeded, "
            f"{total_docs} docs discovered in {total_duration}s ==="
        )

        return OrchestratorRunSummary(
            total_sources=len(active_sources),
            succeeded_sources=succeeded_count,
            failed_sources=failed_count,
            total_documents_discovered=total_docs,
            duration_seconds=total_duration,
            results=results,
            failed_source_details=failed_details,
        )
