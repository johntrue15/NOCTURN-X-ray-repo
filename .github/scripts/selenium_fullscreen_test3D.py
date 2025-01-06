from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import os
import sys
import argparse
from datetime import datetime

# Default URL for 3D test
DEFAULT_URL = "https://www.morphosource.org/concern/media/000699150"

def parse_arguments():
    parser = argparse.ArgumentParser(description='Run Selenium fullscreen test')
    parser.add_argument('--url', type=str, help='URL to test (optional)', default=DEFAULT_URL)
    return parser.parse_args()

def take_screenshot_with_retry(driver, screenshot_name, max_retries=3, wait_between_retries=10):
    """Attempt to take a screenshot with multiple retries"""
    for attempt in range(max_retries):
        try:
            driver.save_screenshot(screenshot_name)
            print(f"Screenshot successfully saved as {screenshot_name} on attempt {attempt + 1}")
            return True
        except TimeoutException as e:
            print(f"Screenshot attempt {attempt + 1} failed with timeout: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Waiting {wait_between_retries} seconds before retry...")
                time.sleep(wait_between_retries)
            else:
                print("Max retries reached for screenshot")
                raise
        except Exception as e:
            print(f"Unexpected error during screenshot: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Waiting {wait_between_retries} seconds before retry...")
                time.sleep(wait_between_retries)
            else:
                raise

def test_fullscreen_screenshot(url):
    driver = None
    start_time = datetime.now()
    
    try:
        print(f"Testing URL: {url}")
        
        # 1. Configure ChromeOptions with enhanced settings
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--start-maximized')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        
        # Initialize webdriver with extended timeouts
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(60)
        
        print("Starting test execution...")
        
        # 2. Navigate to the page with retry logic
        max_navigation_retries = 3
        for attempt in range(max_navigation_retries):
            try:
                driver.get(url)
                break
            except TimeoutException as e:
                if attempt < max_navigation_retries - 1:
                    print(f"Navigation timeout, attempt {attempt + 1} of {max_navigation_retries}")
                    driver.refresh()
                    time.sleep(5)
                else:
                    raise Exception("Failed to load page after multiple attempts") from e

        # 3. Set up WebDriverWait with longer timeout
        wait = WebDriverWait(driver, 30)
        
        # 4. Wait for and switch to iframe
        print("Waiting for iframe...")
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)
        
        # 5. Wait for and click fullscreen button
        print("Waiting for fullscreen button...")
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        
        # 6. Wait for content to load with progress monitoring
        #total_wait = 2
        #interval = 1
        #print(f"Waiting {total_wait} seconds for content to load...")
        #for i in range(0, total_wait, interval):
        #    time.sleep(interval)
        #    elapsed = i + interval
        #    print(f"Still waiting... {elapsed}/{total_wait} seconds elapsed")
        
        # 7. Take screenshot with retry mechanism
        screenshot_name = "fullscreen_screenshot_3D.png"
        take_screenshot_with_retry(driver, screenshot_name)
        
    except TimeoutException as e:
        print(f"Operation timed out: {str(e)}")
        raise
    except WebDriverException as e:
        print(f"WebDriver error: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise
    finally:
        # 8. Cleanup
        if driver:
            try:
                driver.quit()
            except Exception as e:
                print(f"Error during driver cleanup: {str(e)}")
        
        # Print execution time
        end_time = datetime.now()
        duration = end_time - start_time
        print(f"Total execution time: {duration}")

if __name__ == "__main__":
    try:
        args = parse_arguments()
        test_fullscreen_screenshot(args.url)
    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        sys.exit(1)
