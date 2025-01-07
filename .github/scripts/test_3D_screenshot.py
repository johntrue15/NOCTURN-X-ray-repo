from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import time
import sys
import re
import traceback
from datetime import datetime

def extract_id_from_url(url):
    """Extract the media ID from a MorphoSource URL"""
    # Try to match the ID pattern in the URL
    patterns = [
        r'/media/(\d+)',  # matches /media/123
        r'/media/0*(\d+)',  # matches /media/000123
        r'media/0*(\d+)\?',  # matches media/000123?locale=en
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # If no pattern matches, extract any numeric sequence as fallback
    numbers = re.findall(r'\d+', url)
    if numbers:
        return numbers[0]
        
    return 'unknown'

def setup_driver():
    """Configure and return a Chrome WebDriver instance"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--use-gl=swiftshader')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-gpu-driver-bug-workarounds')
    chrome_options.add_argument('--ignore-gpu-blocklist')
    chrome_options.add_argument('--window-size=1920,1080')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    driver.implicitly_wait(20)
    
    return driver

def process_url(url):
    """Process a single URL and take screenshots"""
    driver = None
    start_time = datetime.now()
    file_id = extract_id_from_url(url)
    
    print(f"Extracted ID: {file_id}")
    
    try:
        print(f"\nProcessing ID: {file_id}")
        print(f"URL: {url}")
        
        driver = setup_driver()
        wait = WebDriverWait(driver, 30)
        actions = ActionChains(driver)
        
        # Load page
        print("Loading page...")
        driver.get(url)
        
        # Take initial screenshot for debugging
        driver.save_screenshot(f"initial_{file_id}.png")
        
        # First look for the 3D viewer iframe
        print("Looking for 3D viewer iframe...")
        viewer_url = None
        try:
            iframe = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
            )
            viewer_url = iframe.get_attribute('src')
            print(f"Found viewer URL: {viewer_url}")
            
            # Switch to iframe
            driver.switch_to.frame(iframe)
            time.sleep(5)  # Wait for iframe content to load
            
            # Take post-iframe screenshot for debugging
            driver.save_screenshot(f"iframe_{file_id}.png")
        except Exception as e:
            print(f"Error with iframe: {str(e)}")
            if driver:
                driver.save_screenshot(f"iframe_error_{file_id}.png")
            raise
        
        # Enter fullscreen
        try:
            print("Entering fullscreen...")
            full_screen_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
            )
            full_screen_btn.click()
            time.sleep(5)
        except Exception as e:
            print(f"Error entering fullscreen: {str(e)}")
            if driver:
                driver.save_screenshot(f"fullscreen_error_{file_id}.png")
            raise
        
        # Expand controls if needed
        try:
            print("Expanding controls...")
            expand_button = driver.find_element(By.CSS_SELECTOR, '.expandButton[title="Expand Contents"]')
            if expand_button.is_displayed():
                actions.move_to_element(expand_button).click().perform()
                time.sleep(2)
        except Exception as e:
            print(f"Note: Could not expand controls: {str(e)}")
        
        # Take screenshots for each orientation
        orientations = [
            'Default (Y+ Up)',
            'Upside Down (Y- Up)',
            'Forward 90° (Z- Up)',
            'Back 90° (Z+ Up)'
        ]
        
        for orientation in orientations:
            try:
                print(f"\nProcessing orientation: {orientation}")
                if set_orientation(driver, actions, orientation):
                    filename = f"{file_id}_{orientation.replace(' ', '_').replace('(', '').replace(')', '').replace('+', 'plus').replace('°', '')}.png"
                    driver.save_screenshot(filename)
                    print(f"Saved screenshot: {filename}")
                time.sleep(3)
            except Exception as e:
                print(f"Error processing orientation {orientation}: {str(e)}")
                if driver:
                    driver.save_screenshot(f"orientation_error_{file_id}_{orientation}.png")
        
        return True
        
    except Exception as e:
        print(f"Error processing URL: {str(e)}")
        traceback.print_exc()
        if driver:
            try:
                error_file = f"error_{file_id}.png"
                driver.save_screenshot(error_file)
                print(f"Error screenshot saved as {error_file}")
                
                with open(f"error_{file_id}.txt", 'w') as f:
                    f.write(f"Error processing URL: {url}\n")
                    f.write(f"Error message: {str(e)}\n")
                    f.write(f"Traceback:\n{traceback.format_exc()}")
            except:
                print("Could not save error files")
        return False
        
    finally:
        if driver:
            driver.quit()
        duration = datetime.now() - start_time
        print(f"Processing time: {duration}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python screenshot_test.py <url_file>")
        sys.exit(1)
    
    try:
        with open(sys.argv[1], 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        print(f"Found {len(urls)} URLs to process")
        
        success_count = 0
        for i, url in enumerate(urls, 1):
            print(f"\nProcessing URL {i}/{len(urls)}")
            if process_url(url):
                success_count += 1
        
        print(f"\nProcessing complete")
        print(f"Successfully processed: {success_count}/{len(urls)}")
        
        if success_count != len(urls):
            sys.exit(1)
            
    except Exception as e:
        print(f"Error reading URL file: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
