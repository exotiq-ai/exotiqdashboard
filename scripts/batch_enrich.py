import sqlite3
import time
from pathlib import Path
import sys
from dotenv import load_dotenv

# Add project root to path and load .env
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


from skills.lead_enrichment import enrich_lead

DB_PATH = PROJECT_ROOT / "db" / "exotiq.db"

def run_batch_enrichment():
    """
    Finds all unenriched leads and enriches them.
    An unenriched lead is defined as one where `enrichment_history` is NULL.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM leads WHERE enrichment_history IS NULL")
    leads_to_enrich = [row['id'] for row in cursor.fetchall()]
    
    print(f"Found {len(leads_to_enrich)} leads to enrich.")
    
    for i, lead_id in enumerate(leads_to_enrich):
        print(f"[{i+1}/{len(leads_to_enrich)}] Enriching lead '{lead_id}'...")
        try:
            summary = enrich_lead(lead_id)
            print(f"  > Success. Updated fields: {summary.get('fields_updated', 'none')}")
        except Exception as e:
            print(f"  > ERROR enriching {lead_id}: {e}")
        
        # Rate limit to be kind to APIs
        time.sleep(1.5)

    conn.close()
    print("Batch enrichment complete.")

if __name__ == "__main__":
    run_batch_enrichment()
