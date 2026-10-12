"""Reject navigation labels; derive titles only from document evidence."""
import re
from bs4 import BeautifulSoup


def is_navigation_title(title):
    return bool(re.fullmatch(r'(?:page\s*\d+|\d+|last\s*page.*|next(?:\s*page)?\s*[\u00bb>]*|previous(?:\s*page)?\s*[\u00ab<]*)',
                             (title or '').strip(), re.I))


def corrected_title(title, source_name, html=None, text=None):
    if not is_navigation_title(title) and (title or '').strip().lower() != 'correction slip':
        return title
    if html:
        soup = BeautifulSoup(html, 'lxml')
        for node in soup.select('.LegInstrumentTitle, .LegTitle, h1, title'):
            candidate = node.get_text(' ', strip=True)
            if candidate and not is_navigation_title(candidate) and candidate.lower() != 'correction slip':
                if candidate.lower() not in ('ontario gazette', 'ontario.ca', 'legislation.gov.uk'):
                    return candidate
    if text:
        lines = text.splitlines()
        for index, line in enumerate(lines):
            candidate = line.strip()
            if 'Ontario Gazette' in source_name and re.match(r'^Ontario Gazette\s+(?:Volume|Vol\.|Issue|\d)', candidate, re.I):
                return candidate
            if re.match(r'^(?:The .*(?:Rules|Regulations|Order)|Rheoliadau |Gorchymyn )', candidate):
                if not re.search(r'\b(?:19|20)\d{2}\b', candidate):
                    continuation = []
                    for following in lines[index + 1:index + 7]:
                        following = following.strip()
                        if not following or re.match(r'^\d+\.', following) or following.lower() == 'correction slip':
                            break
                        continuation.append(following)
                        if re.search(r'\b(?:19|20)\d{2}\b', following):
                            candidate = ' '.join([candidate] + continuation)
                            break
                return candidate
    return f'{source_name} capture, unlabeled'
