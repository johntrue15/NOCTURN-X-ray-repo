import os
import json
import logging
import argparse
import requests
from bs4 import BeautifulSoup
import pandas as pd
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
import time

def setup_logging(log_file):
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def get_latest_data_file():
    """Find the most recent morphosource_data_complete.json file"""
    data_dir = Path('data')
    timestamp_dirs = sorted([d for d in data_dir.iterdir() if d.is_dir() and d.name[0].isdigit()], reverse=True)
    
    for dir in timestamp_dirs:
        data_file = dir / 'morphosource_data_complete.json'
        if data_file.exists():
            return data_file
            
    raise FileNotFoundError("No morphosource_data_complete.json found")

def extract_page_data(soup):
    """Extract structured data from MorphoSource page"""
    data = {}
    
    # Extract basic information
    title_elem = soup.find('h1')
    data['title'] = title_elem.text.strip() if title_elem else None
    
    # Extract all detail sections
    sections = soup.find_all('div', class_='detail-section')
    for section in sections:
        section_title = section.find('h2')
        if not section_title:
            continue
            
        section_name = section_title.text.strip()
        fields = section.find_all('div', class_='field-item')
        
        section_data = {}
        for field in fields:
            label = field.find('div', class_='field-label')
            value = field.find('div', class_='field-value')
            if label and value:
                section_data[label.text.strip()] = value.text.strip()
                
        data[section_name] = section_data
        
    return data

def process_url_batch(urls, output_dir, logger):
    """Process a batch of URLs and save to parquet"""
    all_data = []
    
    for url in tqdm(urls, desc="Processing URLs"):
        try:
            logger.info(f"Processing URL: {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            page_data = extract_page_data(soup)
            
            # Add metadata
            page_data['url'] = url
            page_data['processed_at'] = datetime.now().isoformat()
            
            all_data.append(page_data)
            
            # Be nice to the server
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
            continue
    
    if all_data:
        # Convert to DataFrame
        df = pd.json_normalize(all_data)
        
        # Save to parquet
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        parquet_file = output_dir / f'morphosource_data_{timestamp}.parquet'
        df.to_parquet(parquet_file, index=False)
        
        logger.info(f"Saved {len(all_data)} records to {parquet_file}")
        return len(all_data)
    
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--log-file', required=True)
    args = parser.parse_args()
    
    # Setup
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logging(args.log_file)
    
    try:
        # Get latest data file
        data_file = get_latest_data_file()
        logger.info(f"Using data file: {data_file}")
        
        # Load URLs
        with open(data_file) as f:
            data = json.load(f)
            
        urls = [record['url'] for record in data if record.get('url')]
        logger.info(f"Found {len(urls)} URLs to process")
        
        # Process in batches
        for i in range(0, len(urls), args.batch_size):
            batch = urls[i:i + args.batch_size]
            logger.info(f"Processing batch {i//args.batch_size + 1}")
            processed = process_url_batch(batch, output_dir, logger)
            logger.info(f"Processed {processed} records in batch")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == '__main__':
    main() 