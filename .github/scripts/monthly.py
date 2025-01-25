import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
import os
import sys
import logging

class MonthlyMorphoSourceCollector:
    def __init__(self, base_url: str, data_dir: str = 'data'):
        self.base_url = base_url
        self.data_dir = data_dir
        self.setup_logging()
        self.complete_data_path = os.path.join(data_dir, 'morphosource_data_complete.json')
        self.release_notes_path = os.path.join(data_dir, 'monthly_release_notes.txt')
        self.all_records = []
        self.previous_records = {}
        self.modifications = []

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join('data', 'monthly_collector.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_existing_data(self):
        """Load and backup existing records and create ID-based lookup"""
        if os.path.exists(self.complete_data_path):
            # Create backup
            backup_path = f"{self.complete_data_path}.backup"
            with open(self.complete_data_path, 'r') as src, open(backup_path, 'w') as dst:
                data = json.load(src)
                json.dump(data, dst, indent=2)
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
        analysis_path = os.path.join(self.data_dir, 'monthly_analysis.json')
        with open(analysis_path, 'w') as f:
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
                
            self.create_release_notes(analysis)
            
            return len(self.all_records)
            
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")
            # Restore from backup if it exists
            backup_path = f"{self.complete_data_path}.backup"
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

    def parse_record(self, record_elem):
        """Parse a single record from the page"""
        try:
            title_elem = record_elem.find('div', class_='search-results-title-row')
            title = title_elem.get_text(strip=True) if title_elem else ""
            
            link_elem = record_elem.find('a', href=True)
            record_url = f"https://www.morphosource.org{link_elem['href']}" if link_elem else ""
            record_id = record_url.split('/')[-1].split('?')[0] if record_url else ""
            
            metadata = {}
            fields = record_elem.find_all('div', class_='index-field-item')
            for field in fields:
                field_text = field.get_text(strip=True)
                if ':' in field_text:
                    key, value = field_text.split(':', 1)
                    metadata[key.strip()] = value.strip()
            
            return {
                'title': title,
                'url': record_url,
                'id': record_id,
                'metadata': metadata,
                'scraped_date': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error parsing record: {e}")
            raise

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
        
        stats_path = os.path.join(self.data_dir, 'monthly_stats.json')
        with open(stats_path, 'w') as f:
            json.dump(stats, f, indent=2)

    def collect_all_records(self):
        """Collect all records from MorphoSource"""
        self.last_page_processed = 0
        self.last_successful_page = 0
        self.last_successful_id = None
        self.error_count = 0
        page = 1
        
        while True:
            try:
                url = f"{self.base_url}&page={page}"
                self.logger.info(f"Processing page {page}")
                
                response = requests.get(url)
                if response.status_code != 200:
                    self.error_count += 1
                    self.logger.error(f"Failed to fetch page {page}: {response.status_code}")
                    if self.error_count >= 5:  # Max consecutive errors
                        break
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                records = soup.find_all('div', class_='search-result-wrapper')
                
                if not records:
                    break
                
                page_records = []
                for record_elem in records:
                    try:
                        record = self.parse_record(record_elem)
                        self.check_for_modifications(record)
                        page_records.append(record)
                        self.last_successful_id = record['id']
                    except Exception as e:
                        self.error_count += 1
                        self.logger.error(f"Error parsing record on page {page}: {e}")
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
                
                page += 1
                self.last_page_processed = page
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                self.error_count += 1
                self.logger.error(f"Error processing page {page}: {e}")
                if self.error_count >= 5:  # Max consecutive errors
                    break

    def create_release_notes(self):
        """Create detailed release notes"""
        with open(self.release_notes_path, 'w') as f:
            f.write(f"# Monthly MorphoSource Collection Report\n\n")
            f.write(f"Collection Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary statistics
            f.write("## Summary\n")
            f.write(f"- Total Records: {len(self.all_records)}\n")
            f.write(f"- Modified Records: {len(self.modifications)}\n")
            f.write(f"- New Records: {len(self.all_records) - len(self.previous_records)}\n\n")
            
            # Modified Records Table
            if self.modifications:
                f.write("## Modified Records\n\n")
                f.write("| ID | Title | Object ID | Status | Link |\n")
                f.write("|----|----|----|----|----|\n")
                for mod in self.modifications:
                    new_record = mod['new']
                    f.write(
                        f"| {new_record['id']} | {new_record['title']} | "
                        f"{new_record['metadata'].get('Object', 'N/A')} | "
                        f"{new_record['metadata'].get('Publication Status', 'N/A')} | "
                        f"[View]({new_record['url']}) |\n"
                    )

    def save_data(self):
        """Save collected data"""
        try:
            # Save complete dataset
            with open(self.complete_data_path, 'w') as f:
                json.dump(self.all_records, f, indent=2)
                
            self.create_release_notes()
            
            return len(self.all_records)
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")
            raise

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

def main():
    base_url = "https://www.morphosource.org/catalog/media?locale=en&per_page=100&q=X-Ray+Computed+Tomography&search_field=all_fields&sort=system_create_dtsi+desc"
    
    collector = MonthlyMorphoSourceCollector(base_url)
    total_records = collector.run()
    
    print(f"Total records collected: {total_records}")
    sys.exit(0 if total_records > 0 else 1)

if __name__ == "__main__":
    main()
