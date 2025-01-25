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
        """Load existing records and create ID-based lookup"""
        if os.path.exists(self.complete_data_path):
            with open(self.complete_data_path, 'r') as f:
                existing_records = json.load(f)
                self.previous_records = {r['id']: r for r in existing_records}
                self.logger.info(f"Loaded {len(existing_records)} existing records")
                return existing_records
        return []

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

    def collect_all_records(self):
        """Collect all records from MorphoSource"""
        page = 1
        total_pages = None
        
        while True:
            try:
                url = f"{self.base_url}&page={page}"
                self.logger.info(f"Fetching page {page}")
                
                response = requests.get(url)
                if response.status_code != 200:
                    self.logger.error(f"Failed to fetch page {page}: {response.status_code}")
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                records = soup.find_all('div', class_='search-result-wrapper')
                
                if not records:
                    break
                
                for record_elem in records:
                    record = self.parse_record(record_elem)
                    self.check_for_modifications(record)
                    self.all_records.append(record)
                
                # Basic progress logging
                if page % 10 == 0:
                    self.logger.info(f"Collected {len(self.all_records)} records so far")
                
                page += 1
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                self.logger.error(f"Error on page {page}: {e}")
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
