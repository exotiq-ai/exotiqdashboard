"""
Imports manually enriched data from a CSV file into the CRM database.

This script takes a CSV file (exported by export_gaps_for_enrichment.py and
filled out by a human or agent) and updates the corresponding leads in the
database with the new information.
"""

import csv
import sys
from pathlib import Path
from skills.db_utils import update_lead, log_activity, get_lead

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def import_manual_enrichment(file_path: Path):
    """
    Imports enriched data from a CSV and updates the database.

    Args:
        file_path: Path to the completed CSV file.
    """
    if not file_path.exists():
        print(f"Error: File not found at {file_path}")
        return

    updated_leads_count = 0
    with open(file_path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            lead_id = row.get('lead_id')
            if not lead_id:
                continue

            # Fetch the original lead to see what's changed
            original_lead = get_lead(lead_id)
            if not original_lead:
                print(f"Warning: Lead ID {lead_id} from CSV not found in DB. Skipping.")
                continue

            # Build a dictionary of fields to update
            update_data = {}
            newly_filled_fields = []

            # Check each field and add to update_data if it's newly filled
            fields_to_check = {
                'contact_first_name': row.get('contact_first_name_fill'),
                'contact_last_name': row.get('contact_last_name_fill'),
                'contact_email': row.get('contact_email_fill'),
                'contact_phone': row.get('contact_phone_fill'),
            }

            for field, new_value in fields_to_check.items():
                if new_value and not original_lead.get(field):
                    update_data[field] = new_value
                    # Also set the provenance for the new data
                    update_data[f"{field}_source"] = "coworker_manual"
                    update_data[f"{field}_confidence"] = "ESTIMATED"
                    newly_filled_fields.append(field)

            # If there's new data, update the lead and log it
            if update_data:
                try:
                    update_lead(lead_id, update_data)
                    log_activity(
                        type="enrichment",
                        description=f"Manually enriched with new data for fields: {', '.join(newly_filled_fields)}",
                        lead_id=lead_id,
                        source="coworker_manual",
                        agent="import_manual_enrichment",
                    )
                    updated_leads_count += 1
                except Exception as e:
                    print(f"Error updating lead {lead_id}: {e}")

    print(f"\nImport complete.")
    print(f"Successfully updated {updated_leads_count} leads with new information.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import manually enriched leads from a CSV file.")
    parser.add_argument("file_path", type=Path, help="Path to the CSV file to import.")
    args = parser.parse_args()

    import_manual_enrichment(args.file_path)
