from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import os
import sys
import re

def setup_chrome_options():
    """Configure Chrome options for headless operation in CI environment."""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    return options

def extract_urls_from_release(release_file):
    """Extract MorphoSource URLs from the release body text file."""
    try:
        with open(release_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all MorphoSource URLs using regex
        pattern = r'https://www\.morphosource\.org/concern/media/\d+'
        urls = re.findall(pattern, content)
        
        print(f"Found {len(urls)} MorphoSource URLs in release body")
        return urls
    except Exception as e:
        print(f"Error reading release file: {e}")
        return []

def take_screenshot(driver, url, index):
    """Take a screenshot of a specific MorphoSource page."""
    try:
        print(f"\nProcessing URL {index + 1}: {url}")
        
        # Create screenshots directory if it doesn't exist
        os.makedirs('screenshots', exist_ok=True)
        
        # Navigate to the page
        driver.get(url)
        
        # Wait for the UV iframe to load
        wait = WebDriverWait(driver, 20)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        
        # Switch to the iframe
        driver.switch_to.frame(uv_iframe)
        
        # Wait for and click the full screen button
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        
        # Wait for fullscreen mode to take effect
        time.sleep(3)
        
        # Take the screenshot
        screenshot_path = f"screenshots/morphosource_{index + 1}.png"
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved: {screenshot_path}")
        
        # Switch back to default content for next iteration
        driver.switch_to.default_content()
        
        return True
    except TimeoutException as e:
        print(f"Timeout while processing {url}: {str(e)}")
        return False
    except WebDriverException as e:
        print(f"WebDriver error for {url}: {str(e)}")
        return False
    except Exception as e:
        print(f"Unexpected error processing {url}: {str(e)}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python selenium_screenshot.py <release_body_file>")
        sys.exit(1)
    
    release_file = sys.argv[1]
    urls = extract_urls_from_release(release_file)
    
    if not urls:
        print("No MorphoSource URLs found in release body")
        sys.exit(1)
    
    driver = None
    try:
        # Initialize the WebDriver with our options
        options = setup_chrome_options()
        driver = webdriver.Chrome(options=options)
        
        # Process each URL
        successful_screenshots = 0
        for index, url in enumerate(urls):
            if take_screenshot(driver, url, index):
                successful_screenshots += 1
        
        print(f"\nScreenshot process complete.")
        print(f"Successfully captured {successful_screenshots} out of {len(urls)} screenshots")
        
        # Exit with error if we didn't get all screenshots
        if successful_screenshots != len(urls):
            sys.exit(1)
            
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        sys.exit(1)
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
