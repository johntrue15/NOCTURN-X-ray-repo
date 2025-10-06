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
from selenium.common.exceptions import TimeoutException, WebDriverException
import signal
import functools

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
    chrome_options.binary_location = '/usr/bin/google-chrome'
    
    # Create driver with increased timeouts
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(45)    # Increased to 45 seconds
    driver.set_script_timeout(45)       # Increased to 45 seconds
    driver.implicitly_wait(20)          # Increased to 20 seconds
    
    return driver

def get_fields_for_type(media_type):
    """Get relevant fields based on media type"""
    base_fields = {
        'GENERAL DETAILS': [
            'Media ID', 'Media type', 'Object element or part',
            'Object represented', 'Object taxonomy', 'Object organization',
            'Side', 'Orientation', 'Short description', 'Full description',
            'Creator', 'Date created', 'Date uploaded'
        ],
        'OWNERSHIP AND PERMISSIONS': [
            'Data managed by', 'Data uploaded by', 'Publication status',
            'Download reviewer', 'IP holder', 'Copyright statement',
            'Creative Commons license', 'Morphosource use agreement type',
            'Permits commercial use', 'Permits 3D use',
            'Required archival of published derivatives', 'Funding attribution',
            'Publisher', 'Cite as', 'Media preview mode',
            'Additional usage agreement'
        ],
        'IDENTIFIERS AND EXTERNAL LINKS': [
            'MorphoSource ARK', 'MorphoSource DOI', 
            'External identifier', 'External media URL'
        ]
    }
    
    if media_type.lower() == 'volumetric image series':
        base_fields.update({
            'FILE OBJECT DETAILS': [
                'File name', 'File format(s)', 'File size', 'Image width',
                'Image height', 'Color space', 'Color depth', 'Compression',
                'X pixel spacing', 'Y pixel spacing', 'Z pixel spacing',
                'Pixel spacing units', 'Slice thickness', 'Number of images in set'
            ],
            'IMAGE ACQUISITION AND PROCESSING AT A GLANCE': [
                'Number of parent media', 'Number of processing events', 
                'Modality', 'Device'
            ]
        })
    elif media_type.lower() == 'mesh':
        base_fields.update({
            'FILE OBJECT DETAILS': [
                'File name', 'File format(s)', 'File size',
                'Points', 'Polygons', 'Map type', 'UV coordinates',
                'Vertex color', 'Bounding box dimensions', 
                'Centroid coordinates', 'Units of point coordinates'
            ],
            'IMAGE ACQUISITION AND PROCESSING AT A GLANCE': [
                'Number of parent media', 'Number of processing events',
                'Derived directly from', 'Modality', 'Device'
            ]
        })
    
    return base_fields

def check_page_structure(driver, url, logger):
    """Analyze page structure and return appropriate configuration"""
    logger.info(f"Analyzing structure for: {url}")
    
    try:
        # Wait for initial page load with progressive checks
        driver.get(url)
        
        # Wait for title to be present
        WebDriverWait(driver, 10).until(lambda d: d.title)
        logger.info("Title loaded")
        
        # Check if we're on a valid page
        if "Showcase Media" not in driver.title:
            return None, "Not a valid MorphoSource media page"
        
        # Wait for content to be present
        content_present = False
        max_attempts = 3
        attempt = 0
        
        while not content_present and attempt < max_attempts:
            try:
                # Try to find any showcase-label or field-name element
                WebDriverWait(driver, 10).until(lambda d: (
                    d.find_elements(By.CLASS_NAME, "showcase-label") or 
                    d.find_elements(By.CLASS_NAME, "field-name")
                ))
                content_present = True
                logger.info("Content elements found")
            except:
                attempt += 1
                logger.warning(f"Content load attempt {attempt} failed, retrying...")
                time.sleep(5)
        
        if not content_present:
            return None, "Content failed to load after multiple attempts"
            
        # Try different layout patterns
        layouts = {
            'showcase': {
                'media_type_xpath': "//div[contains(@class, 'showcase-label')][contains(text(), 'Media type')]/following-sibling::div[contains(@class, 'showcase-value')]",
                'field_class': 'showcase-label',
                'value_class': 'showcase-value'
            },
            'traditional': {
                'media_type_xpath': "//div[@class='field-name'][contains(text(), 'Media type')]/following-sibling::div[@class='field-value']",
                'field_class': 'field-name',
                'value_class': 'field-value'
            }
        }
        
        # Detect layout type and media type with retries
        layout_used = None
        media_type = None
        
        for layout_name, selectors in layouts.items():
            try:
                # Wait for media type element with timeout
                elem = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, selectors['media_type_xpath']))
                )
                if elem:
                    media_type = elem.text.strip()
                    layout_used = layout_name
                    logger.info(f"Found media type using {layout_name} layout")
                    break
            except:
                continue
                
        if not layout_used or not media_type:
            return None, "Could not determine page layout or media type"
            
        logger.info(f"Detected Layout: {layout_used}")
        logger.info(f"Media Type: {media_type}")
        
        # Get fields for type
        sections = get_fields_for_type(media_type)
            
        # Return configuration
        return {
            'layout': layout_used,
            'media_type': media_type,
            'selectors': layouts[layout_used],
            'sections': sections
        }, None
        
    except Exception as e:
        logger.error(f"Error analyzing page structure: {str(e)}", exc_info=True)
        return None, f"Error analyzing page structure: {str(e)}"

def extract_page_data(driver, url, logger):
    """Extract structured data from MorphoSource page using Selenium"""
    data = {
        'url': url,
        'processed_at': datetime.now().isoformat(),
        'error': None
    }
    
    try:
        # Get page structure configuration
        config, error = check_page_structure(driver, url, logger)
        
        if error:
            logger.error(f"Error: {error}")
            data['error'] = error
            return data
            
        # Extract data using detected layout
        for section_name, fields in config['sections'].items():
            logger.debug(f"Processing section: {section_name}")
            
            for field in fields:
                try:
                    if config['layout'] == 'showcase':
                        field_xpath = f"//div[contains(@class, 'showcase-label')][contains(text(), '{field}')]"
                        value_xpath = "./following-sibling::div[contains(@class, 'showcase-value')]"
                    else:
                        field_xpath = f"//div[@class='field-name'][contains(text(), '{field}')]"
                        value_xpath = "./following-sibling::div[@class='field-value']"
                    
                    field_elem = driver.find_element(By.XPATH, field_xpath)
                    if field_elem:
                        value_elem = field_elem.find_element(By.XPATH, value_xpath)
                        value = value_elem.text.strip() if value_elem else ""
                        if '\n' in value:
                            value = value.split('\n')[0]
                        
                        # Convert field name to column name
                        column_name = field.lower().replace(' ', '_').replace('(', '').replace(')', '')
                        data[column_name] = value
                        logger.debug(f"Found {field}: {value}")
                        
                except Exception as e:
                    logger.debug(f"Could not find {field}: {str(e)}")
                    column_name = field.lower().replace(' ', '_').replace('(', '').replace(')', '')
                    data[column_name] = None
        
        return data
        
    except Exception as e:
        logger.error(f"Error extracting data from {url}: {e}", exc_info=True)
        data['error'] = str(e)
        return data

def process_url_batch(urls, output_dir, logger, start_index, total_processed, max_records, output_file=None):
    """Process a batch of URLs and save to parquet"""
    all_data = []
    processed_count = 0
    error_count = 0
    skipped_records = []
    retry_count = 3
    record_timeout = 120  # 2 minutes timeout per record
    
    # Calculate the correct start and end indices
    end_index = min(start_index + max_records, len(urls))
    batch_urls = urls[start_index:end_index]
    
    logger.info(f"Processing batch from index {start_index} to {end_index} (total processed so far: {total_processed})")
    
    driver = None
    
    try:
        for url in tqdm(batch_urls, desc=f"Processing URLs {start_index}-{end_index}"):
            attempts = 0
            success = False
            start_time = time.time()
            
            current_index = start_index + processed_count
            logger.info(f"Processing record {current_index} (URL: {url})")
            
            while attempts < retry_count and not success and (time.time() - start_time) < record_timeout:
                try:
                    if driver is None:
                        logger.info("Setting up new Chrome driver")
                        driver = setup_driver()
                    
                    logger.info(f"Processing URL: {url} (Attempt {attempts + 1}/{retry_count})")
                    page_data = extract_page_data(driver, url, logger)
                    
                    page_data['batch_index'] = current_index
                    page_data['attempt'] = attempts + 1
                    page_data['processing_time'] = time.time() - start_time
                    
                    if page_data.get('error'):
                        logger.warning(f"Data extracted with error: {page_data['error']}")
                        error_count += 1
                        attempts += 1
                    else:
                        success = True
                        logger.info(f"Successfully processed {url} (record {current_index})")
                        all_data.append(page_data)
                        processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error on attempt {attempts + 1} for {url}: {str(e)}", exc_info=True)
                    attempts += 1
                    
                    # Reset driver on error
                    if driver is not None:
                        try:
                            driver.quit()
                        except:
                            pass
                        driver = None
                    
                    if attempts < retry_count:
                        logger.info(f"Retrying {url} after error...")
                        time.sleep(5)
                
                # Check timeout outside the try block
                if (time.time() - start_time) >= record_timeout:
                    logger.warning(f"Record processing timeout reached for {url}")
                    if not success:  # Only add to skipped if not already processed
                        skipped_records.append({
                            'url': url,
                            'index': current_index,
                            'reason': 'timeout',
                            'processing_time': time.time() - start_time,
                            'attempts': attempts
                        })
                        # Save skipped record immediately
                        skipped_file = output_dir / f'skipped_records_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                        with open(skipped_file, 'w') as f:
                            json.dump([skipped_records[-1]], f, indent=2)  # Save only the current skipped record
                        logger.info(f"Saved skipped record to {skipped_file}")
                    break
            
            # Only add to skipped records if truly failed and not already processed
            if not success and not any(r['url'] == url for r in skipped_records):
                skipped_records.append({
                    'url': url,
                    'index': current_index,
                    'reason': 'max_attempts',
                    'processing_time': time.time() - start_time,
                    'attempts': attempts
                })
            
            # Save intermediate results every 10 records
            if len(all_data) % 10 == 0 and all_data:
                save_batch_results(all_data, output_dir, logger)
                
    finally:
        if driver is not None:
            try:
                driver.quit()
            except:
                pass
    
    # Save final results
    if all_data:
        save_batch_results(all_data, output_dir, logger)
        
        # Write outputs to GitHub Actions output file
        if output_file:
            with open(output_file, 'a') as f:
                has_more = end_index < len(urls)
                f.write(f"has_more={str(has_more).lower()}\n")
                f.write(f"next_index={end_index}\n")
                f.write(f"total_processed={total_processed + processed_count}\n")
                f.write(f"error_count={error_count}\n")
                f.write(f"skipped_count={len(skipped_records)}\n")
        
        return processed_count
    
    return 0

def save_batch_results(data, output_dir, logger):
    """Save current batch of results to parquet file"""
    try:
        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        parquet_file = output_dir / f'morphosource_data_{timestamp}.parquet'
        df.to_parquet(parquet_file, index=False)
        logger.info(f"Saved {len(data)} records to {parquet_file}")
        logger.info(f"Columns: {', '.join(df.columns)}")
    except Exception as e:
        logger.error(f"Error saving batch results: {e}", exc_info=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--max-records', type=int, default=500)
    parser.add_argument('--start-index', type=int, default=0)
    parser.add_argument('--total-processed', type=int, default=0)
    parser.add_argument('--total-target', type=int, default=0)
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
        total_available = len(urls)
        logger.info(f"Found {total_available} URLs to process")
        
        # Convert inputs to integers and validate
        try:
            total_processed = int(args.total_processed)
            total_target = int(args.total_target)
            start_index = int(args.start_index)
        except ValueError as e:
            logger.error(f"Error converting input parameters: {e}")
            total_processed = 0
            total_target = 0
            start_index = 0
            
        logger.info(f"Starting with: index={start_index}, processed={total_processed}, target={total_target}")
        
        # Determine total records to process
        total_to_process = total_target if total_target > 0 else total_available
        remaining = total_to_process - total_processed
        
        if remaining <= 0:
            logger.info(f"Target number of records already processed: {total_processed} of {total_to_process}")
            if args.output_file:
                with open(args.output_file, 'a') as f:
                    f.write("has_more=false\n")
                    f.write(f"next_index={start_index}\n")
                    f.write(f"total_processed={total_processed}\n")
            return 0
            
        # Adjust max_records if needed
        max_records = min(args.max_records, remaining)
        logger.info(f"Processing up to {max_records} records this batch")
        logger.info(f"Total target: {total_to_process}, Remaining: {remaining}")
        logger.info(f"Starting at index {start_index}, processed so far: {total_processed}")
        
        # Process batch
        processed = process_url_batch(
            urls, 
            output_dir, 
            logger,
            start_index,
            total_processed,
            max_records,
            args.output_file
        )
        logger.info(f"Processed {processed} records in this batch")
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == '__main__':
    main() 