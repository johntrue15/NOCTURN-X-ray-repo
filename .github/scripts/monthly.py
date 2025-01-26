import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
import os
import sys
import logging
import argparse

class MonthlyMorphoSourceCollector:
    def __init__(self, base_url: str, data_dir: str = 'data'):
        """Initialize collector with base URL and output directory."""
        self.base_url = base_url
        self.data_dir = data_dir
        
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

    # ... [rest of the class methods remain the same until save_stats] ...

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

def main():
    parser = argparse.ArgumentParser(description='Monthly MorphoSource Data Collection')
    parser.add_argument('--output-dir', type=str, required=True,
                      help='Directory to store output files')
    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)

    base_url = "https://www.morphosource.org/catalog/media?locale=en&per_page=100&q=X-Ray+Computed+Tomography&search_field=all_fields&sort=system_create_dtsi+desc"
    
    collector = MonthlyMorphoSourceCollector(base_url, data_dir=args.output_dir)
    total_records = collector.run()
    
    print(f"Total records collected: {total_records}")
    print(f"Output directory: {args.output_dir}")
    sys.exit(0 if total_records > 0 else 1)

if __name__ == "__main__":
    main()
