"""
Lead Discovery Script for the Exotiq Lead Intelligence Pipeline.

This script takes a city and a list of search query templates to find new
exotic and luxury car rental businesses. It uses the web_search tool,
filters out major corporations, and extracts company names and websites.

The output is a JSON file containing a list of discovered leads for that city.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import List, Dict, Set

# This script is intended to be run by a sub-agent, which has the `web_search`
# tool available in its environment. We simulate this for local testing.
try:
    from claw.tools import web_search
except ImportError:
    print("Warning: web_search tool not found. Using dummy implementation.")
    def web_search(query: str, count: int = 10) -> List[Dict[str, str]]:
        return [{"title": f"Dummy Result for {query}", "url": f"https://dummy-{query.replace(' ', '-')}.com", "snippet": "A dummy search result."}]

# --- Constants ---
# Major corporations to be excluded from the results.
EXCLUSION_LIST = {"hertz", "enterprise", "avis", "budget", "sixt", "thrifty", "dollar", "turo"}

# Regex to extract a clean domain name from a URL.
DOMAIN_REGEX = re.compile(r"https?://(?:www\.)?([^/]+)")

# Search query templates.
QUERY_TEMPLATES = [
    "exotic car rental {city}",
    "luxury car rental {city}",
    "lamborghini rental {city}",
    "ferrari rental {city}",
    "supercar rental {city}",
]

def discover_leads(city: str, output_path: Path) -> None:
    """
    Discovers new leads in a given city and saves them to a JSON file.

    Args:
        city: The city to search for leads in.
        output_path: The file path to save the JSON output.
    """
    print(f"Starting lead discovery for: {city}")
    
    discovered_domains: Set[str] = set()
    all_leads: List[Dict[str, str]] = []

    for template in QUERY_TEMPLATES:
        query = template.format(city=city)
        print(f"  > Searching: '{query}'")
        
        try:
            results = web_search(query=query, count=10)
        except Exception as e:
            print(f"    ! Error during web search for '{query}': {e}")
            continue

        for result in results:
            title = result.get("title", "")
            url = result.get("url", "")

            # --- Filtering ---
            # 1. Check against exclusion list
            if any(excluded in title.lower() or excluded in url.lower() for excluded in EXCLUSION_LIST):
                continue

            # 2. Check for domain uniqueness to avoid duplicates
            domain_match = DOMAIN_REGEX.search(url)
            if not domain_match:
                continue
            
            domain = domain_match.group(1)
            if domain in discovered_domains:
                continue

            # --- Data Extraction ---
            # A simple title clean-up. More sophisticated parsing can be added.
            company_name = re.sub(r"\|.*$", "", title).strip()
            company_name = re.sub(r"-.*$", "", company_name).strip()

            if not company_name:
                continue

            # --- Add to list ---
            discovered_domains.add(domain)
            all_leads.append({
                "company_name": company_name,
                "website": url,
                "market": city,
                "lead_source": "discovery_agent_v1",
            })
        
        # Be a good citizen to the search API
        time.sleep(1)

    # --- Save results ---
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_leads, f, indent=2)

    print(f"Discovery for {city} complete. Found {len(all_leads)} new potential leads.")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Discover new exotic car rental leads in a city.")
    parser.add_argument("city", type=str, help="The target city for lead discovery.")
    parser.add_argument("--output", type=str, default="discovered_leads.json", help="Path to save the output JSON file.")
    args = parser.parse_args()

    discover_leads(args.city, Path(args.output))
