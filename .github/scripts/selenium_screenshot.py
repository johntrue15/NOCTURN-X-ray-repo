import sys
import re
import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service

def log_time(message):
    """Helper function to print timestamped messages"""
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] {message}")

def take_fullscreen_screenshot(driver, url, output_path):
    start_time = time.time()
    log_time(f"Starting screenshot process for {url}")
    
    try:
        log_time("Navigating to URL")
        driver.get(url)
        log_time(f"Navigation complete. Took {time.time() - start_time:.2f} seconds")
        
        nav_time = time.time()
        driver.maximize_window()
        log_time("Window maximized")
        
        wait = WebDriverWait(driver, 40)
        log_time("Looking for iframe...")
        
        iframe_start = time.time()
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                uv_iframe = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
                )
                log_time(f"Found iframe on attempt {attempt + 1}. Took {time.time() - iframe_start:.2f} seconds")
                break
            except Exception as e:
                log_time(f"Attempt {attempt + 1} failed to find iframe")
                if attempt == max_attempts - 1:
                    raise
                time.sleep(5)
        
        switch_time = time.time()
        driver.switch_to.frame(uv_iframe)
        log_time(f"Switched to iframe. Took {time.time() - switch_time:.2f} seconds")
        
        log_time("Waiting 5 seconds for page stabilization")
        time.sleep(5)
        
        button_start = time.time()
        log_time("Looking for Full Screen button")
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        log_time(f"Found Full Screen button. Took {time.time() - button_start:.2f} seconds")
        
        click_start = time.time()
        for attempt in range(max_attempts):
            try:
                log_time(f"Attempting to click fullscreen (attempt {attempt + 1})")
                full_screen_btn.click()
                log_time("Successfully clicked fullscreen")
                break
            except Exception as e:
                log_time(f"Click attempt {attempt + 1} failed")
                if attempt == max_attempts - 1:
                    raise
                time.sleep(5)
        
        log_time("Waiting 10 seconds in fullscreen mode")
        time.sleep(10)
        
        screenshot_start = time.time()
        log_time("Taking screenshot")
        driver.save_screenshot(output_path)
        log_time(f"Screenshot saved to {output_path}. Took {time.time() - screenshot_start:.2f} seconds")
        
        total_time = time.time() - start_time
        log_time(f"Total screenshot process took {total_time:.2f} seconds")
                
    except Exception as e:
        log_time(f"Error during screenshot: {str(e)}")
        raise

def main():
    start_time = time.time()
    log_time("=== Starting selenium_screenshot.py ===")

    if len(sys.argv) < 2:
        log_time("Usage: python selenium_screenshot.py <release_body.txt>")
        sys.exit(1)

    release_body_file = sys.argv[1]
    log_time(f"Release body file provided: {release_body_file}")

    # Parse URLs
    parse_start = time.time()
    pattern = r'New Record #(\d+).*?Detail Page URL: (https:\/\/www\.morphosource\.org\/concern\/media\/\d+\?locale=en)'
    with open(release_body_file, 'r', encoding='utf-8') as f:
        content = f.read()
    matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
    records = [(record_id.strip(), url.strip()) for record_id, url in matches]
    log_time(f"Found {len(records)} URLs. Parsing took {time.time() - parse_start:.2f} seconds")

    if not records:
        log_time("No MorphoSource URLs found. Exiting.")
        sys.exit(0)

    os.makedirs("screenshots", exist_ok=True)
    log_time("Created screenshots directory")

    # Set up WebDriver
    driver_start = time.time()
    log_time("Configuring Chrome...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.binary_location = '/usr/bin/chromium-browser'
    options.set_capability('pageLoadStrategy', 'normal')
    
    service = Service()
    driver = webdriver.Chrome(service=service, options=options)
    log_time(f"Chrome setup complete. Took {time.time() - driver_start:.2f} seconds")

    try:
        for idx, (record_id, url) in enumerate(records, start=1):
            log_time(f"\nProcessing record {idx}/{len(records)}: #{record_id}")
            screenshot_name = f"screenshots/{record_id}.png"
            try:
                take_fullscreen_screenshot(driver, url, screenshot_name)
                log_time(f"Successfully processed record #{record_id}")
            except Exception as e:
                log_time(f"Failed to process record #{record_id}: {str(e)}")
                continue

    except Exception as e:
        log_time(f"Fatal error: {e}")
    finally:
        log_time("Closing Chrome...")
        driver.quit()
        log_time("Chrome closed")

    total_time = time.time() - start_time
    log_time(f"=== Script completed in {total_time:.2f} seconds ===")

if __name__ == "__main__":
    main()
