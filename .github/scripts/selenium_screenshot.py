from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import sys
import re

def extract_urls_from_release(release_file):
    """Extract MorphoSource URLs from the release body text file."""
    try:
        with open(release_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all MorphoSource URLs
        pattern = r'https://www\.morphosource\.org/concern/media/\d+'
        urls = re.findall(pattern, content)
        
        print(f"Found {len(urls)} MorphoSource URLs in release body")
        return urls
    except Exception as e:
        print(f"Error reading release file: {e}")
        return []

def take_screenshot(url, index):
    """Take a screenshot of a specific MorphoSource page."""
    # Set up Chrome options using the working configuration
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=options)
    
    try:
        print(f"\nProcessing URL {index + 1}: {url}")
        
        # Navigate to the page
        driver.get(url)
        driver.maximize_window()

        # Wait for and switch to the UV iframe
        wait = WebDriverWait(driver, 5)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)

        # Click the Full Screen button
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()

        # Wait for fullscreen animation
        time.sleep(3)

        # Take the screenshot
        screenshot_name = f"morphosource_{index + 1}.png"
        driver.save_screenshot(screenshot_name)
        print(f"Screenshot saved as {screenshot_name}")

        return True

    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        return False
        
    finally:
        driver.quit()

def main():
    if len(sys.argv) != 2:
        print("Usage: python selenium_screenshot.py <release_body_file>")
        sys.exit(1)
    
    release_file = sys.argv[1]
    urls = extract_urls_from_release(release_file)
    
    if not urls:
        print("No MorphoSource URLs found in release body")
        sys.exit(1)
    
    # Process each URL
    successful_screenshots = 0
    for index, url in enumerate(urls):
        if take_screenshot(url, index):
            successful_screenshots += 1
    
    print(f"\nScreenshot process complete")
    print(f"Successfully captured {successful_screenshots} out of {len(urls)} screenshots")
    
    # Exit with error if we didn't get all screenshots
    if successful_screenshots != len(urls):
        sys.exit(1)

if __name__ == "__main__":
    main()
