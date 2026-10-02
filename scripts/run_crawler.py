"""JurisMon Daily Crawler & Diff Orchestrator CLI.

Runs daily ingestion across all configured municipal sources, detects content
updates, extracts cleaned text, generates statutory diffs, and saves snapshots to DB.
"""

import os
import sys
import yaml
import time
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Optional, List, Dict, Any

from crawler.adapters import get_adapter
from crawler.requests_crawler import RequestsCrawler
from extractor.pdf_extractor import PDFExtractor
from extractor.html_extractor import HTMLExtractor
from diff_engine.engine import DiffEngine
from db.repository import Repository
from notifications.crawl_report import send_crawl_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("jurismon.orchestrator")


def load_sites_config(config_path: str = "config/sites.json") -> list:
    if not os.path.exists(config_path):
        yaml_path = "config/sites.yaml"
        if os.path.exists(yaml_path):
            try:
                import yaml
                with open(yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                return data.get("sources", [])
            except Exception:
                pass
        logger.error(f"Configuration file not found at {config_path}")
        return []

    try:
        import json
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading {config_path}: {e}")
        return []


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def main(run_id: Optional[str] = None):
    logger.info("=== Starting JurisMon Daily Ingestion & Diff Run ===")
    start_time = time.time()
    sources = load_sites_config()
    
    if not sources:
        logger.warning("No sources configured to crawl. Exiting.")
        return

    repo = Repository()
    diff_engine = DiffEngine()
    requests_fetcher = RequestsCrawler()

    sources_succeeded = 0
    sources_failed = 0
    failure_details = []
    total_docs_processed = 0
    total_diffs_created = 0

    active_sources = [s for s in sources if s.get("is_active", True)]
    total_sources = len(active_sources)

    run_id = run_id or repo.start_crawl_run()
    run_status = "failed"

    try:
        for source_cfg in sources:
            if not source_cfg.get("is_active", True):
                continue

            source_name = source_cfg.get("name", "Unnamed")
            adapter_type = source_cfg.get("adapter_type", "custom")
            logger.info(f"--- Processing Source: {source_name} (Adapter: {adapter_type}) ---")

            try:
                adapter = get_adapter(adapter_type)
                result = adapter.crawl(source_cfg)

                if not result.success:
                    logger.error(f"Source {source_name} crawl failed: {result.error_message}")
                    sources_failed += 1
                    failure_details.append({"source_name": source_name, "error": str(result.error_message)})
                    continue

                sources_succeeded += 1
                logger.info(f"Discovered {len(result.documents)} documents for {source_name}")

                for doc_item in result.documents:
                    total_docs_processed += 1
                    try:
                        # 1. Fetch document binary/HTML
                        if doc_item.url.lower().endswith(".pdf") or "pdf" in doc_item.url.lower():
                            content_bytes = requests_fetcher.fetch_pdf_bytes(doc_item.url)
                            content_hash = compute_sha256(content_bytes)

                            # Extract text with layout awareness and OCR fallback
                            cleaned_text, raw_text, ocr_applied = PDFExtractor.extract_from_bytes(content_bytes)
                        else:
                            resp = requests_fetcher.fetch_url(doc_item.url)
                            content_bytes = resp.content
                            content_hash = compute_sha256(content_bytes)
                            cleaned_text, raw_text = HTMLExtractor.extract_from_html(resp.text)
                            ocr_applied = False

                        # 2. Database check if repo connected
                        if repo.is_connected():
                            db_source = repo.upsert_source(source_cfg)
                            source_id = db_source["id"] if db_source else source_cfg.get("id")
                            
                            db_doc = repo.get_or_create_document(
                                source_id=source_id,
                                title=doc_item.title,
                                pdf_url=doc_item.url,
                                document_type=doc_item.document_type,
                            )
                            doc_id = db_doc["id"] if db_doc else None

                            if doc_id:
                                latest_snap = repo.get_latest_snapshot(doc_id)
                                # Check if unchanged
                                if latest_snap and latest_snap.get("content_hash") == content_hash:
                                    logger.info(f"Document '{doc_item.title}' unchanged (hash match). Skipping.")
                                    continue

                                # New or Changed: Create snapshot
                                next_version = (latest_snap.get("version", 0) + 1) if latest_snap else 1
                                new_snap = repo.create_snapshot(
                                    document_id=doc_id,
                                    version=next_version,
                                    content_hash=content_hash,
                                    raw_text=raw_text,
                                    cleaned_text=cleaned_text,
                                    ocr_applied=ocr_applied,
                                )

                                # 3. If previous snapshot exists, generate Diff
                                if latest_snap and new_snap:
                                    old_text = latest_snap.get("cleaned_text", "")
                                    diff_res = diff_engine.compare(old_text=old_text, new_text=cleaned_text)
                                    repo.save_diff(
                                        document_id=doc_id,
                                        previous_snapshot_id=latest_snap["id"],
                                        current_snapshot_id=new_snap["id"],
                                        diff_payload=diff_res.model_dump(),
                                    )
                                    total_diffs_created += 1
                                    logger.info(f"Diff generated for '{doc_item.title}': {diff_res.summary}")
                        else:
                            logger.info(f"[Dry Run] Cleaned {len(cleaned_text)} chars from {doc_item.title} (hash: {content_hash[:8]})")

                    except Exception as doc_err:
                        logger.warning(f"Error processing doc {doc_item.url}: {doc_err}")

            except Exception as source_err:
                sources_failed += 1
                failure_details.append({"source_name": source_name, "error": str(source_err)})
                logger.error(f"Error during source execution for {source_name}: {source_err}")

        if sources_failed == 0:
            run_status = "completed"
        elif sources_succeeded == 0:
            run_status = "failed"
        else:
            run_status = "partial_failure"

        duration = round(time.time() - start_time, 2)
        logger.info(f"=== Daily Crawl Completed in {duration}s ===")
        logger.info(f"Sources: {sources_succeeded} succeeded, {sources_failed} failed | Docs: {total_docs_processed} | Diffs: {total_diffs_created}")

        # An unattended run fails silently otherwise - the log sits on the server
        # and nobody reads it.
        send_crawl_report(
            succeeded=sources_succeeded,
            failed=sources_failed,
            documents=total_docs_processed,
            diffs=total_diffs_created,
            duration_seconds=duration,
            failures=failure_details,
        )
    finally:
        repo.finish_crawl_run(
            run_id=run_id,
            status=run_status,
            total_sources=total_sources,
            sources_succeeded=sources_succeeded,
            sources_failed=sources_failed,
            documents_found=total_docs_processed,
            diffs_created=total_diffs_created,
            error_logs=failure_details,
        )


if __name__ == "__main__":
    main()
