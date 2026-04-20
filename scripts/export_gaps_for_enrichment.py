"""
Exports a list of leads with missing key information for manual enrichment.

This script queries the database for leads that are missing a first name, email,
or phone number, and outputs them to a CSV file. This file can be handed off
to a human or another agent for manual research.

The output CSV includes the lead_id, which is essential for the corresponding
import_manual_enrichment.py script to merge the data back in.
"""

import sqlite3
import csv
from pathlib import Path
from datetime import datetime

# Add project root to path to allow sibling imports
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "db" / "exotiq.db"
OUTPUT_DIR = PROJECT_ROOT / "data" / "manual_enrichment"

def export_gaps():
    """
    Exports leads with missing contact info to a timestamped CSV file.
    """
    # Ensure the full path to the output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = OUTPUT_DIR / f"enrichment_needed_{timestamp}.csv"

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Query for leads that are not marked 'Not a Fit' and are missing a name or email.
    # We prioritize these as they are the most critical gaps.
    cursor = conn.execute("""
        SELECT
            id,
            company,
            market,
            company_website,
            company_ig_handle,
            contact_first_name,
            contact_last_name,
            contact_email,
            contact_phone
        FROM leads
        WHERE 
            (contact_first_name IS NULL OR contact_email IS NULL)
            AND (outreach_status IS NULL OR outreach_status != 'Not a Fit')
    """)
    
    leads = cursor.fetchall()
    conn.close()

    if not leads:
        print("No leads found with critical enrichment gaps.")
        return

    # Write to CSV
    with open(output_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Write header
        header = [
            'lead_id', 'company', 'market', 'website', 'instagram',
            'contact_first_name_fill', 'contact_last_name_fill', 
            'contact_email_fill', 'contact_phone_fill'
        ]
        writer.writerow(header)

        # Write lead data
        for lead in leads:
            writer.writerow([
                lead['id'],
                lead['company'],
                lead['market'],
                lead['company_website'],
                lead['company_ig_handle'],
                lead['contact_first_name'], # Pre-fill what we have
                lead['contact_last_name'],
                lead['contact_email'],
                lead['contact_phone'],
            ])

    print(f"Successfully exported {len(leads)} leads needing enrichment.")
    print(f"File saved to: {output_filename}")

if __name__ == "__main__":
    export_gaps()
