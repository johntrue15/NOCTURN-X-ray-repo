import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
import os
import sys
import logging
import argparse

class DailyMorphoSourceExtractor:
    def __init__(self, base_url: str, data_dir: str = 'data'):
        self.base_url = base_url
        self.data_dir = data_dir
        self.setup_logging()
        self.setup_directories()
        self.complete_data_path = os.path.join(data_dir, 'morphosource_data_complete.json')
        self.latest_webpage_record = None  # Store for info file
        self.logger.info(f"Using data file: {self.complete_data_path}")

    def setup_logging(self):
        # Create logs in current data directory
        log_dir = os.path.dirname(self.data_dir)
        os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'daily_extractor.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_directories(self):
        os.makedirs(self.data_dir, exist_ok=True)

    def get_latest_webpage_record(self) -> dict:
        try:
            response = requests.get(self.base_url)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch page: {response.status_code}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            first_record = soup.find('div', class_='search-result-wrapper')
            if not first_record:
                raise Exception("Could not find any records on page")
            
            self.latest_webpage_record = self.parse_record(first_record)  # Store for info file
            return self.latest_webpage_record
            
        except Exception as e:
            self.logger.error(f"Error getting latest webpage record: {e}")
            raise

    def load_latest_stored_record(self) -> dict:
        try:
            abs_path = os.path.abspath(self.complete_data_path)
            self.logger.info(f"Looking for data file at: {abs_path}")
            
            # List directory contents for debugging
            dir_path = os.path.dirname(abs_path)
            self.logger.info(f"Contents of {dir_path}:")
            if os.path.exists(dir_path):
                for f in os.listdir(dir_path):
                    self.logger.info(f"  - {f}")
            
            if not os.path.exists(self.complete_data_path):
                self.logger.info("No existing data file found")
                return None
                
            with open(self.complete_data_path, 'r') as f:
                data = json.load(f)
                
            if not data:
                self.logger.info("No records in existing data")
                return None
                
            return data[0]  # First record is the most recent
            
        except Exception as e:
            self.logger.error(f"Error loading latest stored record: {e}")
            raise

    def parse_record(self, record_elem) -> dict:
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

    def records_match(self, record1: dict, record2: dict) -> bool:
        if not record1 or not record2:
            return False
            
        return (record1['id'] == record2['id'] and 
                record1['title'] == record2['title'] and 
                record1['url'] == record2['url'])

    def run(self) -> bool:
        try:
            latest_webpage_record = self.get_latest_webpage_record()
            self.logger.info(f"Latest webpage record ID: {latest_webpage_record['id']}")
            
            latest_stored_record = self.load_latest_stored_record()
            if latest_stored_record:
                self.logger.info(f"Latest stored record ID: {latest_stored_record['id']}")
            
            if self.records_match(latest_webpage_record, latest_stored_record):
                self.logger.info("No new records found - latest records match")
                return False
            else:
                self.logger.info("New records available - latest records differ")
                return True
                
        except Exception as e:
            self.logger.error(f"Error in daily check: {e}")
            raise

def create_no_changes_release_notes(output_dir: str, source_dir: str, logger):
    """Create release notes for when no changes are found"""
    release_notes_path = os.path.join(output_dir, 'release_notes.txt')
    try:
        with open(release_notes_path, 'w') as f:
            f.write("# Daily Check Report\n")
            f.write(f"Check Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("No new records found since last check.\n\n")
            f.write("## Previous Data\n")
            f.write(f"Last check: {source_dir}\n")
            
        logger.info(f"Created 'no changes' release notes at: {release_notes_path}")
        
    except Exception as e:
        logger.error(f"Error creating release notes: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description='Daily MorphoSource Check')
    parser.add_argument('--data-dir', type=str, required=True,
                      help='Directory containing latest data files')
    parser.add_argument('--output-dir', type=str, required=True,
                      help='Directory to store output files')
    parser.add_argument('--create-notes', action='store_true',
                      help='Create release notes for no changes case')
    args = parser.parse_args()
    
    try:
        if args.create_notes:
            # Setup logging for release notes creation
            logger = setup_logging(args.output_dir)
            create_no_changes_release_notes(args.output_dir, args.data_dir, logger)
            return 0
            
        # Normal daily check flow
        extractor = DailyMorphoSourceExtractor(base_url, data_dir=args.data_dir)
        has_new_records = extractor.run()
        
        # Create daily info regardless of result
        daily_info = {
            'check_date': datetime.now().isoformat(),
            'source_dir': args.data_dir,
            'has_new_records': has_new_records,
            'latest_record_id': extractor.latest_webpage_record['id'] if hasattr(extractor, 'latest_webpage_record') else None
        }
        
        # Save daily info
        os.makedirs(args.output_dir, exist_ok=True)
        with open(os.path.join(args.output_dir, 'daily_info.json'), 'w') as f:
            json.dump(daily_info, f, indent=2)
        
        if has_new_records:
            print("New records found - ready for collection")
            sys.exit(1)  # Signal that new records are available
        else:
            print("No new records found")
            sys.exit(0)  # Signal that no new records are needed
            
    except Exception as e:
        print(f"Error during execution: {e}")
        sys.exit(2)  # Signal error condition

if __name__ == "__main__":
    main()
