"""
Imports newly discovered leads from JSON files into the main CRM database.

This script reads all .json files from the data/discovery/ directory,
de-duplicates them against existing leads, assigns new unique IDs,
and inserts them into the database.
"""

import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "exotiq.db"
DISCOVERY_DIR = PROJECT_ROOT / "data" / "discovery"

MARKET_CODES = {
    'Chicago': 'chi', 'Phoenix': 'phx', 'Philadelphia': 'phl',
    'San Antonio': 'sat', 'San Diego': 'san', 'Dallas': 'dal',
    'Austin': 'aus', 'Jacksonville': 'jax', 'San Jose': 'sjc',
    'Fort Worth': 'ftw',
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def import_discovered_leads():
    """
    Imports discovered leads from the data/discovery directory into the database.
    """
    conn = get_db()
    
    # Get existing company names to avoid duplicates
    existing_companies = {row['company'].lower() for row in conn.execute("SELECT company FROM leads")}
    
    # Get the latest lead number for each market code
    lead_counters = {}
    for code in MARKET_CODES.values():
        result = conn.execute(f"SELECT id FROM leads WHERE id LIKE 'lead_{code}_%' ORDER BY id DESC LIMIT 1").fetchone()
        if result:
            lead_counters[code] = int(result['id'].split('_')[-1])
        else:
            lead_counters[code] = 0

    conn.close()

    json_files = list(DISCOVERY_DIR.glob("*.json"))
    if not json_files:
        print("No new discovery files to import.")
        return

    all_new_leads = []
    for file in json_files:
        with open(file, 'r', encoding='utf-8') as f:
            all_new_leads.extend(json.load(f))

    leads_to_insert = []
    for lead in all_new_leads:
        if lead['company_name'].lower() not in existing_companies:
            market = lead['market']
            market_code = MARKET_CODES.get(market, 'unk')
            
            lead_counters[market_code] = lead_counters.get(market_code, 0) + 1
            new_id = f"lead_{market_code}_{str(lead_counters[market_code]).zfill(3)}"
            
            now = datetime.now(timezone.utc).isoformat()
            
            leads_to_insert.append({
                'id': new_id,
                'company': lead['company_name'],
                'market': market,
                'company_website': lead.get('website'),
                'lead_source': lead.get('lead_source', 'discovery_agent_v1'),
                'outreach_status': 'New',
                'created_at': now,
                'updated_at': now,
            })
            existing_companies.add(lead['company_name'].lower())

    if not leads_to_insert:
        print("No new, unique leads to import after de-duplication.")
        return

    # Bulk insert the new leads
    conn = get_db()
    cursor = conn.cursor()
    try:
        for lead in leads_to_insert:
            cols = ', '.join(lead.keys())
            placeholders = ', '.join('?' for _ in lead)
            cursor.execute(f"INSERT INTO leads ({cols}) VALUES ({placeholders})", list(lead.values()))
        conn.commit()
    finally:
        conn.close()

    print(f"Successfully imported {len(leads_to_insert)} new leads into the database.")
    # Clean up the discovery files after successful import
    for file in json_files:
        file.unlink()
    print("Cleaned up temporary discovery files.")

if __name__ == "__main__":
    import_discovered_leads()
