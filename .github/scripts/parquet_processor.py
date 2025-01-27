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
    
    # Extract collections
    collections_section = soup.find('div', class_='collections-section')
    if collections_section:
        collections = []
        for collection in collections_section.find_all('div', class_='collection-item'):
            name = collection.find('div', class_='collection-name')
            type_elem = collection.find('div', class_='collection-type')
            if name:
                collections.append({
                    'name': name.text.strip(),
                    'type': type_elem.text.strip() if type_elem else None
                })
        data['collections'] = collections
    
    # Extract tags
    tags_section = soup.find('div', class_='tags-section')
    if tags_section:
        tags = [tag.text.strip() for tag in tags_section.find_all('div', class_='tag-item')]
        data['tags'] = tags
    
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
                # Clean and normalize field names
                field_name = label.text.strip().lower().replace(' ', '_')
                field_value = value.text.strip()
                
                # Convert numeric values where appropriate
                if any(num in field_name for num in ['size', 'width', 'height', 'depth', 'spacing', 'voltage', 'power']):
                    try:
                        # Extract numeric part
                        numeric_part = ''.join(c for c in field_value if c.isdigit() or c == '.')
                        if numeric_part:
                            field_value = float(numeric_part)
                    except ValueError:
                        pass
                
                section_data[field_name] = field_value
                
        # Normalize section names
        section_key = section_name.lower().replace(' ', '_')
        data[section_key] = section_data
    
    # Extract image acquisition steps
    acquisition_steps = soup.find_all('div', class_='acquisition-step')
    if acquisition_steps:
        steps_data = []
        for step in acquisition_steps:
            step_title = step.find('h3')
            step_fields = step.find_all('div', class_='field-item')
            
            step_data = {
                'title': step_title.text.strip() if step_title else None,
                'fields': {}
            }
            
            for field in step_fields:
                label = field.find('div', class_='field-label')
                value = field.find('div', class_='field-value')
                if label and value:
                    field_name = label.text.strip().lower().replace(' ', '_')
                    step_data['fields'][field_name] = value.text.strip()
                    
            steps_data.append(step_data)
            
        data['acquisition_steps'] = steps_data
    
    return data

def process_url_batch(urls, output_dir, logger, start_index, total_processed, max_records):
    """Process a batch of URLs and save to parquet"""
    all_data = []
    processed_count = 0
    
    end_index = min(start_index + max_records, len(urls))
    batch_urls = urls[start_index:end_index]
    
    for url in tqdm(batch_urls, desc=f"Processing URLs {start_index}-{end_index}"):
        try:
            logger.info(f"Processing URL: {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            page_data = extract_page_data(soup)
            
            # Add metadata
            page_data['url'] = url
            page_data['processed_at'] = datetime.now().isoformat()
            page_data['batch_index'] = start_index + processed_count
            
            all_data.append(page_data)
            processed_count += 1
            
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
        
        # Set outputs for GitHub Actions
        has_more = end_index < len(urls)
        print(f"::set-output name=has_more::{str(has_more).lower()}")
        print(f"::set-output name=next_index::{end_index}")
        print(f"::set-output name=total_processed::{total_processed + processed_count}")
        
        return processed_count
    
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--max-records', type=int, default=500)
    parser.add_argument('--start-index', type=int, default=0)
    parser.add_argument('--total-processed', type=int, default=0)
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
        logger.info(f"Starting at index {args.start_index}, processed so far: {args.total_processed}")
        
        # Process batch
        processed = process_url_batch(
            urls, 
            output_dir, 
            logger,
            args.start_index,
            args.total_processed,
            args.max_records
        )
        logger.info(f"Processed {processed} records in this batch")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == '__main__':
    main() 