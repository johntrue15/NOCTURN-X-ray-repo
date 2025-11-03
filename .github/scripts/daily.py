import json
from datetime import datetime
import time
import os
import sys
import logging
import argparse
from pathlib import Path
from morphosource_api import MorphoSourceAPI, MorphoSourceAPIError, MorphoSourceTemporarilyUnavailable

# Try to import pandas and pyarrow for parquet support
try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    PARQUET_SUPPORT = True
except ImportError:
    PARQUET_SUPPORT = False
    logging.warning("pandas/pyarrow not available - parquet output disabled")

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
    def __init__(self, data_dir: str = 'data'):
        self.data_dir = data_dir
        self.api = MorphoSourceAPI()
        self.setup_logging()
        self.setup_directories()
        self.latest_webpage_record = None
        self.logger.info(f"Using data directory: {self.data_dir}")

    def setup_logging(self):
        self.logger = setup_logging(self.data_dir)

    def setup_directories(self):
        os.makedirs(self.data_dir, exist_ok=True)

    def get_all_records(self, latest_stored_id: str = None, fetch_all: bool = False) -> list:
        """Get all records from the API
        
        Args:
            latest_stored_id: If provided and fetch_all is False, stops at this ID
            fetch_all: If True, fetches all records from all pages (for daily parquet export)
        
        Returns:
            List of all fetched records
        """
        try:
            records = []
            page = 1
            found_latest = False
            per_page = 100
            error_count = 0
            max_errors = 5
            
            while True:
                self.logger.info(f"Fetching page {page} via API")
                
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
                        self.logger.info(f"No more records found on page {page}")
                        break
                    
                    # Process records before incrementing page counter
                    page_had_error = False
                    
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
                            
                            records.append(record)
                            
                            # Stop if we hit the latest stored record (only if not fetching all)
                            if not fetch_all and latest_stored_id and record['id'] == latest_stored_id:
                                self.logger.info(f"Found latest stored record {latest_stored_id} - stopping fetch")
                                found_latest = True
                                break
                        except (KeyError, ValueError, TypeError) as e:
                            # Catch specific exceptions from record normalization
                            self.logger.error(f"Error normalizing record (KeyError/ValueError/TypeError): {e}")
                            error_count += 1
                            if error_count >= max_errors:
                                raise
                            continue
                        except Exception as e:
                            # Log unexpected exceptions with full details
                            self.logger.error(f"Unexpected error normalizing record: {type(e).__name__}: {e}")
                            error_count += 1
                            if error_count >= max_errors:
                                raise
                            continue
                    
                    # Reset error count on successful page processing
                    error_count = 0
                    
                    # Log progress every 5 pages
                    if page % 5 == 0:
                        self.logger.info(f"Progress - Page: {page}, Total records: {len(records)}")
                    
                    if found_latest and not fetch_all:
                        break
                    
                    # Check if we've reached the last page
                    if page >= result['meta']['total_pages']:
                        self.logger.info(f"Reached last page ({page} of {result['meta']['total_pages']})")
                        break
                    
                    # Only increment page after successful processing
                    page += 1
                    time.sleep(2)  # Rate limiting
                    
                except MorphoSourceAPIError as e:
                    error_count += 1
                    self.logger.error(f"API error on page {page}: {e} (error {error_count}/{max_errors})")
                    if error_count >= max_errors:
                        raise
                    time.sleep(5)  # Wait before retry
                    # Don't increment page - will retry the same page
                    continue
                
            self.logger.info(f"Completed fetch - Found {len(records)} records from {page} pages")
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

    # parse_record method is no longer needed as the API client handles normalization

    def records_match(self, record1: dict, record2: dict) -> bool:
        if not record1 or not record2:
            return False
            
        return (record1['id'] == record2['id'] and 
                record1['title'] == record2['title'] and 
                record1['url'] == record2['url'])
    
    def save_to_parquet(self, records: list, filename: str = 'morphosource_data_complete.parquet'):
        """Save records to parquet format
        
        Args:
            records: List of record dictionaries
            filename: Output filename (default: morphosource_data_complete.parquet)
        """
        if not PARQUET_SUPPORT:
            self.logger.warning("Parquet support not available - skipping parquet save")
            return
        
        if not records:
            self.logger.warning("No records to save to parquet")
            return
        
        try:
            output_path = os.path.join(self.data_dir, filename)
            
            # Flatten the records for parquet format
            # Metadata is a dict, so we'll convert it to JSON string or flatten it
            flattened_records = []
            for record in records:
                flat_record = {
                    'id': record['id'],
                    'title': record['title'],
                    'url': record['url'],
                    'scraped_date': record['scraped_date']
                }
                
                # Add metadata fields as separate columns
                if 'metadata' in record and isinstance(record['metadata'], dict):
                    seen_col_names = set()
                    for key, value in record['metadata'].items():
                        # Create valid column names (replace spaces with underscores)
                        base_col_name = f"metadata_{key.replace(' ', '_').replace('/', '_')}"
                        col_name = base_col_name
                        
                        # Ensure uniqueness by adding suffix if needed
                        counter = 1
                        while col_name in seen_col_names:
                            col_name = f"{base_col_name}_{counter}"
                            counter += 1
                        
                        seen_col_names.add(col_name)
                        flat_record[col_name] = str(value) if value is not None else ''
                
                flattened_records.append(flat_record)
            
            # Create DataFrame
            df = pd.DataFrame(flattened_records)
            
            # Save to parquet
            df.to_parquet(output_path, engine='pyarrow', compression='snappy', index=False)
            
            self.logger.info(f"Saved {len(records)} records to parquet: {output_path}")
            self.logger.info(f"Parquet file size: {os.path.getsize(output_path) / 1024 / 1024:.2f} MB")
            
        except Exception as e:
            self.logger.error(f"Error saving to parquet: {e}")
            # Don't raise - parquet is optional, JSON is primary format

    def run(self, fetch_all: bool = False):
        """Run the daily check and save results
        
        Args:
            fetch_all: If True, fetches all records from all pages and saves to parquet
        """
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
            
            # Get records based on mode
            if fetch_all:
                self.logger.info("=== FULL FETCH MODE: Collecting all records from all pages ===")
                all_records = self.get_all_records(latest_stored_id=None, fetch_all=True)
                if not all_records:
                    self.logger.error("No records found during full fetch")
                    return 0
                
                self.latest_webpage_record = all_records[0]  # First is most recent
                self.logger.info(f"Latest webpage record ID: {self.latest_webpage_record['id']}")
                self.logger.info(f"Total records fetched: {len(all_records)}")
                
                # Save to JSON
                output_file = os.path.join(self.data_dir, 'morphosource_data_complete.json')
                with open(output_file, 'w') as f:
                    json.dump(all_records, f, indent=2)
                self.logger.info(f"Saved {len(all_records)} records to JSON: {output_file}")
                
                # Save to Parquet
                self.save_to_parquet(all_records)
                
                # Create release notes
                release_notes_path = os.path.join(self.data_dir, 'release_notes.txt')
                with open(release_notes_path, 'w') as f:
                    f.write("# Daily Full Collection Report\n\n")
                    f.write(f"Collection Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write("## Collection Mode\n")
                    f.write("Full pagination - collected all records from MorphoSource\n\n")
                    f.write("## Record Statistics\n")
                    f.write(f"Total Records: {len(all_records)}\n")
                    if latest_stored:
                        f.write(f"Previous Collection: {len(stored_records)} records\n")
                        f.write(f"Change: {len(all_records) - len(stored_records):+d} records\n")
                    f.write(f"\nLatest Record ID: {self.latest_webpage_record['id']}\n")
                    f.write(f"Latest Record Title: {self.latest_webpage_record['title']}\n\n")
                    
                    # Add info about data formats
                    f.write("## Data Formats\n")
                    f.write("- JSON: morphosource_data_complete.json\n")
                    if PARQUET_SUPPORT:
                        f.write("- Parquet: morphosource_data_complete.parquet\n")
                
                self.logger.info(f"Created release notes at: {release_notes_path}")
                return 1
                
            else:
                # Incremental mode - only fetch new records
                self.logger.info("=== INCREMENTAL MODE: Fetching only new records ===")
                new_records = self.get_all_records(latest_stored_id, fetch_all=False)
                if not new_records:
                    self.logger.error("No records found during incremental fetch")
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
                    
                    # Copy over the previous data file
                    if stored_records:
                        output_file = os.path.join(self.data_dir, 'morphosource_data_complete.json')
                        with open(output_file, 'w') as f:
                            json.dump(stored_records, f, indent=2)
                        self.logger.info(f"Copied {len(stored_records)} previous records to: {output_file}")
                        
                        # Create release notes for no changes
                        release_notes_path = os.path.join(self.data_dir, 'release_notes.txt')
                        with open(release_notes_path, 'w') as f:
                            f.write("# Daily Check Report\n\n")
                            f.write(f"Check Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                            f.write("## Status\n")
                            f.write("No new records found - using previous dataset\n\n")
                            f.write("## Latest Record\n")
                            f.write(f"Record ID: {latest_stored['id']}\n\n")
                            f.write("## Record Counts\n")
                            f.write(f"Total Records: {len(stored_records)}\n")
                        
                        self.logger.info(f"Created 'no changes' release notes at: {release_notes_path}")
                    
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
    parser.add_argument('--fetch-all', action='store_true',
                      help='Fetch all records from all pages and save to parquet (daily full collection)')
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
        logger.info(f"Fetch all mode: {args.fetch_all}")
        
        if args.create_notes:
            logger.info("Creating no-changes release notes")
            create_no_changes_release_notes(args.output_dir, args.data_dir, logger)
            return 0
            
        # Normal daily check flow
        extractor = DailyMorphoSourceExtractor(data_dir=args.data_dir)
        result = extractor.run(fetch_all=args.fetch_all)
        
        # Create daily info regardless of result
        daily_info = {
            'check_date': datetime.now().isoformat(),
            'source_dir': args.data_dir,
            'has_new_records': result == 1,
            'latest_record_id': extractor.latest_webpage_record['id'] if extractor.latest_webpage_record else None,
            'fetch_all_mode': args.fetch_all,
            'parquet_support': PARQUET_SUPPORT
        }
        
        # Save daily info
        with open(os.path.join(args.output_dir, 'daily_info.json'), 'w') as f:
            json.dump(daily_info, f, indent=2)
        
        if result == 1:
            if args.fetch_all:
                print(f"Full collection complete - all records saved to JSON and parquet")
            else:
                print("New records found - ready for collection")
            sys.exit(1)  # Signal that new records are available
        else:
            print("No new records found - using previous dataset")
            sys.exit(0)  # Signal that no new records are needed
            
    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)  # Signal error condition

if __name__ == "__main__":
    main()
