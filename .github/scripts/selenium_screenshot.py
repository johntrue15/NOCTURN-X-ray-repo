import sys
import re
import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def log_time(message):
    """Helper function to print timestamped messages"""
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] {message}")

def parse_morphosource_urls(file_path):
    """
    Reads the release body from file_path and extracts MorphoSource record IDs and URLs.
    """
    log_time(f"Reading file: {file_path}")
    pattern = r'New Record #(\d+).*?Detail Page URL: (https:\/\/www\.morphosource\.org\/concern\/media\/\d+\?locale=en)'
    results = []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        log_time("File content loaded. Searching for matches...")
        matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
        for record_id, url in matches:
            results.append((record_id.strip(), url.strip()))

    log_time(f"Found {len(results)} record(s).")
    return results

def take_fullscreen_screenshot(driver, url, output_path):
    """
    Takes a fullscreen screenshot of a MorphoSource page.
    """
    try:
        log_time(f"Navigating to {url}")
        driver.get(url)
        driver.maximize_window()
        log_time("Window maximized")

        # Wait for and switch to iframe
        log_time("Waiting for iframe...")
        wait = WebDriverWait(driver, 5)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)
        log_time("Switched to iframe")

        # Click fullscreen button
        log_time("Looking for Full Screen button")
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        log_time("Clicked Full Screen button")

        # Wait for fullscreen and take screenshot
        log_time("Waiting for fullscreen animation...")
        time.sleep(112)  # Using the working timeout value
        
        log_time(f"Taking screenshot: {output_path}")
        driver.save_screenshot(output_path)
        log_time("Screenshot saved")

        # Brief pause after screenshot
        time.sleep(3)

    except Exception as e:
        log_time(f"Error during screenshot: {str(e)}")
        raise

def main():
    log_time("=== Starting selenium_screenshot.py ===")

    if len(sys.argv) < 2:
        log_time("Usage: python selenium_screenshot.py <release_body.txt>")
        sys.exit(1)

    release_body_file = sys.argv[1]
    log_time(f"Release body file provided: {release_body_file}")

    records = parse_morphosource_urls(release_body_file)
    if not records:
        log_time("No MorphoSource URLs found in the release body. Exiting.")
        sys.exit(0)

    log_time(f"Preparing to capture screenshots for {len(records)} record(s)...")

    os.makedirs("screenshots", exist_ok=True)
    log_time("Created/ensured 'screenshots' folder exists.")

    log_time("Configuring Selenium WebDriver...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    if os.path.exists('/usr/bin/chromium-browser'):
        options.binary_location = '/usr/bin/chromium-browser'

    driver = webdriver.Chrome(options=options)
    log_time("WebDriver initialization complete.")

    try:
        for idx, (record_id, url) in enumerate(records, start=1):
            log_time(f"\n[{idx}/{len(records)}] Processing Record #{record_id}")
            screenshot_name = f"screenshots/{record_id}.png"
            try:
                take_fullscreen_screenshot(driver, url, screenshot_name)
                log_time(f"Successfully captured screenshot for Record #{record_id}")
            except Exception as e:
                log_time(f"Error processing record {record_id}: {str(e)}")
                continue  # Continue with next record even if one fails

    except Exception as e:
        log_time(f"ERROR occurred while capturing screenshots: {e}")
    finally:
        log_time("Closing WebDriver...")
        driver.quit()
        log_time("WebDriver closed successfully.")

    log_time("=== Finished selenium_screenshot.py ===")

if __name__ == "__main__":
    main()
