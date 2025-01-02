import sys
import re
import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def log_time(message):
    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{timestamp}] {message}")

def parse_morphosource_urls(file_path):
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
    try:
        log_time(f"Navigating to {url}")
        driver.get(url)
        driver.maximize_window()
        log_time("Window maximized")

        # Wait for and switch to iframe with shorter initial wait
        log_time("Waiting for iframe...")
        wait = WebDriverWait(driver, 10)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)
        log_time("Switched to iframe")

        # Take multiple screenshots with shorter intervals
        for attempt in range(3):
            try:
                log_time(f"Screenshot attempt {attempt + 1}")
                
                # Click fullscreen button
                full_screen_btn = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
                )
                full_screen_btn.click()
                log_time("Clicked Full Screen button")

                # Break up the long wait into smaller chunks
                total_wait = 30  # Reduced from 112
                chunk_size = 5
                for i in range(0, total_wait, chunk_size):
                    time.sleep(chunk_size)
                    log_time(f"Waited {i + chunk_size} seconds of {total_wait}")

                # Take screenshot with attempt number
                attempt_path = f"{output_path}_attempt_{attempt + 1}.png"
                log_time(f"Taking screenshot: {attempt_path}")
                driver.save_screenshot(attempt_path)
                log_time(f"Screenshot saved: {attempt_path}")

                # If we get here, screenshot was successful
                if os.path.exists(attempt_path):
                    os.rename(attempt_path, output_path)
                    log_time(f"Final screenshot saved as: {output_path}")
                    break

            except TimeoutException:
                log_time(f"Timeout on attempt {attempt + 1}")
                continue
            except Exception as e:
                log_time(f"Error on attempt {attempt + 1}: {str(e)}")
                continue

    except Exception as e:
        log_time(f"Error during screenshot process: {str(e)}")
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

    log_time("Configuring Selenium WebDriver...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
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
                log_time(f"Successfully processed Record #{record_id}")
            except Exception as e:
                log_time(f"Error processing record {record_id}: {str(e)}")
                continue

    except Exception as e:
        log_time(f"ERROR in main process: {e}")
    finally:
        log_time("Closing WebDriver...")
        driver.quit()
        log_time("WebDriver closed successfully.")

    log_time("=== Finished selenium_screenshot.py ===")

if __name__ == "__main__":
    main()
