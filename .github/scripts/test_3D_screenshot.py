from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import time
import sys
import re
import traceback
from datetime import datetime
from urllib3.exceptions import ReadTimeoutError
import urllib3
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_driver(max_retries=3, retry_delay=5):
    """Configure and return a Chrome WebDriver instance with retry logic"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--use-gl=swiftshader')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-gpu-driver-bug-workarounds')
    chrome_options.add_argument('--ignore-gpu-blocklist')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Additional options to improve stability
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-dev-tools')
    chrome_options.add_argument('--remote-debugging-port=9222')
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} to setup WebDriver")
            
            # Install ChromeDriver with increased timeout
            driver_path = ChromeDriverManager().install()
            service = Service(driver_path)
            
            # Create driver with custom connection timeout
            urllib3.Timeout.DEFAULT_TIMEOUT = 300.0  # 5 minutes
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Configure timeouts
            driver.set_page_load_timeout(300)  # 5 minutes
            driver.set_script_timeout(300)     # 5 minutes
            driver.implicitly_wait(30)         # 30 seconds
            
            logger.info("WebDriver setup successful")
            return driver
            
        except ReadTimeoutError as e:
            logger.error(f"Timeout during WebDriver setup: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                raise Exception("Max retries reached for WebDriver setup")
                
        except Exception as e:
            logger.error(f"Error during WebDriver setup: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                raise

def extract_id_from_url(url):
    """Extract the media ID from a MorphoSource URL"""
    patterns = [
        r'/media/(\d+)',
        r'/media/0*(\d+)',
        r'media/0*(\d+)\?'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    numbers = re.findall(r'\d+', url)
    return numbers[0] if numbers else 'unknown'

def verify_page_loaded(driver, timeout=60):
    """Verify that the page has loaded properly"""
    try:
        # Wait for body to be present
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Check page readyState
        ready_state = driver.execute_script("return document.readyState")
        if ready_state != "complete":
            raise Exception(f"Page not fully loaded. Ready state: {ready_state}")
            
        return True
    except Exception as e:
        logger.error(f"Page load verification failed: {str(e)}")
        return False

def wait_for_iframe(driver, timeout=60):
    """Wait for iframe to be present and switch to it"""
    try:
        iframe = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(iframe)
        time.sleep(5)  # Give iframe content time to load
        return True
    except Exception as e:
        logger.error(f"Iframe wait/switch failed: {str(e)}")
        return False

def process_url(url):
    """Process a single URL and take screenshots"""
    driver = None
    start_time = datetime.now()
    file_id = extract_id_from_url(url)
    
    logger.info(f"Starting processing of URL: {url}")
    logger.info(f"Extracted ID: {file_id}")
    
    try:
        # Setup WebDriver with retry logic
        driver = setup_driver(max_retries=3, retry_delay=5)
        
        # Load the page
        logger.info("Loading page...")
        driver.get(url)
        
        # Verify page load
        if not verify_page_loaded(driver):
            raise Exception("Page failed to load properly")
        
        # Take initial screenshot
        driver.save_screenshot(f"initial_{file_id}.png")
        
        # Switch to iframe
        if not wait_for_iframe(driver):
            raise Exception("Failed to switch to iframe")
        
        # Process rest of the workflow...
        # (Rest of the code remains the same)
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing URL: {str(e)}")
        traceback.print_exc()
        if driver:
            try:
                error_file = f"error_{file_id}.png"
                driver.save_screenshot(error_file)
                logger.info(f"Error screenshot saved as {error_file}")
                
                with open(f"error_{file_id}.txt", 'w') as f:
                    f.write(f"Error processing URL: {url}\n")
                    f.write(f"Error message: {str(e)}\n")
                    f.write(f"Traceback:\n{traceback.format_exc()}")
            except:
                logger.error("Could not save error files")
        return False
        
    finally:
        if driver:
            driver.quit()
        duration = datetime.now() - start_time
        logger.info(f"Processing time: {duration}")

def main():
    if len(sys.argv) != 2:
        logger.error("Usage: python screenshot_test.py <url_file>")
        sys.exit(1)
    
    try:
        with open(sys.argv[1], 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        logger.info(f"Found {len(urls)} URLs to process")
        
        success_count = 0
        for i, url in enumerate(urls, 1):
            logger.info(f"\nProcessing URL {i}/{len(urls)}")
            if process_url(url):
                success_count += 1
        
        logger.info(f"\nProcessing complete")
        logger.info(f"Successfully processed: {success_count}/{len(urls)}")
        
        if success_count != len(urls):
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error reading URL file: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
