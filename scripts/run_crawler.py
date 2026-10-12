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
from crawler.url_normalizer import URLNormalizer
from extractor.pdf_extractor import PDFExtractor
from extractor.html_extractor import HTMLExtractor
from extractor.capture_quality import capture_issue
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


def main(run_id: Optional[str] = None, source_ids: Optional[List[str]] = None):
    logger.info("=== Starting JurisMon Daily Ingestion & Diff Run ===")
    start_time = time.time()
    sources = load_sites_config()
    
    if source_ids:
        selected = set(source_ids)
        known = {source.get("id") for source in sources}
        if selected - known:
            raise ValueError("Unknown source IDs: " + ", ".join(sorted(selected - known)))
        sources = [source for source in sources if source.get("id") in selected]
        logger.info("Selected source-only crawl: %s", ", ".join(sorted(selected)))

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
    skipped_sources = [s for s in sources if not s.get("is_active", True)]
    total_sources = len(active_sources)
    sources_skipped = len(skipped_sources)
    skipped_details = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "url": s.get("base_url") or s.get("url"),
            "reason": s.get("health_status") or "inactive",
        }
        for s in skipped_sources
    ]

    if not run_id:
        active = repo.get_active_crawl_run()
        if active and active.get("id"):
            run_id = active["id"]
        else:
            run_id = repo.start_crawl_run()
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

                logger.info(f"Discovered {len(result.documents)} documents for {source_name}")
                processing_errors = []
                usable_documents = 0

                for doc_item in result.documents:
                    total_docs_processed += 1
                    try:
                        title_html = None
                        # 1. Fetch document binary/HTML
                        if doc_item.url.lower().endswith(".pdf") or "pdf" in doc_item.url.lower():
                            content_bytes = requests_fetcher.fetch_pdf_bytes(doc_item.url)
                            content_hash = compute_sha256(content_bytes)

                            # Extract text with layout awareness and OCR fallback
                            cleaned_text, raw_text, ocr_applied, _ = PDFExtractor.extract_from_bytes(content_bytes)
                        else:
                            resp = requests_fetcher.fetch_url(doc_item.url)
                            # Official document handlers such as Austin's document.cfm
                            # return PDFs without a .pdf suffix. Inspect the response
                            # before decoding binary content as HTML.
                            if URLNormalizer.is_pdf(doc_item.url, resp.headers.get("content-type", "")) or resp.content.startswith(b"%PDF-"):
                                content_bytes = resp.content
                                cleaned_text, raw_text, ocr_applied, _ = PDFExtractor.extract_from_bytes(content_bytes)
                            else:
                                extraction_url = doc_item.url
                                embedded_url = HTMLExtractor.embedded_document_url(resp.text, extraction_url)
                                if embedded_url:
                                    resp = requests_fetcher.fetch_url(embedded_url)
                                    extraction_url = embedded_url
                                content_bytes = resp.content
                                cleaned_text, raw_text = HTMLExtractor.extract_from_html(
                                    resp.text,
                                    target_selector=(source_cfg.get("selectors_config") or {}).get("content_selector"),
                                    source_url=extraction_url,
                                )
                                title_html = resp.text
                                ocr_applied = False
                            content_hash = compute_sha256(content_bytes)

                        issue = capture_issue(doc_item.url, cleaned_text)
                        if issue:
                            logger.warning("Skipping non-document capture (%s): %s", issue, doc_item.url)
                            processing_errors.append({"url": doc_item.url, "error": issue})
                            continue

                        from extractor.document_title import corrected_title
                        doc_item.title = corrected_title(doc_item.title, source_name, html=title_html, text=raw_text)
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
                            if db_doc and db_doc.get('title') != doc_item.title:
                                from extractor.document_title import is_navigation_title
                                old_title = db_doc.get('title', '')
                                if is_navigation_title(old_title) or old_title.lower() == 'correction slip':
                                    repo.correct_document_title(doc_id, old_title, doc_item.title)

                            if doc_id:
                                latest_snap = repo.get_latest_snapshot(doc_id)
                                # Check if unchanged
                                if latest_snap and latest_snap.get("content_hash") == content_hash:
                                    logger.info(f"Document '{doc_item.title}' unchanged (hash match). Skipping.")
                                    if latest_snap.get("is_searchable", True):
                                        usable_documents += 1
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
                                if not new_snap:
                                    raise RuntimeError("Snapshot persistence was not confirmed")
                                usable_documents += 1

                                # 3. If previous snapshot exists, generate Diff
                                if latest_snap and new_snap and latest_snap.get("is_searchable", True) and not capture_issue(doc_item.url, latest_snap.get("cleaned_text", "")):
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
                                raise RuntimeError("Document persistence was not confirmed")
                        else:
                            logger.info(f"[Dry Run] Cleaned {len(cleaned_text)} chars from {doc_item.title} (hash: {content_hash[:8]})")

                    except Exception as doc_err:
                        logger.warning(f"Error processing doc {doc_item.url}: {doc_err}")
                        processing_errors.append({"url": doc_item.url, "error": str(doc_err)[:500]})

                if processing_errors or usable_documents == 0:
                    sources_failed += 1
                    failure_details.append({"source_name": source_name, "error": "Document ingestion incomplete" if processing_errors else "No usable stored legal documents", "documents": processing_errors})
                else:
                    sources_succeeded += 1

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
        logger.info(
            f"Sources: {total_sources} crawled, {sources_succeeded} succeeded, "
            f"{sources_failed} failed, {sources_skipped} skipped | "
            f"Docs: {total_docs_processed} | Diffs: {total_diffs_created}"
        )

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
            sources_skipped=sources_skipped,
            skipped_sources=skipped_details,
        )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", help="Crawl only this configured source ID; repeat for a subset")
    args = parser.parse_args()
    main(source_ids=args.source)
