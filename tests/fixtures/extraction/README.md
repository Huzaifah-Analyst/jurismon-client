# Public extraction fixtures

Captured 11 October 2026 from the public government URLs below. These are
sanitized content subtrees: scripts, styles, metadata, forms, inputs and nonce
attributes were removed. No cookies, session tokens or local credentials are
retained. Full unmodified captures remain in ignored local test artifacts.

- germany-rss.html: https://www.gesetze-im-internet.de/aktuDienst.html
- canada-resource.html: https://open.canada.ca/data/en/dataset/4d277b82-c4af-4431-b31d-48fcece6dd8a/resource/93ca8728-3ee3-4156-8b41-4633e1cb688e
- australia-act.html: https://www.legislation.gov.au/C1914A00034
- australia-document.html: https://www.legislation.gov.au/C1914A00034/asmade/1914-12-21/text/original/epub/OEBPS/document_1/document_1.html

The NZ XML URL from config returned an empty body during this capture. It is
not represented as a successful statutory-text fixture or a repaired source.

Source-repair fixtures captured 11 October 2026 contain only selected public
legal-document anchors, with no scripts, forms or page/session metadata:

- san-diego-code-updates.html: https://www.sandiegocounty.gov/content/sdc/pds/zoning/CodeUpdates/
- site-17-sbcounty.html: https://lus.sbcounty.gov/planning-home/development-code/
- site-09-miamidade.html: https://www.miamidade.gov/zoning/districts.asp
- site-13-austintexas.html: https://www.austintexas.gov/development-services/development-policy-corner
- site-05-hctx.html: https://oce.harriscountytx.gov/Divisions/Watershed-Protection/Regulations-Standards-Forms
- site-15-dallascounty.html: https://www.dallascounty.org/departments/pubworks/permits-development.php
- site-20-bexar.html: https://www.bexar.org/3219/Post-Construction
- site-19-tarrantcounty.html: https://www.tarrantcountytx.gov/en/engineering-services/development/subdivision-and-land-use-regulations.html

These listings establish discovery; separate read-only VPS checks extracted
actual legal PDFs. Full document binaries were not committed.
