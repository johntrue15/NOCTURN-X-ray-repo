import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
import os
import sys
import logging

class RecordCollector:
    def __init__(self, base_url: str, data_dir: str = 'data'):
        self.base_url = base_url
        self.data_dir = data_dir
        self.setup_logging()
        self.complete_data_path = os.path.join(data_dir, 'morphosource_data_complete.json')
        self.release_notes_path = os.path.join(data_dir, 'release_notes.txt')
        self.new_records_path = os.path.join(data_dir, 'new_records_details.json')
        self.new_records = []

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join('data', 'collector.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_existing_data(self):
        with open(self.complete_data_path, 'r') as f:
            return json.load(f)

    def parse_record(self, record_elem):
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

    def collect_new_records(self):
        existing_data = self.load_existing_data()
        existing_ids = {record['id'] for record in existing_data}
        page = 1
        
        while True:
            try:
                url = f"{self.base_url}&page={page}"
                self.logger.info(f"Fetching page {page}")
                
                response = requests.get(url)
                if response.status_code != 200:
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                records = soup.find_all('div', class_='search-result-wrapper')
                
                if not records:
                    break
                
                found_existing = False
                for record_elem in records:
                    record = self.parse_record(record_elem)
                    if record['id'] in existing_ids:
                        found_existing = True
                        break
                    self.new_records.append(record)
                
                if found_existing:
                    break
                
                page += 1
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                self.logger.error(f"Error on page {page}: {e}")
                break

    def create_release_notes(self):
        """Create release notes and save record details"""
        if self.new_records:
            # Create release notes with table
            with open(self.release_notes_path, 'w') as f:
                f.write(f"Added {len(self.new_records)} new record(s):\n\n")
                
                # Write summary table
                f.write("| Title | Object ID | Taxonomy | Element | Data Manager | Status | Link |\n")
                f.write("|-------|-----------|----------|----------|--------------|--------|------|\n")
                
                for record in self.new_records:
                    metadata = record['metadata']
                    f.write(
                        f"| {record['title']} | {metadata.get('Object', 'N/A')} | "
                        f"{metadata.get('Taxonomy', 'N/A')} | {metadata.get('Element or Part', 'N/A')} | "
                        f"{metadata.get('Data Manager', 'N/A')} | "
                        f"{metadata.get('Publication Status', 'N/A')} | "
                        f"[View]({record['url']}) |\n"
                    )
            
            # Create JSON file with just the new records
            with open(self.new_records_path, 'w') as f:
                json.dump(self.new_records, f, indent=2)
        else:
            # Create empty release notes if no new records
            with open(self.release_notes_path, 'w') as f:
                f.write("No new records found")
            # Create empty JSON for new records
            with open(self.new_records_path, 'w') as f:
                json.dump([], f, indent=2)

    def save_records(self):
        if not self.new_records:
            self.create_release_notes()
            return 0
            
        existing_data = self.load_existing_data()
        updated_data = self.new_records + existing_data
        
        with open(self.complete_data_path, 'w') as f:
            json.dump(updated_data, f, indent=2)
            
        self.create_release_notes()
        return len(self.new_records)

    def run(self):
        try:
            self.collect_new_records()
            new_count = self.save_records()
            self.logger.info(f"Added {new_count} new records")
            return new_count
        except Exception as e:
            self.logger.error(f"Error in collection: {e}")
            raise

def main():
    base_url = "https://www.morphosource.org/catalog/media?locale=en&per_page=100&q=X-Ray+Computed+Tomography&search_field=all_fields&sort=system_create_dtsi+desc"
    
    collector = RecordCollector(base_url)
    new_count = collector.run()
    
    print(f"Records added: {new_count}")
    sys.exit(0 if new_count >= 0 else 1)

if __name__ == "__main__":
    main()
