from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import sys
import re

def extract_url_from_release(release_file):
    """Extract single MorphoSource URL from the release body text file."""
    try:
        with open(release_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the first MorphoSource URL
        pattern = r'https://www\.morphosource\.org/concern/media/\d+'
        urls = re.findall(pattern, content)
        
        if urls:
            print(f"Found MorphoSource URL: {urls[0]}")
            return urls[0]
        else:
            print("No MorphoSource URL found in release body")
            return None
            
    except Exception as e:
        print(f"Error reading release file: {e}")
        return None

def take_morpho_screenshot(url):
    """Take a screenshot of a MorphoSource page."""
    # Set up Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=options)

    try:
        # Go to the MorphoSource page
        print(f"Navigating to URL: {url}")
        driver.get(url)
        driver.maximize_window()

        # Wait for UV iframe
        print("Waiting for UV iframe...")
        wait = WebDriverWait(driver, 5)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)

        # Click Full Screen button
        print("Clicking fullscreen button...")
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()

        # Wait for fullscreen animation
        print("Waiting for fullscreen transition...")
        time.sleep(112)  # Using the same timing that worked in the original script

        # Take screenshot
        screenshot_name = "fullscreen_screenshot.png"
        print(f"Taking screenshot: {screenshot_name}")
        driver.save_screenshot(screenshot_name)
        print(f"Screenshot saved as {screenshot_name}")

        return True

    except Exception as e:
        print(f"Error taking screenshot: {str(e)}")
        return False

    finally:
        driver.quit()

def main():
    if len(sys.argv) != 2:
        print("Usage: python selenium_screenshot_new.py <release_body_file>")
        sys.exit(1)
    
    release_file = sys.argv[1]
    url = extract_url_from_release(release_file)
    
    if not url:
        print("No URL found to process")
        sys.exit(1)
    
    success = take_morpho_screenshot(url)
    
    if not success:
        print("Failed to capture screenshot")
        sys.exit(1)
    
    print("Screenshot process completed successfully")

if __name__ == "__main__":
    main()
