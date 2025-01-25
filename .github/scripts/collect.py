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
        from record_details import RecordDetailsManager
        
        if self.new_records:
            # Create record details manager
            details_manager = RecordDetailsManager(self.data_dir)
            
            # Save detailed and summary JSON files
            details_manager.save_record_details(self.new_records)
            details_manager.save_record_summary(self.new_records)
            
            # Create release notes
            details_manager.create_release_notes(self.new_records, self.release_notes_path)
        else:
                f.write(f"Added {len(self.new_records)} new record(s):\n\n")
                
                # Write summary table header
                f.write("| Title | ID | Link | Taxonomy | Element | Modality | Data Manager | Date |\n")
                f.write("|-------|----|----|----------|----------|-----------|--------------|------|\n")
                
                # Add each record to the table
                for record in self.new_records:
                    metadata = record['metadata']
                    title = record['title']
                    record_id = record['id']
                    url = record['url']
                    
                    # Extract metadata fields (with fallbacks to 'N/A')
                    taxonomy = metadata.get('Taxonomy', 'N/A')
                    element = metadata.get('Element or Part', 'N/A')
                    modality = metadata.get('Modality', 'N/A')
                    data_manager = metadata.get('Data Manager', 'N/A')
                    date = metadata.get('Date Uploaded', 'N/A')
                    
                    # Write table row
                    f.write(f"| {title} | {record_id} | [View]({url}) | {taxonomy} | {element} | {modality} | {data_manager} | {date} |\n")
                
                # Add detailed record information
                for record in self.new_records:
                    metadata = record['metadata']
                    f.write(f"\n### Details for Record {record['id']}\n\n")
                    f.write(f"**Title:** {record['title']}\n")
                    
                    # Write all available metadata fields
                    for key, value in metadata.items():
                        if value:  # Only write non-empty fields
                            f.write(f"**{key}:** {value}\n")
            else:
                f.write("No new records found")

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
