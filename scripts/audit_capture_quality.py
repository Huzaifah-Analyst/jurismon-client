"""Read-only historical-capture audit. Produces a reviewable repair manifest.

Usage: python scripts/audit_capture_quality.py --output test-results/capture-audit.json
Default audit performs no database writes. --apply changes only search visibility.
No snapshot text or diff payloads are deleted or rewritten. Full source text and secrets are
excluded from the manifest; IDs let a reviewed cleanup preserve an audit trail.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db.repository import Repository
from extractor.capture_quality import capture_issue


def audit(repository):
    issues = []
    checked = 0
    if repository.supabase:
        offset = 0
        while True:
            rows = repository.supabase.table('snapshots').select(
                'id,document_id,version,cleaned_text,crawled_at,documents(pdf_url)'
            ).order('id').range(offset, offset + 499).execute().data or []
            for row in rows:
                checked += 1
                document = row.get('documents') or {}
                if isinstance(document, list):
                    document = document[0] if document else {}
                reason = capture_issue(document.get('pdf_url', ''), row.get('cleaned_text', ''))
                if reason:
                    issues.append({'id': row['id'], 'document_id': row['document_id'], 'version': row['version'], 'reason': reason, 'crawled_at': row.get('crawled_at')})
            if len(rows) < 500:
                break
            offset += 500
    else:
        with repository._connect() as connection:
            for row in connection.execute('SELECT s.id,s.document_id,s.version,s.cleaned_text,s.crawled_at,d.pdf_url FROM snapshots s JOIN documents d ON d.id=s.document_id'):
                checked += 1
                reason = capture_issue(row[5], row[3])
                if reason:
                    issues.append({'id': row[0], 'document_id': row[1], 'version': row[2], 'reason': reason, 'crawled_at': row[4]})
    return {'audited_at': datetime.now(timezone.utc).isoformat(), 'checked': checked, 'flagged': len(issues), 'issues': issues, 'mode': 'read_only', 'limits': 'Known empty/catalogue/wrapper patterns only; unflagged text is not certified legal content.'}


def change_visibility(repository, manifest, restore=False):
    reason = manifest.get("applied_reason") or (None if restore else "capture_audit:" + datetime.now(timezone.utc).isoformat())
    if not reason or not reason.startswith("capture_audit:"):
        raise ValueError("Restore requires an applied audit manifest")
    ids = [row["id"] for row in manifest["issues"]]
    affected = {"snapshots": 0, "diffs": 0}
    for start in range(0, len(ids), 100):
        counts = repository.set_capture_visibility(ids[start:start + 100], restore, reason)
        for key in affected:
            affected[key] += counts[key]
    return {**manifest, "mode": "restored" if restore else "quarantined", "applied_reason": reason, "affected": affected}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--apply', action='store_true', help='Quarantine fresh audited captures, preserving history')
    actions.add_argument('--restore-manifest', type=Path, help='Restore only visibility changed by this manifest')
    args = parser.parse_args()
    repository = Repository()
    if args.restore_manifest:
        result = change_visibility(repository, json.loads(args.restore_manifest.read_text(encoding='utf-8-sig')), restore=True)
    else:
        result = audit(repository)
        # Save the reviewed IDs before any operation that could partly fail.
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
        if args.apply:
            result["applied_reason"] = "capture_audit:" + datetime.now(timezone.utc).isoformat()
            args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
            result = change_visibility(repository, result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f"Checked {result['checked']}; flagged {result['flagged']}; mode {result['mode']}.")
