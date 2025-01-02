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

def take_morphosource_screenshot(url, record_id):
    """Takes a fullscreen screenshot of a MorphoSource page."""
    # 1. Launch the browser with the same working options
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    if os.path.exists('/usr/bin/chromium-browser'):
        options.binary_location = '/usr/bin/chromium-browser'

    driver = webdriver.Chrome(options=options)

    try:
        # 2. Go to the MorphoSource page
        driver.get(url)
        driver.maximize_window()

        # 3. Wait until the uv-iframe is available, then switch into it
        wait = WebDriverWait(driver, 5)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)

        # 4. Click the Full Screen button
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()

        # 5. Wait a moment to let the fullscreen animation take effect
        time.sleep(112)

        # 6. Take screenshots with both naming patterns
        # Original working filename
        screenshot_name = "fullscreen_screenshot.png"
        driver.save_screenshot(screenshot_name)
        print(f"Screenshot saved as {screenshot_name}")

        # Record-specific filename in screenshots directory
        record_screenshot = f"screenshots/{record_id}.png"
        driver.save_screenshot(record_screenshot)
        print(f"Screenshot also saved as {record_screenshot}")

        # 7. Pause briefly
        time.sleep(3)

    finally:
        # 8. Quit the browser
        driver.quit()

def main():
    if len(sys.argv) < 2:
        print("Usage: python selenium_screenshot.py <release_body.txt>")
        sys.exit(1)

    # Parse URLs from release body
    records = parse_morphosource_urls(sys.argv[1])
    if not records:
        print("No MorphoSource URLs found. Exiting.")
        sys.exit(0)

    # Create screenshots directory
    os.makedirs("screenshots", exist_ok=True)

    # Process each record
    for record_id, url in records:
        print(f"\nProcessing Record #{record_id}")
        try:
            take_morphosource_screenshot(url, record_id)
        except Exception as e:
            print(f"Error processing record {record_id}: {e}")

if __name__ == "__main__":
    main()
