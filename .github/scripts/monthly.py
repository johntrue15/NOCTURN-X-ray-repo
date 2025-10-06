import json
from datetime import datetime
import time
import os
import sys
import logging
import argparse
from morphosource_api import MorphoSourceAPI, MorphoSourceAPIError, MorphoSourceTemporarilyUnavailable

class MonthlyMorphoSourceCollector:
    def __init__(self, data_dir: str = 'data'):
        """Initialize collector with output directory."""
        self.data_dir = data_dir
        self.api = MorphoSourceAPI()
        
        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Define all file paths relative to data directory
        self.complete_data_path = os.path.join(data_dir, 'morphosource_data_complete.json')
        self.release_notes_path = os.path.join(data_dir, 'monthly_release_notes.txt')
        self.stats_path = os.path.join(data_dir, 'monthly_stats.json')
        self.analysis_path = os.path.join(data_dir, 'monthly_analysis.json')
        self.log_path = os.path.join(data_dir, 'monthly_collector.log')
        
        self.setup_logging()
        self.all_records = []
        self.previous_records = {}
        self.modifications = []

    def setup_logging(self):
        """Setup logging to both file and console."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_path),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized collector with output directory: {self.data_dir}")

    def load_existing_data(self):
        """Load and backup existing records and create ID-based lookup"""
        # Look for existing data in root data directory
        root_data_path = os.path.join('data', 'morphosource_data_complete.json')
        
        if os.path.exists(root_data_path):
            self.logger.info(f"Loading existing data from {root_data_path}")
            with open(root_data_path, 'r') as f:
                data = json.load(f)
            
            # Create backup in new directory
            backup_path = os.path.join(self.data_dir, 'previous_data.json')
            with open(backup_path, 'w') as f:
                json.dump(data, f, indent=2)
            self.logger.info(f"Created backup at: {backup_path}")
            
            # Create lookup dictionary
            self.previous_records = {r['id']: r for r in data}
            self.logger.info(f"Loaded {len(data)} existing records")
            return data
        return []

    def analyze_changes(self):
        """Analyze differences between existing and new data"""
        analysis = {
            'total_existing': len(self.previous_records),
            'total_new': len(self.all_records),
            'modified_records': [],
            'new_records': [],
            'removed_records': []
        }

        # Create set of all IDs
        existing_ids = set(self.previous_records.keys())
        new_ids = {r['id'] for r in self.all_records}
        
        # Find new and removed records
        analysis['new_records'] = list(new_ids - existing_ids)
        analysis['removed_records'] = list(existing_ids - new_ids)
        
        # Check for modifications in existing records
        for record in self.all_records:
            if record['id'] in self.previous_records:
                old_record = self.previous_records[record['id']]
                if (old_record['title'] != record['title'] or 
                    old_record['metadata'] != record['metadata']):
                    analysis['modified_records'].append({
                        'id': record['id'],
                        'old': old_record,
                        'new': record,
                        'changes': {
                            'title_changed': old_record['title'] != record['title'],
                            'metadata_changed': old_record['metadata'] != record['metadata']
                        }
                    })
        
        self.logger.info(f"Analysis complete:")
        self.logger.info(f"- Existing records: {analysis['total_existing']}")
        self.logger.info(f"- New records: {len(analysis['new_records'])}")
        self.logger.info(f"- Modified records: {len(analysis['modified_records'])}")
        self.logger.info(f"- Removed records: {len(analysis['removed_records'])}")
        
        # Save analysis to file
        with open(self.analysis_path, 'w') as f:
            json.dump(analysis, f, indent=2)
            
        return analysis

    def save_data(self):
        """Save collected data with validation"""
        try:
            # First analyze changes
            analysis = self.analyze_changes()
            
            # Validate new dataset
            if not self.all_records:
                raise ValueError("No records to save - aborting to prevent data loss")
                
            if len(self.all_records) < len(self.previous_records) * 0.9:
                raise ValueError(
                    f"New record count ({len(self.all_records)}) is less than 90% of "
                    f"previous count ({len(self.previous_records)}) - aborting to prevent data loss"
                )
            
            # Save complete dataset
            self.logger.info("Validation passed - saving new dataset")
            with open(self.complete_data_path, 'w') as f:
                json.dump(self.all_records, f, indent=2)
                
            # Create attestation template
            self.create_attestation_template()
            
            self.create_release_notes(analysis)
            
            return len(self.all_records)
            
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")
            # Restore from backup if it exists
            backup_path = os.path.join(self.data_dir, 'previous_data.json')
            if os.path.exists(backup_path):
                self.logger.info("Restoring from backup")
                with open(backup_path, 'r') as src, open(self.complete_data_path, 'w') as dst:
                    json.dump(json.load(src), dst, indent=2)
            raise

    def create_release_notes(self, analysis):
        """Create detailed release notes with analysis"""
        with open(self.release_notes_path, 'w') as f:
            f.write(f"# Monthly MorphoSource Collection Report\n\n")
            f.write(f"Collection Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary statistics
            f.write("## Summary\n")
            f.write(f"- Total Records: {len(self.all_records)}\n")
            f.write(f"- New Records: {len(analysis['new_records'])}\n")
            f.write(f"- Modified Records: {len(analysis['modified_records'])}\n")
            f.write(f"- Removed Records: {len(analysis['removed_records'])}\n\n")
            
            # Add attestation placeholder
            f.write("## Attestations\n")
            f.write("<!-- ATTESTATION_URLS -->\n\n")
            
            # Modified Records Table
            if analysis['modified_records']:
                f.write("## Modified Records\n\n")
                f.write("| ID | Title | Object ID | Status | Changes | Link |\n")
                f.write("|----|----|----|----|----|----|----|\n")
                for mod in analysis['modified_records']:
                    new_record = mod['new']
                    changes = []
                    if mod['changes']['title_changed']:
                        changes.append("title")
                    if mod['changes']['metadata_changed']:
                        changes.append("metadata")
                    changes_str = ", ".join(changes)
                    
                    f.write(
                        f"| {new_record['id']} | {new_record['title']} | "
                        f"{new_record['metadata'].get('Object', 'N/A')} | "
                        f"{new_record['metadata'].get('Publication Status', 'N/A')} | "
                        f"{changes_str} | "
                        f"[View]({new_record['url']}) |\n"
                    )

    # parse_record method is no longer needed as the API client handles normalization

    def check_for_modifications(self, record):
        """Check if a record has been modified compared to previous version"""
        if record['id'] in self.previous_records:
            old_record = self.previous_records[record['id']]
            # Compare relevant fields
            if (old_record['title'] != record['title'] or 
                old_record['metadata'] != record['metadata']):
                self.modifications.append({
                    'id': record['id'],
                    'old': old_record,
                    'new': record
                })
                return True
        return False

    def save_stats(self):
        """Save collection statistics"""
        stats = {
            'total_records': len(self.all_records),
            'modified_records': len(self.modifications),
            'new_records': len(self.all_records) - len(self.previous_records),
            'collection_date': datetime.now().isoformat(),
            'pages_processed': self.last_page_processed,
            'error_count': self.error_count,
            'checkpoint_status': {
                'last_successful_page': self.last_successful_page,
                'last_successful_id': self.last_successful_id
            }
        }
        
        with open(self.stats_path, 'w') as f:
            json.dump(stats, f, indent=2)
            self.logger.info(f"Saved stats to {self.stats_path}")

    def collect_all_records(self):
        """Collect all records from MorphoSource using the API"""
        self.last_page_processed = 0
        self.last_successful_page = 0
        self.last_successful_id = None
        self.error_count = 0
        page = 1
        per_page = 100
        
        while True:
            try:
                self.logger.info(f"Processing page {page} via API")
                
                try:
                    # Use API to fetch records
                    result = self.api.search_media(
                        query="X-Ray Computed Tomography",
                        sort="system_create_dtsi desc",
                        page=page,
                        per_page=per_page
                    )
                    
                    api_records = result['data']
                    
                    if not api_records:
                        break
                    
                    page_records = []
                    for api_record in api_records:
                        try:
                            # Normalize the record
                            normalized = self.api.normalize_record(api_record)
                            
                            # Convert to the format expected by the rest of the code
                            record = {
                                'id': normalized['id'],
                                'title': normalized['title'],
                                'url': normalized['url'],
                                'metadata': normalized['metadata'],
                                'scraped_date': datetime.now().isoformat()
                            }
                            
                            self.check_for_modifications(record)
                            page_records.append(record)
                            self.last_successful_id = record['id']
                        except Exception as e:
                            self.error_count += 1
                            self.logger.error(f"Error normalizing record on page {page}: {e}")
                            continue
                    
                    # Only add records if page was successful
                    self.all_records.extend(page_records)
                    self.last_successful_page = page
                    self.error_count = 0  # Reset error count after successful page
                    
                    # Checkpoint logging
                    if page % 5 == 0:
                        self.logger.info(
                            f"Checkpoint - Page: {page}, "
                            f"Records: {len(self.all_records)}, "
                            f"Last ID: {self.last_successful_id}"
                        )
                        self.save_stats()  # Save intermediate stats
                    
                    # Check if we've reached the last page
                    if page >= result['meta']['total_pages']:
                        break
                    
                    page += 1
                    self.last_page_processed = page
                    time.sleep(2)  # Rate limiting
                    
                except MorphoSourceAPIError as e:
                    self.error_count += 1
                    self.logger.error(f"API error on page {page}: {e}")
                    if self.error_count >= 5:  # Max consecutive errors
                        break
                    continue
                
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"Error processing page {page}: {e}")
                if self.error_count >= 5:  # Max consecutive errors
                    break

    def run(self):
        """Run the monthly collection process"""
        try:
            self.load_existing_data()
            self.collect_all_records()
            total_records = self.save_data()
            
            self.logger.info(f"Collection complete. Total records: {total_records}")
            self.logger.info(f"Modified records: {len(self.modifications)}")
            
            return total_records
        except Exception as e:
            self.logger.error(f"Error in monthly collection: {e}")
            raise

    def create_attestation_template(self):
        """Create initial attestation template"""
        attestation_file = os.path.join(self.data_dir, 'attestation.json')
        attestation = {
            "_type": "https://in-toto.io/Statement/v0.1",
            "subject": [{
                "name": "morphosource_data_complete.json",
                "digest": {
                    "sha256": ""
                }
            }],
            "predicateType": "https://in-toto.io/attestation/release/v0.1",
            "predicate": {
                "purl": f"pkg:github/{os.environ.get('GITHUB_REPOSITORY', '')}",
                "version": os.environ.get('GITHUB_SHA', ''),
                "metadata": {
                    "buildInvocationId": os.environ.get('GITHUB_RUN_ID', ''),
                    "completeness": {
                        "parameters": True,
                        "environment": True,
                        "materials": True
                    },
                    "stats": {
                        "total_records": str(len(self.all_records)),
                        "modified_records": str(len(self.modifications))
                    }
                }
            }
        }
        with open(attestation_file, 'w') as f:
            json.dump(attestation, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description='Monthly MorphoSource Data Collection')
    parser.add_argument('--output-dir', type=str, required=True,
                      help='Directory to store output files')
    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    collector = MonthlyMorphoSourceCollector(data_dir=args.output_dir)
    total_records = collector.run()
    
    print(f"Total records collected: {total_records}")
    print(f"Output directory: {args.output_dir}")
    sys.exit(0 if total_records > 0 else 1)

if __name__ == "__main__":
    main()
