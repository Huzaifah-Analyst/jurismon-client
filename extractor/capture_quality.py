"""Conservative checks for known non-document captures, including old snapshots."""
from urllib.parse import urlparse


def capture_issue(url: str, text: str):
    if not (text or '').strip():
        return 'empty_text'
    normalized = ' '.join(text.lower().replace('\u2019', "'").split())
    if ("verify that you're not a robot" in normalized
            and ('requires javascript' in normalized or 'javascript is disabled' in normalized)):
        return 'bot_check_interstitial'
    parsed = urlparse(url or '')
    host = (parsed.hostname or '').lower()
    if host == 'www.gesetze-im-internet.de' and parsed.path == '/aktuDienst.html':
        return 'rss_catalogue'
    if host == 'open.canada.ca' and parsed.path.startswith('/data/') and '/dataset/' in parsed.path:
        return 'dataset_metadata_or_resource_wrapper'
    if host == 'www.legislation.gov.au' and all(marker in text for marker in
            ('Save this title to My Account', 'Set up an alert', 'View document', 'Select value')):
        return 'registry_wrapper'
    return None
