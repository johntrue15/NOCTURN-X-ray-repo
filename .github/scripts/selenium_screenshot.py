import sys
import re
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def parse_morphosource_urls(file_path):
    """Reads the release body and extracts MorphoSource record IDs and URLs."""
    print(f"Reading file: {file_path}")
    pattern = r'New Record #(\d+).*?Detail Page URL: (https:\/\/www\.morphosource\.org\/concern\/media\/\d+\?locale=en)'
    results = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
        for record_id, url in matches:
            results.append((record_id.strip(), url.strip()))
    
    print(f"Found {len(results)} record(s).")
    return results

def take_fullscreen_screenshot(driver, url, output_path):
    """Takes a fullscreen screenshot of a MorphoSource page."""
    print(f"Taking screenshot of {url}")
    
    # 1. Navigate and maximize
    driver.get(url)
    driver.maximize_window()
    
    # 2. Wait for and switch to iframe
    wait = WebDriverWait(driver, 5)
    uv_iframe = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
    )
    driver.switch_to.frame(uv_iframe)
    
    # 3. Click fullscreen button
    full_screen_btn = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
    )
    full_screen_btn.click()
    
    # 4. Wait for fullscreen animation (using the same wait time that worked)
    print(f"Waiting 112 seconds for fullscreen animation...")
    time.sleep(12)
    
    # 5. Take the screenshot
    driver.save_screenshot(output_path)
    print(f"Screenshot saved to {output_path}")
    
    # 6. Brief pause after screenshot
    time.sleep(3)

def main():
    if len(sys.argv) < 2:
        print("Usage: python selenium_screenshot.py <release_body.txt>")
        sys.exit(1)

    # Parse URLs from release body
    records = parse_morphosource_urls(sys.argv[1])
    if not records:
        print("No MorphoSource URLs found. Exiting.")
        sys.exit(0)

    # Ensure screenshots directory exists
    os.makedirs("screenshots", exist_ok=True)

    # Configure Chrome with the same working options
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    if os.path.exists('/usr/bin/chromium-browser'):
        options.binary_location = '/usr/bin/chromium-browser'

    driver = webdriver.Chrome(options=options)

    try:
        # Process each record
        for record_id, url in records:
            print(f"\nProcessing Record #{record_id}")
            screenshot_name = f"screenshots/{record_id}.png"
            try:
                take_fullscreen_screenshot(driver, url, screenshot_name)
                print(f"Successfully processed Record #{record_id}")
            except Exception as e:
                print(f"Error processing record {record_id}: {e}")

    finally:
        print("Closing WebDriver...")
        driver.quit()
        print("Browser closed")

if __name__ == "__main__":
    main()
