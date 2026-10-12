"""Review title repairs from stored evidence; --apply uses compare-and-set updates."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db.repository import Repository
from extractor.document_title import corrected_title, is_navigation_title


def repair(repository, apply=False):
    if repository.supabase:
        rows = []
        offset = 0
        while True:
            batch = repository.supabase.table('documents').select('id,title,source_id,sources(name)').or_(
                'title.eq.Correction Slip,title.ilike.Page%,title.ilike.Last page%'
            ).order('id').range(offset, offset + 199).execute().data or []
            rows.extend(batch)
            if len(batch) < 200:
                break
            offset += 200
    else:
        with repository._connect() as connection:
            rows = [dict(zip(('id', 'title', 'name', 'raw_text'), row)) for row in connection.execute(
                'SELECT d.id,d.title,s.name,(SELECT raw_text FROM snapshots WHERE document_id=d.id ORDER BY crawled_at DESC LIMIT 1) FROM documents d JOIN sources s ON d.source_id=s.id')]
    changes = []
    for row in rows:
        source = row.get('sources') or {}
        if isinstance(source, list):
            source = source[0] if source else {}
        name = row.get('name') or source.get('name', '')
        if 'Ontario Gazette' not in name and 'UK Legislation' not in name:
            continue
        old = row.get('title') or ''
        if not is_navigation_title(old) and old.lower() != 'correction slip':
            continue
        snapshot = repository.get_latest_snapshot(row['id']) if repository.supabase else None
        text = row.get('raw_text') or ((snapshot or {}).get('raw_text') or '')
        new = corrected_title(old, name, text=text)
        changes.append({'document_id': row['id'], 'old_title': old, 'new_title': new,
                        'applied': repository.correct_document_title(row['id'], old, new) if apply else False})
    return changes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository = Repository()
    result = repair(repository, False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    if args.apply:
        # Preserve original titles before the first mutation, including on a
        # partially failed run. Compare-and-set protects concurrent edits.
        for row in result:
            row['applied'] = repository.correct_document_title(
                row['document_id'], row['old_title'], row['new_title'])
            args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f'Reviewed {len(result)} title corrections; applied {sum(r["applied"] for r in result)}.')
