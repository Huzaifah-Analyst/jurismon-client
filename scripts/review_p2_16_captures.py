"""Read-only review of production title/bot findings; no capture text exported."""
import json
import sys
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extractor.capture_quality import capture_issue
from extractor.document_title import corrected_title, is_navigation_title


def main():
    credentials = {}
    for line in Path('credentials/admin_password_rotated.txt').read_text(encoding='utf-8-sig').splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            credentials[key.strip().lower()] = value.strip()
    email = next(v for k, v in credentials.items() if 'email' in k)
    password = next(v for k, v in credentials.items() if 'password' in k)
    session = requests.Session()
    login = session.post('https://jurismon.com/api/admin/login', json={'email':email, 'password':password}, timeout=30)
    login.raise_for_status()
    session.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
    findings = {}
    for query in ('', 'Crimes Act', 'Correction Slip', 'robot'):
        response = session.get('https://jurismon.com/api/search', params={'q':query}, timeout=60)
        response.raise_for_status()
        payload = response.json()
        assert payload.get('is_gated') is False
        for item in payload.get('items', []):
            title, source = item.get('doc', ''), item.get('entity', '')
            issue = capture_issue(item.get('url', ''), item.get('full', ''))
            if issue or is_navigation_title(title) or title.lower() == 'correction slip' or 'Crimes Act' in title:
                findings[item['id']] = {'id':item['id'], 'source':source, 'old_title':title,
                    'proposed_title':corrected_title(title, source, text=item.get('full', '')),
                    'capture_issue':issue, 'characters':len(item.get('full', ''))}
    path = Path('test-results/p2-16/capture-review.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(findings.values()), indent=2), encoding='utf-8')
    print(json.dumps(list(findings.values()), indent=2))


if __name__ == '__main__':
    main()
