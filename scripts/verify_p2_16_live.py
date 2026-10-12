"""P2-16 browser timings/polling and TLS source diagnostics; never deploys."""
import argparse
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trigger-crawl', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('test-results/p2-16/live.json'))
    args = parser.parse_args()
    # Credential contents and tokens must never enter evidence/output.
    credentials = {}
    for line in Path('credentials/admin_password_rotated.txt').read_text(encoding='utf-8-sig').splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            credentials[key.strip().lower()] = value.strip()
    email = next(v for k, v in credentials.items() if 'email' in k)
    password = next(v for k, v in credentials.items() if 'password' in k)
    evidence = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        base = 'https://jurismon.com'
        page.goto(base + '/')
        evidence['health'] = page.request.get(base + '/api/health').json()
        login = page.request.post(base + '/api/admin/login', data={'email': email, 'password': password})
        assert login.ok, f'Admin login failed ({login.status})'
        token = login.json()['access_token']
        page.add_init_script('localStorage.setItem("jurismon_admin_token", ' + json.dumps(token) + ')')
        evidence['search'] = page.evaluate('''async token => {
            const samples=[];
            for(let i=0;i<3;i++){
                const start=performance.now();
                const r=await fetch('/api/search?q=zoning', {headers:{Authorization:'Bearer '+token}});
                const data=await r.json();
                samples.push({ms:performance.now()-start,status:r.status,count:data.items?.length,gated:data.is_gated,total_snapshots:data.total_snapshots,total_diffs:data.total_diffs});
            }
            return samples;
        }''', token)
        evidence['zero_match'] = page.evaluate('''async token => {
            const r=await fetch('/api/search?q=p216nonexistentzzzz', {headers:{Authorization:'Bearer '+token}});
            const d=await r.json();return {status:r.status,count:d.items?.length,total_snapshots:d.total_snapshots,total_diffs:d.total_diffs};
        }''', token)
        polls = []
        page.on('response', lambda r: polls.append({'seconds': round(time.monotonic(), 2), 'status': r.status}) if '/api/admin/crawl/status' in r.url else None)
        page.goto(base + '/admin')
        page.locator('#btn-run-crawl').wait_for()
        if args.trigger_crawl:
            page.locator('#btn-run-crawl').click()
        started = time.monotonic()
        for _ in range(7):
            page.wait_for_timeout(5000)
        evidence['polling'] = {'observed_seconds': round(time.monotonic()-started, 2), 'requests': polls, 'trigger_requested': args.trigger_crawl}
        status = page.request.get(base + '/api/admin/crawl/status', headers={'Authorization':'Bearer '+token})
        if status.ok:
            data = status.json()
            evidence['crawl_status'] = {k: data.get(k) for k in ('status','sources_succeeded','sources_failed','failure_details')}
        browser.close()
    sites = json.loads(Path('config/sites.json').read_text())
    selected = ['site-02-nyc', 'site-07-sandiego', 'site-11-clarkcountynv', 'site-12-traviscountytx', 'site-13-austintexas']
    candidates = [s for s in sites if s['id'] in selected or any(word in s['name'] for word in ('San Diego', 'Clark County'))]
    def probe(source):
        result = {'id':source['id'], 'name':source['name'], 'url':source['base_url']}
        try:
            response = requests.get(source['base_url'], timeout=(10, 45))
            result.update(status=response.status_code, bytes=len(response.content), tls_verified=True)
            if response.ok:
                selector = (source.get('selectors_config') or {}).get('link_selector', 'a[href]')
                links = BeautifulSoup(response.content, 'lxml').select(selector)
                result['matching_links'] = len(links)
                link = next((a for a in links if '.pdf' in (a.get('href') or '').lower() or '/edims/document.cfm' in (a.get('href') or '')), None)
                if link:
                    target = urljoin(response.url, link['href'])
                    try:
                        document = requests.get(target, timeout=(10, 60))
                        result['document_probe'] = {'url': target, 'status': document.status_code, 'pdf_signature': document.content.startswith(b'%PDF-'), 'bytes':len(document.content)}
                    except requests.RequestException as error:
                        result['document_probe'] = {'url':target, 'error':type(error).__name__}
        except requests.exceptions.SSLError:
            result.update(error='TLS verification failed; verification was not disabled')
        except requests.RequestException as error:
            result.update(error=type(error).__name__)
        return result
    with ThreadPoolExecutor(max_workers=5) as executor:
        evidence['source_probes'] = list(executor.map(probe, candidates))
    try:
        response = requests.get('https://files.clarkcountynv.gov/', timeout=(10, 30))
        evidence['clark_files_tls'] = {'status':response.status_code, 'tls_verified':True}
    except requests.exceptions.SSLError:
        evidence['clark_files_tls'] = {'error':'TLS verification failed with default CA bundle; root cause not yet established'}
    except requests.RequestException as error:
        evidence['clark_files_tls'] = {'error':type(error).__name__}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
