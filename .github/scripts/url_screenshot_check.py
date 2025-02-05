from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import re
import sys
import os
import json
import time
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

class MorphoSourceTemporarilyUnavailable(Exception):
    """Custom exception for when MorphoSource is temporarily unavailable"""
    pass

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--window-size=1920,1080')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)
    
    return driver

def extract_id_from_url(url):
    match = re.search(r'(\d+)$', url)
    return match.group(1) if match else 'unknown'

def check_for_server_error(driver):
    """Check if the page shows the 500 error message"""
    try:
        title = driver.title
        if "MorphoSource temporarily unavailable (500)" in title:
            logging.warning("Detected MorphoSource 500 error page")
            return True
        
        # Also check the page source for the error message
        if "MorphoSource temporarily unavailable (500)" in driver.page_source:
            logging.warning("Detected MorphoSource 500 error in page source")
            return True
            
        return False
    except Exception as e:
        if "MorphoSource temporarily unavailable (500)" in str(e):
            logging.warning("Detected MorphoSource 500 error in exception")
            return True
        return False

def handle_media_error(url, driver, error_type="media_error", error_message=None):
    """Handle media error case and create status file"""
    file_id = extract_id_from_url(url)
    status_data = {
        'status': error_type,
        'url': url,
        'file_id': file_id,
        'timestamp': datetime.now().isoformat()
    }
    if error_message:
        status_data['error_message'] = error_message
    
    # Save the error state screenshot
    error_file = f"error_{file_id}.png"
    try:
        driver.save_screenshot(error_file)
        logging.info(f"Error state screenshot saved to {error_file}")
    except Exception as e:
        logging.error(f"Failed to save error screenshot: {str(e)}")
    
    # Save status file
    with open('url_check_status.json', 'w') as f:
        json.dump(status_data, f, indent=2)
    logging.info(f"Status file saved with {error_type}")
    
    return True

def handle_server_error(url, driver=None):
    """Handle server error case and create status file"""
    file_id = extract_id_from_url(url)
    status_data = {
        'status': 'server_error',
        'url': url,
        'file_id': file_id,
        'timestamp': datetime.now().isoformat(),
        'error': 'MorphoSource temporarily unavailable (500)'
    }
    
    # Try to save error screenshot if driver is available
    if driver:
        error_file = f"error_{file_id}_500.png"
        try:
            driver.save_screenshot(error_file)
            logging.info(f"500 error screenshot saved as {error_file}")
        except Exception as e:
            logging.error(f"Failed to save 500 error screenshot: {str(e)}")
    
    # Save status file
    with open('url_check_status.json', 'w') as f:
        json.dump(status_data, f, indent=2)
    logging.info("Server error status file saved")
    
    return False

def take_screenshot(url):
    file_id = extract_id_from_url(url)
    output_file = f"{file_id}.png"
    error_file = f"error_{file_id}.png"
    max_retries = 3
    server_error_count = 0

    for attempt in range(max_retries):
        driver = None
        try:
            logging.info(f"\nAttempt {attempt + 1}/{max_retries} for ID {file_id}")
            logging.info(f"Loading URL: {url}")
            
            driver = setup_driver()
            driver.get(url)
            
            # Check for 500 error first
            if check_for_server_error(driver):
                server_error_count += 1
                if attempt == max_retries - 1:  # If this is the last attempt
                    return handle_server_error(url, driver)
                logging.warning(f"Server error detected (attempt {attempt + 1}), waiting 5 seconds before retry...")
                time.sleep(5)
                continue
            
            # Check for error messages
            try:
                not_ready = driver.find_element(By.CSS_SELECTOR, 'div.not-ready')
                error_text = not_ready.text
                
                if "Media preview currently unavailable" in error_text:
                    logging.info("morphosource media error")
                    print("morphosource media error")
                    return handle_media_error(url, driver, "media_error", error_text)
                elif "No file uploaded" in error_text:
                    logging.info("morphosource no file error")
                    print("morphosource no file error")
                    return handle_media_error(url, driver, "no_file_error", error_text)
            except NoSuchElementException:
                pass
            
            # If no errors, proceed with screenshot
            wait = WebDriverWait(driver, 10)
            uv_iframe = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
            )

            driver.switch_to.frame(uv_iframe)
            
            full_screen_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
            )
            full_screen_btn.click()

            logging.info("Taking screenshot...")
            driver.save_screenshot(output_file)
            logging.info(f"Screenshot saved to {output_file}")
            return True

        except Exception as e:
            logging.error(f"Error on attempt {attempt + 1}: {str(e)}")
            if driver:
                try:
                    driver.save_screenshot(error_file)
                    logging.info(f"Error screenshot saved as {error_file}")
                except Exception as se:
                    logging.error(f"Failed to save error screenshot: {str(se)}")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    # If we got here and all attempts were server errors, handle it
    if server_error_count == max_retries:
        return handle_server_error(url)
    
    return False

def process_urls_from_file(input_file):
    try:
        with open(input_file, 'r') as f:
            content = f.read().strip()

        urls = re.findall(r'https://www\.morphosource\.org/concern/media/\d+', content)

        if not urls:
            logging.error("No valid MorphoSource URLs found in file")
            return

        logging.info(f"Found {len(urls)} MorphoSource URLs in file")
        successful_screenshots = 0
        server_errors = 0

        for i, url in enumerate(urls, 1):
            logging.info(f"\nProcessing URL {i}/{len(urls)}: {url}")
            result = take_screenshot(url)
            
            # Check if it was a server error
            if os.path.exists('url_check_status.json'):
                with open('url_check_status.json', 'r') as f:
                    status = json.load(f)
                    if status.get('status') == 'server_error':
                        server_errors += 1
                        continue
            
            if result:
                successful_screenshots += 1

        logging.info(f"\nScreenshot process complete")
        logging.info(f"Successfully captured {successful_screenshots} out of {len(urls)} screenshots")
        if server_errors > 0:
            logging.warning(f"Encountered {server_errors} server errors")

        # Exit with success if all failures were server errors
        failed_count = len(urls) - successful_screenshots
        if failed_count > 0 and failed_count == server_errors:
            logging.warning("All failures were due to server errors")
            sys.exit(0)
            
        # Otherwise exit with error if any screenshots failed
        if successful_screenshots != len(urls):
            sys.exit(1)

    except Exception as e:
        logging.error(f"Error processing file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        logging.error("Usage: python script.py <input_file>")
        sys.exit(1)

    process_urls_from_file(sys.argv[1])
