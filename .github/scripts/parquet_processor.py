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
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.page_load_strategy = 'eager'
    chrome_options.binary_location = '/usr/bin/google-chrome'
    return webdriver.Chrome(options=chrome_options)

def extract_page_data(driver, url, logger):
    """Extract structured data from MorphoSource page using Selenium"""
    data = {
        'url': url,
        'processed_at': datetime.now().isoformat(),
        'media_id': None,
        'media_type': None,
        'object_element': None,
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
        'number_of_images': None,
        'creator': None,
        'date_created': None,
        'date_uploaded': None
    }
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "field-value")))
        
        # Dictionary mapping field names to their XPath expressions
        field_mappings = {
            'media_id': '//div[contains(text(), "Media ID")]/following-sibling::*[1]',
            'media_type': '//div[contains(text(), "Media type")]/following-sibling::*[1]',
            'object_element': '//div[contains(text(), "Object element or part")]/following-sibling::*[1]',
            'file_name': '//div[contains(text(), "File name")]/following-sibling::*[1]',
            'file_format': '//div[contains(text(), "File format")]/following-sibling::*[1]',
            'file_size': '//div[contains(text(), "File size")]/following-sibling::*[1]',
            'image_width': '//div[contains(text(), "Image width")]/following-sibling::*[1]',
            'image_height': '//div[contains(text(), "Image height")]/following-sibling::*[1]',
            'color_space': '//div[contains(text(), "Color space")]/following-sibling::*[1]',
            'color_depth': '//div[contains(text(), "Color depth")]/following-sibling::*[1]',
            'compression': '//div[contains(text(), "Compression")]/following-sibling::*[1]',
            'x_pixel_spacing': '//div[contains(text(), "X pixel spacing")]/following-sibling::*[1]',
            'y_pixel_spacing': '//div[contains(text(), "Y pixel spacing")]/following-sibling::*[1]',
            'z_pixel_spacing': '//div[contains(text(), "Z pixel spacing")]/following-sibling::*[1]',
            'pixel_spacing_units': '//div[contains(text(), "Pixel spacing units")]/following-sibling::*[1]',
            'slice_thickness': '//div[contains(text(), "Slice thickness")]/following-sibling::*[1]',
            'number_of_images': '//div[contains(text(), "Number of images in set")]/following-sibling::*[1]',
            'creator': '//div[contains(text(), "Creator")]/following-sibling::*[1]',
            'date_created': '//div[contains(text(), "Date created")]/following-sibling::*[1]',
            'date_uploaded': '//div[contains(text(), "Date uploaded")]/following-sibling::*[1]'
        }
        
        for field, xpath in field_mappings.items():
            try:
                element = driver.find_element(By.XPATH, xpath)
                value = element.text.strip()
                if '\n' in value:
                    value = value.split('\n')[0]
                    
                # Handle special field conversions
                if field == 'file_size':
                    try:
                        size_str = value.lower()
                        number = float(''.join(c for c in size_str if c.isdigit() or c == '.'))
                        if 'gb' in size_str:
                            data['file_size_bytes'] = number * 1024 * 1024 * 1024
                        elif 'mb' in size_str:
                            data['file_size_bytes'] = number * 1024 * 1024
                        elif 'kb' in size_str:
                            data['file_size_bytes'] = number * 1024
                    except ValueError as e:
                        logger.error(f"Error converting file size '{value}': {e}")
                elif field in ['image_width', 'image_height', 'color_depth', 'number_of_images']:
                    try:
                        data[field] = float(''.join(c for c in value if c.isdigit() or c == '.'))
                    except ValueError as e:
                        logger.error(f"Error converting {field} '{value}': {e}")
                elif field in ['x_pixel_spacing', 'y_pixel_spacing', 'z_pixel_spacing']:
                    try:
                        data[field] = float(value)
                    except ValueError as e:
                        logger.error(f"Error converting {field} '{value}': {e}")
                else:
                    data[field] = value
                    
                logger.debug(f"Found {field}: {value}")
                
            except Exception as e:
                logger.debug(f"Field {field} not found: {e}")
                
        return data
        
    except Exception as e:
        logger.error(f"Error extracting data from {url}: {e}")
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