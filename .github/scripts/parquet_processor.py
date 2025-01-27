import os
import json
import logging
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

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

def setup_driver():
    """Configure Chrome driver with optimized settings"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.binary_location = '/usr/bin/google-chrome'
    return webdriver.Chrome(options=chrome_options)

def extract_page_data(driver, url, logger):
    """Extract structured data from MorphoSource page using Selenium"""
    data = {
        'url': url,
        'processed_at': datetime.now().isoformat(),
    }
    
    try:
        driver.get(url)
        time.sleep(5)  # Wait for content to load
        
        # Dictionary of all sections and their fields
        sections = {
            'GENERAL DETAILS': {
                'fields': [
                    'Media ID', 'Media type', 'Object element or part',
                    'Object represented', 'Object taxonomy', 'Object organization',
                    'Side', 'Orientation', 'Short description', 'Full description',
                    'Creator', 'Date created', 'Date uploaded'
                ]
            },
            'FILE OBJECT DETAILS': {
                'fields': [
                    'File name', 'File format(s)', 'File size', 'Image width',
                    'Image height', 'Color space', 'Color depth', 'Compression',
                    'X pixel spacing', 'Y pixel spacing', 'Z pixel spacing',
                    'Pixel spacing units', 'Slice thickness', 'Number of images in set'
                ]
            },
            'IMAGE ACQUISITION AND PROCESSING AT A GLANCE': {
                'fields': [
                    'Number of parent media', 'Number of processing events', 'Modality',
                    'Device'
                ]
            },
            'OWNERSHIP AND PERMISSIONS': {
                'fields': [
                    'Data managed by', 'Data uploaded by', 'Publication status',
                    'Download reviewer', 'IP holder', 'Copyright statement',
                    'Creative Commons license', 'MorphoSource use agreement type',
                    'Permits commercial use', 'Permits 3D use',
                    'Required archival of published derivatives', 'Funding attribution',
                    'Publisher', 'Cite as', 'Media preview mode',
                    'Additional usage agreement'
                ]
            },
            'IDENTIFIERS AND EXTERNAL LINKS': {
                'fields': [
                    'MorphoSource ARK', 'MorphoSource DOI', 'External identifier',
                    'External media URL'
                ]
            }
        }
        
        for section_name, section_info in sections.items():
            logger.debug(f"Looking for section: {section_name}")
            
            for field in section_info['fields']:
                try:
                    # Look for field names and their corresponding values
                    field_elements = driver.find_elements(By.XPATH, 
                        f"//*[contains(text(), '{field}')]/following-sibling::*[1]")
                    
                    if field_elements:
                        value = field_elements[0].text.strip()
                        # Clean up value - remove 'More...' and similar trailing text
                        if '\n' in value:
                            value = value.split('\n')[0]
                        
                        # Convert field name to column name
                        column_name = field.lower().replace(' ', '_')
                        
                        # Handle special conversions
                        if field == 'File size':
                            try:
                                size_str = value.lower()
                                number = float(''.join(c for c in size_str if c.isdigit() or c == '.'))
                                if 'gb' in size_str:
                                    data['file_size_bytes'] = number * 1024 * 1024 * 1024
                                elif 'mb' in size_str:
                                    data['file_size_bytes'] = number * 1024 * 1024
                                elif 'kb' in size_str:
                                    data['file_size_bytes'] = number * 1024
                            except ValueError:
                                data['file_size_bytes'] = None
                        elif field in ['Image width', 'Image height', 'Color depth', 'Number of images in set']:
                            try:
                                data[column_name] = float(''.join(c for c in value if c.isdigit() or c == '.'))
                            except ValueError:
                                data[column_name] = None
                        elif field in ['X pixel spacing', 'Y pixel spacing', 'Z pixel spacing']:
                            try:
                                data[column_name] = float(value)
                            except ValueError:
                                data[column_name] = None
                        else:
                            data[column_name] = value
                            
                        logger.debug(f"Found {field}: {value}")
                except Exception as e:
                    logger.debug(f"Error finding {field}: {e}")
                    data[column_name] = None
        
        return data
        
    except Exception as e:
        logger.error(f"Error extracting data from {url}: {e}", exc_info=True)
        return data

def process_url_batch(urls, output_dir, logger, start_index, total_processed, max_records, output_file=None):
    """Process a batch of URLs and save to parquet"""
    all_data = []
    processed_count = 0
    
    end_index = min(start_index + max_records, len(urls))
    batch_urls = urls[start_index:end_index]
    
    # Setup Chrome driver
    driver = setup_driver()
    
    try:
        for url in tqdm(batch_urls, desc=f"Processing URLs {start_index}-{end_index}"):
            try:
                logger.info(f"Processing URL: {url}")
                page_data = extract_page_data(driver, url, logger)
                page_data['batch_index'] = start_index + processed_count
                
                # Log extracted data
                logger.info(f"Extracted data for {url}:")
                for key, value in page_data.items():
                    if value is not None:
                        logger.info(f"  {key}: {value}")
                
                all_data.append(page_data)
                processed_count += 1
                
                # Be nice to the server
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing {url}: {str(e)}", exc_info=True)
                continue
                
    finally:
        # Clean up driver
        try:
            driver.quit()
        except:
            pass
    
    if all_data:
        # Convert to DataFrame
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