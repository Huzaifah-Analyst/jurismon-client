import re
import yaml
from urllib.parse import urlparse

def generate_sites_yaml():
    with open("jurismon_links.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()

    sources = []
    for line in lines:
        line = line.strip()
        match = re.match(r"^\d+\.\s*(https?://[^\s]+)", line)
        if match:
            url = match.group(1).rstrip("/")
            domain = urlparse(url).netloc
            path = urlparse(url).path
            
            # Determine site id and display name
            clean_domain = domain.replace("www.", "").split(".")[0]
            site_id = f"site-{len(sources) + 1:02d}-{clean_domain}"
            name = f"{clean_domain.capitalize()} Statutory Monitor"

            # Determine adapter
            adapter_type = "custom"
            if "municode" in url:
                adapter_type = "municode"
            elif "legistar" in url or "granicus" in url:
                adapter_type = "granicus"
            elif "civicplus" in url:
                adapter_type = "civicplus"

            sources.append({
                "id": site_id,
                "name": name,
                "base_url": url,
                "adapter_type": adapter_type,
                "selectors_config": {
                    "link_selector": "a[href*='.pdf'], a[href*='notice'], a[href*='bylaw'], a[href*='ordinance'], a[href*='planning']"
                },
                "is_active": True
            })

    output = {"sources": sources}
    with open("config/sites.yaml", "w", encoding="utf-8") as f:
        yaml.dump(output, f, sort_keys=False, indent=2)

    print(f"Generated config/sites.yaml with {len(sources)} sources.")

if __name__ == "__main__":
    generate_sites_yaml()
