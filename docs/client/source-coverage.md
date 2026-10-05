# JurisMon Source Coverage Report

This document records the operational audit status across all 65 configured municipal and statutory data sources in JurisMon.

## Executive Summary

| Category | Count | Status | Notes |
| :--- | :--- | :--- | :--- |
| **Operational Sources** | **41** | **Active & Monitored Daily** | Ingested via automated Playwright, REST API, Atom/RSS, and HTML/PDF pipelines. |
| **Cloudflare Protected** | **7** | **Excluded (Out of Scope)** | Protected by Cloudflare Turnstile / anti-bot challenge (per project spec, CAPTCHA/login bypass is out of scope). |
| **Expired Municipality Links** | **12** | **Excluded (404 / Broken DNS)** | Municipal links dead or migrated on municipality host. |
| **Connection Timeout** | **3** | **Excluded (Unreachable)** | Host server connection timed out or blocks external requests. |
| **Authentication Required** | **1** | **Excluded (API Key Needed)** | Requires registered developer API key from government authority. |
| **HTTP 403 Forbidden** | **1** | **Excluded (Restricted API)** | Automated requests forbidden by government API gateway without pre-approved partner token. |
| **Total Configured** | **65** | | |

---

## Complete Source Coverage Table

| # | Source Name | Target URL | Status | Coverage Details / Exclusion Reason |
| :--- | :--- | :--- | :--- | :--- |
| 1 | New York City Rules | `https://rules.cityofnewyork.us` | Cloudflare | Protected by Cloudflare Turnstile / CAPTCHA (out of project scope). |
| 2 | NYC Planning Commission | `https://www.nyc.gov/site/planning/about/commission.page` | Operational | Ingested and diffed daily. |
| 3 | LA County Regional Planning | `https://planning.lacounty.gov` | Operational | Ingested and diffed daily. |
| 4 | Cook County Government | `https://www.cookcountyil.gov` | Operational | Ingested and diffed daily. |
| 5 | Harris County Engineering & Permits | `https://eng.hctx.net/Permits` | Cloudflare | Protected by Cloudflare Turnstile / CAPTCHA (out of project scope). |
| 6 | Maricopa County Planning & Development | `https://www.maricopa.gov/planning` | Operational | Ingested and diffed daily. |
| 7 | San Diego County Planning | `https://www.sandiegocounty.gov/pds` | Dead Link | HTTP 404 / Broken link on municipality server. |
| 8 | Orange County Florida Zoning | `https://www.orangecountyfl.net` | Operational | Ingested and diffed daily. |
| 9 | Miami-Dade County Regulatory | `https://www.miamidade.gov/economy` | Dead Link | HTTP 404 / Broken link on municipality server. |
| 10 | King County Permitting | `https://kingcounty.gov/depts/permitting.aspx` | Operational | Ingested and diffed daily. |
| 11 | Clark County Nevada Comprehensive Planning | `https://www.clarkcountynv.gov` | Operational | Ingested and diffed daily. |
| 12 | Travis County Permitting Center | `https://www.traviscountytx.gov/tnr/development-services/permitting-center` | Operational | Ingested and diffed daily. |
| 13 | City of Austin Code & Ordinances | `https://www.austintexas.gov/page/code-ordinances` | Dead Link | HTTP 404 / Broken link on municipality server. |
| 14 | Fulton County Government | `https://www.fultoncountyga.gov` | Operational | Ingested and diffed daily. |
| 15 | Dallas County Planning | `https://www.dallascounty.org` | Dead Link | HTTP 404 / Broken link on municipality server. |
| 16 | Riverside County Transportation & Land Management | `https://rctlma.org` | Operational | Ingested and diffed daily. |
| 17 | San Bernardino County Land Use | `https://lu.sbcounty.gov` | Dead Link | HTTP 404 / Broken link on municipality server. |
| 18 | Wayne County Michigan | `https://www.waynecounty.com` | Operational | Ingested and diffed daily. |
| 19 | Tarrant County Administrator | `https://www.tarrantcounty.com` | Dead Link | HTTP 404 / Broken link on municipality server. |
| 20 | Bexar County Texas | `https://www.bexar.org` | Cloudflare | Protected by Cloudflare Turnstile / CAPTCHA (out of project scope). |
| 21 | Santa Clara County Planning & Development | `https://www.sccgov.org/sites/dpd` | Cloudflare | Protected by Cloudflare Turnstile / CAPTCHA (out of project scope). |
| 22 | Ontario Gazette | `https://www.ontario.ca/search/ontario-gazette` | Operational | Ingested and diffed daily. |
| 23 | City of Toronto Municipal Code | `https://www.toronto.ca/legdocs/municode/index.htm` | Operational | Ingested and diffed daily. |
| 24 | British Columbia Laws Gazette | `https://www.bclaws.gov.bc.ca/bcgc/rc.html` | Operational | Ingested and diffed daily. |
| 25 | City of Vancouver Bylaws | `https://vancouver.ca/your-government/vancouver-bylaws.aspx` | Operational | Ingested and diffed daily. |
| 26 | Alberta Gazette | `https://open.alberta.ca/publications/alberta-gazette` | Cloudflare | Protected by Cloudflare Turnstile / CAPTCHA (out of project scope). |
| 27 | Calgary Land Use Bylaw | `https://www.calgary.ca/pda/pd/calgary-land-use-bylaw.html` | Dead Link | HTTP 404 / Broken link on municipality server. |
| 28 | Publications du Québec | `https://www.publicationsquebec.gouv.qc.ca` | Dead Link | HTTP 404 / Broken link on municipality server. |
| 29 | City of Montreal Regulations | `https://montreal.ca/en/regulations` | Dead Link | HTTP 404 / Broken link on municipality server. |
| 30 | City of Ottawa Bylaws | `https://ottawa.ca/en/living-ottawa/laws-licences-and-permits/laws` | Operational | Ingested and diffed daily. |
| 31 | Manitoba Gazette | `https://www.manitoba.ca/gazette` | Operational | Ingested and diffed daily. |
| 32 | UK Legislation Statutory Instruments | `https://www.legislation.gov.uk` | Operational | Ingested and diffed daily. |
| 33 | Greater London Authority Planning | `https://www.london.gov.uk/what-we-do/planning` | Cloudflare | Protected by Cloudflare Turnstile / CAPTCHA (out of project scope). |
| 34 | Birmingham City Council Planning | `https://www.birmingham.gov.uk/planning` | Operational | Ingested and diffed daily. |
| 35 | Manchester City Council Local Plan | `https://www.manchester.gov.uk/info/200074/local_plan` | Operational | Ingested and diffed daily. |
| 36 | Leeds City Council Planning | `https://www.leeds.gov.uk/planning` | Operational | Ingested and diffed daily. |
| 37 | Glasgow City Council Planning | `https://www.glasgow.gov.uk/planning` | Cloudflare | Protected by Cloudflare Turnstile / CAPTCHA (out of project scope). |
| 38 | Bristol City Council Planning Regulations | `https://www.bristol.gov.uk/planning-and-building-regulations` | Operational | Ingested and diffed daily. |
| 39 | City of Edinburgh Planning | `https://www.edinburgh.gov.uk/planning` | Operational | Ingested and diffed daily. |
| 40 | The Edinburgh Gazette | `https://www.theedinburghgazette.co.uk` | Dead Link | HTTP 404 / Broken link on municipality server. |
| 41 | The London Gazette Official Public Record | `https://www.thegazette.co.uk` | Operational | Ingested and diffed daily. |
| 42 | Federal Register of Legislation Australia | `https://www.legislation.gov.au` | Operational | Ingested and diffed daily. |
| 43 | NSW Legislation | `https://www.legislation.nsw.gov.au` | Operational | Ingested and diffed daily. |
| 44 | City of Sydney Council | `https://www.cityofsydney.nsw.gov.au` | Operational | Ingested and diffed daily. |
| 45 | Victorian Legislation | `https://www.legislation.vic.gov.au` | Operational | Ingested and diffed daily. |
| 46 | City of Melbourne Planning | `https://www.melbourne.vic.gov.au` | Dead Link | HTTP 404 / Broken link on municipality server. |
| 47 | Queensland Legislation | `https://www.legislation.qld.gov.au` | Operational | Ingested and diffed daily. |
| 48 | Brisbane City Council Planning | `https://www.brisbane.qld.gov.au` | Operational | Ingested and diffed daily. |
| 49 | Western Australian Legislation | `https://www.legislation.wa.gov.au` | Operational | Ingested and diffed daily. |
| 50 | City of Perth Planning & Development | `https://www.perth.wa.gov.au` | Operational | Ingested and diffed daily. |
| 51 | South Australian Legislation | `https://www.legislation.sa.gov.au` | Operational | Ingested and diffed daily. |
| 52 | Australia Federal Register of Legislation (REST API) | `https://api.prod.legislation.gov.au/v1/titles` | Operational | Ingested and diffed daily via OData REST API. |
| 53 | Victoria Planning Schemes | `https://planning-schemes.app.planning.vic.gov.au/` | Operational | Ingested and diffed daily via Playwright browser automation. |
| 54 | UK Legislation - New Statutory Instruments (Atom Feed) | `https://www.legislation.gov.uk/new/uksi` | Operational | Ingested and diffed daily via Atom syndication feed. |
| 55 | UK Planning Data API | `https://www.planning.data.gov.uk/entity.json` | Operational | Ingested and diffed daily via Open Data JSON API. |
| 56 | Canada Point-in-Time Bulk XML (Open Data) | `https://open.canada.ca/data/en/dataset/4d277b82-c4af-4431-b31d-48fcece6dd8a` | Operational | Ingested and diffed daily via federal Open Data consolidations. |
| 57 | New Zealand Resource Management Act 1991 (XML) | `https://www.legislation.govt.nz/act/public/1990/109/en/latest.xml` | Operational | Ingested and diffed daily via XML feed. |
| 58 | New Zealand Resource Management Act 1991 (PDF) | `https://www.legislation.govt.nz/act/public/1990/109/en/latest.pdf` | Operational | Ingested and diffed daily via PDF parsing. |
| 59 | Germany - Gesetze im Internet | `https://www.gesetze-im-internet.de/` | Operational | Ingested and diffed daily. |
| 60 | UK data.gov.uk Catalogue API | `https://data.gov.uk/api/action/` | Blocked 403 | Government gateway returns HTTP 403 to automated clients without partner API key. |
| 61 | Canada Justice Laws XML Index | `https://laws-lois.justice.gc.ca/eng/XML/Legis.xml` | Timeout | Connection timed out; government host unreachable during audits. |
| 62 | Canada Justice Laws Website | `https://laws-lois.justice.gc.ca/eng/` | Timeout | Connection timed out; government host unreachable during audits. |
| 63 | New Zealand Legislation API | `https://api.legislation.govt.nz/v0/works/` | Auth Required | Returns HTTP 401 Unauthorized; requires developer registration key from NZ PCO. |
| 64 | EU Publications Office CELLAR | `https://publications.europa.eu/resource/cellar/` | Dead Link | Root endpoint returns HTTP 404 Not Found; requires specific resource identifier. |
| 65 | Germany XML Table of Contents | `https://www.gesetze-im-internet.de/gii-toc.xml` | Timeout | Host connection error on XML endpoint while parent portal remains operational. |
