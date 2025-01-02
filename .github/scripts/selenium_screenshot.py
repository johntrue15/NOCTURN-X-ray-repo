import sys
import re
import os
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def parse_morphosource_urls(file_path):
    """
    Reads the release body from file_path and extracts MorphoSource record IDs and URLs.
    """
    print(f"[parse_morphosource_urls] Reading file: {file_path}")
    # Updated pattern to match the new format
    pattern = r'New Record #(\d+).*?Detail Page URL: (https:\/\/www\.morphosource\.org\/concern\/media\/\d+\?locale=en)'
    results = []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        print("[parse_morphosource_urls] File content loaded. Searching for matches...")
        # Make the search multiline and dotall to match across line breaks
        matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
        for record_id, url in matches:
            results.append((record_id.strip(), url.strip()))

    print(f"[parse_morphosource_urls] Found {len(results)} record(s).")
    return results

def take_fullscreen_screenshot(driver, url, output_path):
    """
    Navigates to the given MorphoSource URL, switches to the uv-iframe,
    clicks fullscreen, waits, then saves a screenshot to output_path.
    """
    print(f"[take_fullscreen_screenshot] Navigating to {url}")
    driver.get(url)
    driver.maximize_window()

    wait = WebDriverWait(driver, 20)
    
    # Switch to iframe (if present)
    print("[take_fullscreen_screenshot] Waiting for uv-iframe to appear...")
    uv_iframe = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
    )
    driver.switch_to.frame(uv_iframe)
    print("[take_fullscreen_screenshot] Switched to uv-iframe.")

    # Click Full Screen
    print("[take_fullscreen_screenshot] Looking for Full Screen button...")
    full_screen_btn = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
    )
    print("[take_fullscreen_screenshot] Full Screen button is clickable. Clicking now...")
    full_screen_btn.click()

    # Let the fullscreen load. 15s is just an example; adjust as needed.
    print("[take_fullscreen_screenshot] Waiting 15 seconds in fullscreen mode...")
    time.sleep(15)

    print(f"[take_fullscreen_screenshot] Saving screenshot to {output_path}")
    driver.save_screenshot(output_path)
    print("[take_fullscreen_screenshot] Screenshot saved.")

def main():
    print("=== Starting selenium_screenshot.py ===")

    if len(sys.argv) < 2:
        print("Usage: python selenium_screenshot.py <release_body.txt>")
        sys.exit(1)

    release_body_file = sys.argv[1]
    print(f"Release body file provided: {release_body_file}")

    # 1. Parse the release body for (record_id, url) pairs
    records = parse_morphosource_urls(release_body_file)
    if not records:
        print("No MorphoSource URLs found in the release body. Exiting.")
        sys.exit(0)

    print(f"Preparing to capture screenshots for {len(records)} record(s)...")

    # 2. Make sure screenshots folder exists
    os.makedirs("screenshots", exist_ok=True)
    print("Created/ensured 'screenshots' folder exists.")

    # 3. Configure Selenium WebDriver (headless Chrome)
    print("Configuring Selenium WebDriver for headless Chrome...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')  # Added for consistent resolution
    
    driver = webdriver.Chrome(options=options)
    print("WebDriver initialization complete.")

    try:
        for idx, (record_id, url) in enumerate(records, start=1):
            print(f"\n[{idx}/{len(records)}] Capturing screenshot for Record #{record_id} -> {url}")
            screenshot_name = f"screenshots/{record_id}.png"
            take_fullscreen_screenshot(driver, url, screenshot_name)
            
            # Switch back out of iframe for the next iteration
            print("[main] Switching back to default content...")
            driver.switch_to.default_content()
            print(f"[main] Done with Record #{record_id}")

    except Exception as e:
        print(f"ERROR occurred while capturing screenshots: {e}")
        driver.quit()
        sys.exit(1)

    finally:
        print("Closing WebDriver...")
        driver.quit()
        print("WebDriver closed successfully.")

    print("=== Finished selenium_screenshot.py ===")

if __name__ == "__main__":
    main()
