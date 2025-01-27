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

def extract_page_data(soup, url, logger):
    """Extract structured data from MorphoSource page"""
    data = {
        'url': url,
        'processed_at': datetime.now().isoformat(),
        'file_name': None,
        'file_format': None,
        'file_size_bytes': None,
        'image_width': None,
        'image_height': None,
        'color_space': None,
        'color_depth': None,
        'compression': None,
        'x_pixel_spacing': None,
        'y_pixel_spacing': None,
        'z_pixel_spacing': None,
        'pixel_spacing_units': None,
        'slice_thickness': None,
        'number_of_images': None
    }
    
    # Find the file object details section
    sections = soup.find_all('div', class_='detail-section')
    found_section = False
    
    for section in sections:
        section_title = section.find('h2')
        if not section_title:
            continue
            
        if 'FILE OBJECT DETAILS' in section_title.text.strip():
            found_section = True
            fields = section.find_all('div', class_='field-item')
            logger.debug(f"Found {len(fields)} fields in FILE OBJECT DETAILS section")
            
            for field in fields:
                label = field.find('div', class_='field-label')
                value = field.find('div', class_='field-value')
                
                if label and value:
                    field_name = label.text.strip().lower().replace(' ', '_')
                    field_value = value.text.strip()
                    logger.debug(f"Found field: {field_name} = {field_value}")
                    
                    # Map fields to our data structure
                    if field_name == 'file_name':
                        data['file_name'] = field_value
                    elif field_name == 'file_formats':
                        data['file_format'] = field_value
                    elif field_name == 'file_size':
                        try:
                            size_str = field_value.lower()
                            number = float(''.join(c for c in size_str if c.isdigit() or c == '.'))
                            if 'gb' in size_str:
                                data['file_size_bytes'] = number * 1024 * 1024 * 1024
                            elif 'mb' in size_str:
                                data['file_size_bytes'] = number * 1024 * 1024
                            elif 'kb' in size_str:
                                data['file_size_bytes'] = number * 1024
                        except ValueError as e:
                            logger.error(f"Error converting file size '{field_value}': {e}")
                    elif field_name == 'image_width':
                        try:
                            data['image_width'] = float(''.join(c for c in field_value if c.isdigit() or c == '.'))
                        except ValueError as e:
                            logger.error(f"Error converting image width '{field_value}': {e}")
                    elif field_name == 'image_height':
                        try:
                            data['image_height'] = float(''.join(c for c in field_value if c.isdigit() or c == '.'))
                        except ValueError as e:
                            logger.error(f"Error converting image height '{field_value}': {e}")
                    elif field_name == 'color_space':
                        data['color_space'] = field_value
                    elif field_name == 'color_depth':
                        try:
                            data['color_depth'] = float(''.join(c for c in field_value if c.isdigit() or c == '.'))
                        except ValueError as e:
                            logger.error(f"Error converting color depth '{field_value}': {e}")
                    elif field_name == 'compression':
                        data['compression'] = field_value
                    elif field_name == 'x_pixel_spacing':
                        try:
                            data['x_pixel_spacing'] = float(field_value)
                        except ValueError as e:
                            logger.error(f"Error converting x pixel spacing '{field_value}': {e}")
                    elif field_name == 'y_pixel_spacing':
                        try:
                            data['y_pixel_spacing'] = float(field_value)
                        except ValueError as e:
                            logger.error(f"Error converting y pixel spacing '{field_value}': {e}")
                    elif field_name == 'z_pixel_spacing':
                        try:
                            data['z_pixel_spacing'] = float(field_value)
                        except ValueError as e:
                            logger.error(f"Error converting z pixel spacing '{field_value}': {e}")
                    elif field_name == 'pixel_spacing_units':
                        data['pixel_spacing_units'] = field_value
                    elif field_name == 'slice_thickness':
                        data['slice_thickness'] = field_value
                    elif field_name == 'number_of_images_in_set':
                        try:
                            data['number_of_images'] = float(''.join(c for c in field_value if c.isdigit() or c == '.'))
                        except ValueError as e:
                            logger.error(f"Error converting number of images '{field_value}': {e}")
    
    if not found_section:
        logger.warning(f"No FILE OBJECT DETAILS section found for {url}")
    
    return data

def process_url_batch(urls, output_dir, logger, start_index, total_processed, max_records, output_file=None):
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
            page_data = extract_page_data(soup, url, logger)
            page_data['batch_index'] = start_index + processed_count
            
            # Log extracted data
            logger.info(f"Extracted data for {url}:")
            for key, value in page_data.items():
                if value is not None:  # Only log non-None values
                    logger.info(f"  {key}: {value}")
            
            all_data.append(page_data)
            processed_count += 1
            
            # Be nice to the server
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}", exc_info=True)
            continue
    
    if all_data:
        # Convert to DataFrame directly (no need for json_normalize)
        df = pd.DataFrame(all_data)
        
        # Save to parquet
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        parquet_file = output_dir / f'morphosource_data_{timestamp}.parquet'
        df.to_parquet(parquet_file, index=False)
        
        logger.info(f"Saved {len(all_data)} records to {parquet_file}")
        logger.info(f"Columns: {', '.join(df.columns)}")
        
        # Write outputs to GitHub Actions output file
        if output_file:
            with open(output_file, 'a') as f:
                has_more = end_index < len(urls)
                f.write(f"has_more={str(has_more).lower()}\n")
                f.write(f"next_index={end_index}\n")
                f.write(f"total_processed={total_processed + processed_count}\n")
        
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
    parser.add_argument('--output-file', help='GitHub Actions output file')
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
            args.max_records,
            args.output_file
        )
        logger.info(f"Processed {processed} records in this batch")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == '__main__':
    main() 