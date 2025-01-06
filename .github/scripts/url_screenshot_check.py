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
import json
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
            raise MorphoSourceTemporarilyUnavailable("MorphoSource is temporarily unavailable (500 error)")
    except Exception as e:
        if "MorphoSource temporarily unavailable (500)" in str(e):
            raise MorphoSourceTemporarilyUnavailable("MorphoSource is temporarily unavailable (500 error)")

def handle_media_error(url, driver):
    """Handle media error case and create status file"""
    file_id = extract_id_from_url(url)
    status_data = {
        'status': 'media_error',
        'url': url,
        'file_id': file_id,
        'timestamp': datetime.now().isoformat()
    }
    
    # Save the error state screenshot
    error_file = f"{file_id}.png"
    try:
        driver.save_screenshot(error_file)
        logging.info(f"Error state screenshot saved to {error_file}")
    except Exception as e:
        logging.error(f"Failed to save error screenshot: {str(e)}")
    
    # Save status file
    with open('url_check_status.json', 'w') as f:
        json.dump(status_data, f, indent=2)
    logging.info("Status file saved")
    
    return True

def handle_server_error(url):
    """Handle server error case and create status file"""
    file_id = extract_id_from_url(url)
    status_data = {
        'status': 'server_error',
        'url': url,
        'file_id': file_id,
        'timestamp': datetime.now().isoformat(),
        'error': 'MorphoSource temporarily unavailable (500)'
    }
    
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

    for attempt in range(max_retries):
        driver = None
        try:
            logging.info(f"\nAttempt {attempt + 1}/{max_retries} for ID {file_id}")
            logging.info(f"Loading URL: {url}")
            
            driver = setup_driver()
            driver.get(url)
            
            # Check for 500 error first
            try:
                check_for_server_error(driver)
            except MorphoSourceTemporarilyUnavailable as e:
                logging.warning(f"Server Error: {str(e)}")
                if attempt == max_retries - 1:  # If this is the last attempt
                    return handle_server_error(url)
                time.sleep(5)  # Wait before retry
                continue
            
            # Check for the not-ready message
            try:
                not_ready = driver.find_element(By.CSS_SELECTOR, 'div.not-ready')
                if "Media preview currently unavailable" in not_ready.text:
                    logging.info("morphosource media error")
                    print("morphosource media error")
                    return handle_media_error(url, driver)
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
                driver.quit()

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

        for i, url in enumerate(urls, 1):
            logging.info(f"\nProcessing URL {i}/{len(urls)}: {url}")
            if take_screenshot(url):
                successful_screenshots += 1

        logging.info(f"\nScreenshot process complete")
        logging.info(f"Successfully captured {successful_screenshots} out of {len(urls)} screenshots")

        # Modified exit condition: Don't exit with error if all failures were due to server error
        status_file = 'url_check_status.json'
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                status = json.load(f)
                if status.get('status') == 'server_error':
                    logging.warning("Process completed with server error")
                    sys.exit(0)  # Exit gracefully for server errors

        if successful_screenshots != len(urls):
            sys.exit(1)

    except Exception as e:
        logging.error(f"Error reading file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        logging.error("Usage: python script.py <input_file>")
        sys.exit(1)

    process_urls_from_file(sys.argv[1])
