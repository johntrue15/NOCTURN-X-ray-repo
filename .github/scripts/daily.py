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

    def get_all_records(self, latest_stored_id: str = None) -> list:
        """Get all records from the webpage until we hit the latest stored record"""
        try:
            records = []
            page = 1
            found_latest = False
            
            while True:
                url = f"{self.base_url}&page={page}"
                self.logger.info(f"Fetching page {page}")
                
                response = requests.get(url)
                if response.status_code != 200:
                    raise Exception(f"Failed to fetch page {page}: {response.status_code}")
                
                soup = BeautifulSoup(response.text, 'html.parser')
                record_elements = soup.find_all('div', class_='search-result-wrapper')
                
                if not record_elements:
                    break
                    
                for elem in record_elements:
                    record = self.parse_record(elem)
                    records.append(record)
                    self.logger.info(f"Found record {record['id']} - Total records: {len(records)}")
                    
                    # Stop if we hit the latest stored record
                    if latest_stored_id and record['id'] == latest_stored_id:
                        self.logger.info(f"Found latest stored record {latest_stored_id} - stopping fetch")
                        found_latest = True
                        break
                
                if found_latest:
                    break
                    
                page += 1
                time.sleep(1)  # Be nice to the server
                
            self.logger.info(f"Completed fetch - Found {len(records)} new records")
            return records
            
        except Exception as e:
            self.logger.error(f"Error getting records: {e}")
            raise

    def load_stored_records(self) -> list:
        """Load all records from the most recent data file"""
        try:
            # First try to find the most recent data file
            parent_dir = Path(self.data_dir).parent
            self.logger.info(f"Looking for previous data in: {parent_dir}")
            
            # Find all timestamp directories and sort by name (which is the timestamp)
            timestamp_dirs = sorted(
                [d for d in parent_dir.iterdir() 
                 if d.is_dir() and d.name[0].isdigit()],
                reverse=True
            )
            
            # Look for data files in each directory until we find one
            for dir in timestamp_dirs:
                if dir == Path(self.data_dir):  # Skip current directory
                    continue
                    
                for filename in ['morphosource_data_complete.json', 'updated_morphosource_data.json']:
                    file_path = dir / filename
                    if file_path.exists():
                        self.logger.info(f"Loading previous data from: {file_path}")
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            if data:
                                self.logger.info(f"Loaded {len(data)} records from previous data file")
                                return data
                                
            self.logger.info("No previous data file found")
            return []
            
        except Exception as e:
            self.logger.error(f"Error loading stored records: {e}")
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

    def run(self):
        """Run the daily check and save results"""
        try:
            # Load stored records first to get latest ID
            stored_records = self.load_stored_records()
            latest_stored = stored_records[0] if stored_records else None
            latest_stored_id = latest_stored['id'] if latest_stored else None
            
            if latest_stored:
                self.logger.info(f"Latest stored record ID: {latest_stored['id']}")
                self.logger.info(f"Previous record count: {len(stored_records)}")
            else:
                self.logger.info("No stored records found")
            
            # Get new records up to latest stored
            new_records = self.get_all_records(latest_stored_id)
            if not new_records:
                self.logger.error("No records found on webpage")
                return 0
            
            self.latest_webpage_record = new_records[0]  # First is most recent
            self.logger.info(f"Latest webpage record ID: {self.latest_webpage_record['id']}")
            
            # Compare records
            if not latest_stored or self.latest_webpage_record['id'] != latest_stored['id']:
                self.logger.info("New records available - latest records differ")
                
                # Combine new records with stored records
                existing_ids = set(r['id'] for r in stored_records)
                combined_records = new_records[:]  # Start with new records
                
                # Add old records that aren't in new records
                for record in stored_records:
                    if record['id'] not in set(r['id'] for r in new_records):
                        combined_records.append(record)
                
                # Sort combined records by ID to maintain order
                combined_records.sort(key=lambda x: x['id'], reverse=True)
                
                self.logger.info(f"New records: {len(new_records)}")
                self.logger.info(f"Previous records: {len(stored_records)}")
                self.logger.info(f"Combined records: {len(combined_records)}")
                
                # Save combined records
                output_file = os.path.join(self.data_dir, 'morphosource_data_complete.json')
                with open(output_file, 'w') as f:
                    json.dump(combined_records, f, indent=2)
                self.logger.info(f"Saved {len(combined_records)} records to: {output_file}")
                
                # Create release notes
                release_notes_path = os.path.join(self.data_dir, 'release_notes.txt')
                with open(release_notes_path, 'w') as f:
                    f.write("# Daily Check Report\n\n")
                    f.write("## Record Changes\n")
                    f.write(f"Latest Record ID: {self.latest_webpage_record['id']}\n")
                    if latest_stored:
                        f.write(f"Previous Record ID: {latest_stored['id']}\n")
                    f.write(f"\nTotal Records: {len(combined_records)}\n")
                    f.write(f"Previous Records: {len(stored_records)}\n")
                    f.write(f"New Records Added: {len(new_records)}\n")
                    
                    if new_records:
                        f.write("\n### New Record IDs:\n")
                        for record in new_records[:10]:  # Show first 10
                            f.write(f"- {record['id']}: {record['title']}\n")
                        if len(new_records) > 10:
                            f.write(f"... and {len(new_records) - 10} more\n")
                
                self.logger.info(f"Created detailed release notes at: {release_notes_path}")
                return 1
            else:
                self.logger.info("No new records found")
                return 0
                
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

def create_new_records_release_notes(output_dir: str, daily_info: dict, logger: logging.Logger):
    """Create release notes for new records case"""
    try:
        release_notes_path = os.path.join(output_dir, 'release_notes.txt')
        with open(release_notes_path, 'w') as f:
            f.write("# Daily Check Report\n")
            f.write(f"Check Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Summary\n")
            f.write("New records found - collection in progress\n\n")
            
            f.write("## Latest Record\n")
            f.write(f"Record ID: {daily_info['latest_record_id']}\n\n")
            
            # Get the previous data directory from stored records
            previous_dir = None
            parent_dir = Path(output_dir).parent
            timestamp_dirs = sorted(
                [d for d in parent_dir.iterdir() 
                 if d.is_dir() and d.name[0].isdigit()],
                reverse=True
            )
            
            for dir in timestamp_dirs:
                if dir != Path(output_dir):  # Skip current directory
                    if any(f.name in ['morphosource_data_complete.json', 'updated_morphosource_data.json'] 
                          for f in dir.iterdir()):
                        previous_dir = dir
                        break
            
            f.write("## Data Files\n")
            f.write(f"Current data: {output_dir}/morphosource_data_complete.json\n")
            if previous_dir:
                f.write(f"Previous data: {previous_dir}/morphosource_data_complete.json\n")
            else:
                f.write("Previous data: No previous data found\n")
            f.write("\n")
            
            # Load record counts
            current_count = 0
            previous_count = 0
            
            current_file = Path(output_dir) / 'morphosource_data_complete.json'
            if current_file.exists():
                with open(current_file) as cf:
                    current_count = len(json.load(cf))
            
            if previous_dir:
                previous_file = previous_dir / 'morphosource_data_complete.json'
                if previous_file.exists():
                    with open(previous_file) as pf:
                        previous_count = len(json.load(pf))
            
            f.write("## Record Counts\n")
            f.write(f"Previous records: {previous_count}\n")
            f.write(f"Current records: {current_count}\n")
            f.write(f"Difference: {current_count - previous_count}\n\n")
            
        logger.info(f"Created release notes at: {release_notes_path}")
        
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
        result = extractor.run()
        
        # Create daily info regardless of result
        daily_info = {
            'check_date': datetime.now().isoformat(),
            'source_dir': args.data_dir,
            'has_new_records': result == 1,
            'latest_record_id': extractor.latest_webpage_record['id'] if extractor.latest_webpage_record else None
        }
        
        # Save daily info and create appropriate release notes
        with open(os.path.join(args.output_dir, 'daily_info.json'), 'w') as f:
            json.dump(daily_info, f, indent=2)
            
        if result == 1:
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
