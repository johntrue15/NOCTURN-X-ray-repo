from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementNotInteractableException,
    WebDriverException,
    StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager
import re
import sys
import logging
import time
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('screenshot_script.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

def setup_driver():
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Increase timeouts
        driver.set_page_load_timeout(45)
        driver.set_script_timeout(30)
        driver.implicitly_wait(15)
        
        return driver
    except Exception as e:
        logging.error(f"Failed to setup driver: {str(e)}")
        raise

def extract_id_from_url(url):
    try:
        match = re.search(r'(\d+)$', url)
        return match.group(1) if match else 'unknown'
    except Exception as e:
        logging.error(f"Error extracting ID from URL: {str(e)}")
        return 'unknown'

def wait_for_element(driver, by, selector, timeout=10, condition="presence"):
    """
    Wait for an element with customizable conditions
    """
    try:
        wait = WebDriverWait(driver, timeout)
        if condition == "presence":
            return wait.until(EC.presence_of_element_located((by, selector)))
        elif condition == "clickable":
            return wait.until(EC.element_to_be_clickable((by, selector)))
        elif condition == "visible":
            return wait.until(EC.visibility_of_element_located((by, selector)))
    except TimeoutException:
        logging.error(f"Timeout waiting for element: {selector}")
        raise
    except Exception as e:
        logging.error(f"Error waiting for element {selector}: {str(e)}")
        raise

def verify_page_loaded(driver, timeout=30):
    """Verify that the page has loaded properly"""
    try:
        # Wait for the page to be in ready state
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        
        # Additional check for specific elements that should be present
        WebDriverWait(driver, 5).until(
            lambda d: len(d.find_elements(By.TAG_NAME, "body")) > 0
        )
        return True
    except Exception as e:
        logging.error(f"Page load verification failed: {str(e)}")
        return False

def take_screenshot(url):
    file_id = extract_id_from_url(url)
    output_file = f"{file_id}.png"
    error_file = f"error_{file_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    max_retries = 3
    retry_delay = 10  # increased retry delay

    for attempt in range(max_retries):
        driver = None
        try:
            logging.info(f"\nAttempt {attempt + 1}/{max_retries} for ID {file_id}")
            logging.info(f"Loading URL: {url}")
            
            driver = setup_driver()
            driver.maximize_window()
            
            # Load the page with retry mechanism
            try:
                driver.get(url)
                if not verify_page_loaded(driver):
                    raise TimeoutException("Page did not load completely")
            except TimeoutException:
                logging.warning("Page load timeout, trying again with refresh...")
                driver.refresh()
                time.sleep(5)  # Wait after refresh
                if not verify_page_loaded(driver):
                    raise TimeoutException("Page did not load after refresh")
                
            # Additional wait for dynamic content
            time.sleep(5)  # Wait for dynamic content to load
            
            # Check if we're on the right page
            try:
                if "morphosource" not in driver.current_url.lower():
                    raise WebDriverException("Not on MorphoSource page")
            except Exception as e:
                logging.error(f"URL verification failed: {str(e)}")
                raise
            
            # Wait for and switch to iframe with multiple selectors
            logging.info("Waiting for iframe...")
            iframe_found = False
            iframe_selectors = [
                "iframe#uv-iframe",
                "iframe[id*='uv-']",  # Partial ID match
                "iframe[src*='uv']",   # Partial src match
                "iframe"               # Any iframe as fallback
            ]
            
            for selector in iframe_selectors:
                try:
                    logging.info(f"Trying iframe selector: {selector}")
                    uv_iframe = wait_for_element(
                        driver,
                        By.CSS_SELECTOR,
                        selector,
                        timeout=10,
                        condition="presence"
                    )
                    iframe_found = True
                    logging.info(f"Found iframe with selector: {selector}")
                    break
                except Exception as e:
                    logging.warning(f"Selector {selector} failed: {str(e)}")
                    continue
            
            if not iframe_found:
                logging.error("No iframe found with any selector")
                raise NoSuchElementException("Could not find iframe with any selector")
            
            # Add a small delay before switching
            time.sleep(2)
            driver.switch_to.frame(uv_iframe)
            
            # Wait for fullscreen button with retry
            logging.info("Waiting for fullscreen button...")
            for _ in range(3):
                try:
                    full_screen_btn = wait_for_element(
                        driver,
                        By.CSS_SELECTOR,
                        "button.btn.imageBtn.fullScreen",
                        timeout=10,
                        condition="clickable"
                    )
                    break
                except (TimeoutException, StaleElementReferenceException):
                    logging.warning("Retrying to find fullscreen button...")
                    driver.switch_to.default_content()
                    time.sleep(1)
                    driver.switch_to.frame(uv_iframe)
            
            # Click fullscreen with retry
            try:
                full_screen_btn.click()
            except ElementNotInteractableException:
                logging.warning("Direct click failed, trying JavaScript click...")
                driver.execute_script("arguments[0].click();", full_screen_btn)
            
            # Add delay before screenshot
            time.sleep(3)
            
            logging.info("Taking screenshot...")
            driver.save_screenshot(output_file)
            logging.info(f"Screenshot saved to {output_file}")
            return True

        except TimeoutException as e:
            logging.error(f"Timeout on attempt {attempt + 1}: {str(e)}")
        except WebDriverException as e:
            logging.error(f"WebDriver error on attempt {attempt + 1}: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
        finally:
            if driver:
                try:
                    if attempt < max_retries - 1:  # Save error screenshot only on non-final attempts
                        driver.save_screenshot(error_file)
                        logging.info(f"Error screenshot saved as {error_file}")
                except Exception as e:
                    logging.error(f"Failed to save error screenshot: {str(e)}")
                finally:
                    driver.quit()
        
        if attempt < max_retries - 1:
            logging.info(f"Waiting {retry_delay} seconds before retry...")
            time.sleep(retry_delay)

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
