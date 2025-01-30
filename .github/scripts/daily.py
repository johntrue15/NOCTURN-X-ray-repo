import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
import os
import sys
import logging
import argparse
from pathlib import Path

def setup_logging(log_dir):
    """Configure logging for release notes creation"""
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'daily_extractor.log')),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

class DailyMorphoSourceExtractor:
    def __init__(self, base_url: str, data_dir: str = 'data'):
        self.base_url = base_url
        self.data_dir = data_dir
        self.setup_logging()
        self.setup_directories()
        self.latest_webpage_record = None
        self.logger.info(f"Using data directory: {self.data_dir}")

    def setup_logging(self):
        self.logger = setup_logging(self.data_dir)

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
        """Load latest stored record"""
        try:
            # First try morphosource_data_complete.json in current directory
            current_file = os.path.join(self.data_dir, 'morphosource_data_complete.json')
            if os.path.exists(current_file):
                self.logger.info(f"Using current directory file: {current_file}")
                with open(current_file, 'r') as f:
                    data = json.load(f)
                    if data:
                        return data[0]  # First record is the most recent
                
            # If not found, look in parent directory
            parent_dir = str(Path(self.data_dir).parent)
            self.logger.info(f"Looking in parent directory: {parent_dir}")
            
            # List all timestamp directories in reverse order
            timestamp_dirs = sorted(
                [d for d in Path(parent_dir).iterdir() 
                 if d.is_dir() and d.name[0].isdigit()],
                reverse=True
            )
            
            for dir in timestamp_dirs:
                for filename in ['morphosource_data_complete.json', 'updated_morphosource_data.json']:
                    file_path = dir / filename
                    if file_path.exists():
                        self.logger.info(f"Using file from previous run: {file_path}")
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            if data:
                                return data[0]
            
            self.logger.info("No existing data files found")
            return None
            
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
    try:
        # Create daily info
        daily_info = {
            'check_date': datetime.now().isoformat(),
            'source_dir': source_dir,
            'has_new_records': False,
            'latest_record_id': None,
            'current_data_file': os.path.join(output_dir, 'morphosource_data_complete.json'),
            'previous_data_file': os.path.join(source_dir, 'morphosource_data_complete.json')
        }
        
        # Save daily info
        with open(os.path.join(output_dir, 'daily_info.json'), 'w') as f:
            json.dump(daily_info, f, indent=2)
            
        # Create release notes
        release_notes_path = os.path.join(output_dir, 'release_notes.txt')
        with open(release_notes_path, 'w') as f:
            f.write("# Daily Check Report\n")
            f.write(f"Check Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("No new records found since last check.\n\n")
            f.write("## Data Files\n")
            f.write(f"Current data: {daily_info['current_data_file']}\n")
            f.write(f"Previous data: {daily_info['previous_data_file']}\n")
            
        logger.info(f"Created 'no changes' release notes at: {release_notes_path}")
        
    except Exception as e:
        logger.error(f"Error creating release notes: {e}")
        raise

def create_new_records_release_notes(output_dir: str, daily_info: dict, logger):
    """Create release notes for when new records are found"""
    release_notes_path = os.path.join(output_dir, 'release_notes.txt')
    try:
        with open(release_notes_path, 'w') as f:
            f.write("# Daily Check Report\n")
            f.write(f"Check Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("## Summary\n")
            f.write("New records found - collection in progress\n\n")
            f.write("## Latest Record\n")
            f.write(f"Record ID: {daily_info['latest_record_id']}\n")
            f.write("\n## Data Files\n")
            f.write(f"Current data: {os.path.join(output_dir, 'morphosource_data_complete.json')}\n")
            f.write(f"Previous data: {os.path.join(daily_info['source_dir'], 'morphosource_data_complete.json')}\n")
            f.write("\n## Attestations\n")
            f.write("<!-- ATTESTATION_URLS -->\n")
            
        logger.info(f"Created 'new records' release notes at: {release_notes_path}")
        
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
        # Validate directories
        if not args.data_dir:
            raise ValueError("data-dir cannot be empty")
        if not args.output_dir:
            raise ValueError("output-dir cannot be empty")
            
        # Create output directory
        os.makedirs(args.output_dir, exist_ok=True)
        logger = setup_logging(args.output_dir)
        
        logger.info(f"Data directory: {args.data_dir}")
        logger.info(f"Output directory: {args.output_dir}")
        
        if args.create_notes:
            logger.info("Creating no-changes release notes")
            create_no_changes_release_notes(args.output_dir, args.data_dir, logger)
            return 0
            
        # Normal daily check flow
        base_url = "https://www.morphosource.org/catalog/media?locale=en&per_page=100&q=X-Ray+Computed+Tomography&search_field=all_fields&sort=system_create_dtsi+desc"
        extractor = DailyMorphoSourceExtractor(base_url, data_dir=args.data_dir)
        has_new_records = extractor.run()
        
        # Create daily info regardless of result
        daily_info = {
            'check_date': datetime.now().isoformat(),
            'source_dir': args.data_dir,
            'has_new_records': has_new_records,
            'latest_record_id': extractor.latest_webpage_record['id'] if hasattr(extractor, 'latest_webpage_record') else None
        }
        
        # Save daily info and create appropriate release notes
        with open(os.path.join(args.output_dir, 'daily_info.json'), 'w') as f:
            json.dump(daily_info, f, indent=2)
            
        if has_new_records:
            create_new_records_release_notes(args.output_dir, daily_info, logger)
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
