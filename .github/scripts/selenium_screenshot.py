import sys
import re
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service

def parse_morphosource_urls(file_path):
    """
    Reads the release body from file_path and extracts MorphoSource record IDs and URLs.
    """
    print(f"[parse_morphosource_urls] Reading file: {file_path}")
    pattern = r'New Record #(\d+).*?Detail Page URL: (https:\/\/www\.morphosource\.org\/concern\/media\/\d+\?locale=en)'
    results = []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        print("[parse_morphosource_urls] File content loaded. Searching for matches...")
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
    try:
        print(f"[take_fullscreen_screenshot] Navigating to {url}")
        driver.get(url)
        time.sleep(5)  # Wait for initial page load
        
        driver.maximize_window()
        print("[take_fullscreen_screenshot] Window maximized")
        
        # Set longer timeout for iframe
        wait = WebDriverWait(driver, 40)  # Increased timeout
        print("[take_fullscreen_screenshot] Waiting for uv-iframe to appear...")
        
        # Try multiple times to find the iframe
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                uv_iframe = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
                )
                print(f"[take_fullscreen_screenshot] Found iframe on attempt {attempt + 1}")
                break
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise
                print(f"Attempt {attempt + 1} failed, retrying...")
                time.sleep(5)
        
        driver.switch_to.frame(uv_iframe)
        print("[take_fullscreen_screenshot] Switched to uv-iframe")
        
        # Wait for the page to stabilize
        time.sleep(10)
        
        print("[take_fullscreen_screenshot] Looking for Full Screen button...")
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        
        # Multiple attempts for clicking fullscreen
        for attempt in range(max_attempts):
            try:
                print(f"[take_fullscreen_screenshot] Attempting to click fullscreen (attempt {attempt + 1})")
                full_screen_btn.click()
                break
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise
                time.sleep(5)
        
        print("[take_fullscreen_screenshot] Waiting in fullscreen mode...")
        time.sleep(20)  # Reduced wait time but added stability checks
        
        # Take multiple screenshots to ensure quality
        for i in range(3):
            screenshot_path = f"{output_path}_attempt_{i+1}.png"
            print(f"[take_fullscreen_screenshot] Saving screenshot attempt {i+1} to {screenshot_path}")
            driver.save_screenshot(screenshot_path)
            time.sleep(5)
        
        # Use the last screenshot as the final one
        if os.path.exists(f"{output_path}_attempt_3.png"):
            os.rename(f"{output_path}_attempt_3.png", output_path)
            print(f"[take_fullscreen_screenshot] Final screenshot saved as {output_path}")
            
        # Clean up temporary screenshots
        for i in range(2):
            temp_path = f"{output_path}_attempt_{i+1}.png"
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        print(f"[take_fullscreen_screenshot] Error during screenshot: {str(e)}")
        raise

def main():
    print("=== Starting selenium_screenshot.py ===")

    if len(sys.argv) < 2:
        print("Usage: python selenium_screenshot.py <release_body.txt>")
        sys.exit(1)

    release_body_file = sys.argv[1]
    print(f"Release body file provided: {release_body_file}")

    records = parse_morphosource_urls(release_body_file)
    if not records:
        print("No MorphoSource URLs found in the release body. Exiting.")
        sys.exit(0)

    print(f"Preparing to capture screenshots for {len(records)} record(s)...")

    os.makedirs("screenshots", exist_ok=True)
    print("Created/ensured 'screenshots' folder exists.")

    print("Configuring Selenium WebDriver for headless Chrome...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')  # Using new headless mode
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-web-security')
    options.add_argument('--enable-logging')
    options.add_argument('--v=1')
    options.binary_location = '/usr/bin/chromium-browser'

    # Set page load strategy
    options.set_capability('pageLoadStrategy', 'normal')
    
    service = Service()
    driver = webdriver.Chrome(service=service, options=options)
    print("WebDriver initialization complete.")

    try:
        for idx, (record_id, url) in enumerate(records, start=1):
            print(f"\n[{idx}/{len(records)}] Capturing screenshot for Record #{record_id} -> {url}")
            screenshot_name = f"screenshots/{record_id}.png"
            try:
                take_fullscreen_screenshot(driver, url, screenshot_name)
                print("[main] Switching back to default content...")
                driver.switch_to.default_content()
                print(f"[main] Done with Record #{record_id}")
            except Exception as e:
                print(f"Error processing record {record_id}: {str(e)}")
                continue  # Continue with next record even if one fails

    except Exception as e:
        print(f"ERROR occurred while capturing screenshots: {e}")
    finally:
        print("Closing WebDriver...")
        driver.quit()
        print("WebDriver closed successfully.")

    print("=== Finished selenium_screenshot.py ===")

if __name__ == "__main__":
    main()
