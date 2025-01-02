#https://claude.ai/chat/7e5795ce-34c7-4311-b301-22950dc5435c

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import time
import sys
import re

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    return driver

def extract_id_from_url(url):
    # Extract the last digits from the URL
    match = re.search(r'(\d+)$', url)
    return match.group(1) if match else 'unknown'

def take_screenshot(url):
    driver = None
    file_id = extract_id_from_url(url)
    output_file = f"{file_id}.png"
    error_file = f"error_{file_id}.png"
    
    try:
        driver = setup_driver()
        driver.maximize_window()
        
        print(f"\nProcessing URL for ID {file_id}")
        print(f"Loading URL: {url}")
        driver.get(url)
        
        wait = WebDriverWait(driver, 5)
        print("Looking for iframe...")
        uv_iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe")))
        
        print("Switching to iframe...")
        driver.switch_to.frame(uv_iframe)
        
        print("Starting fullscreen click loop...")
        start_time = time.time()
        
        while time.time() - start_time < 20:  # Run for 20 seconds
            try:
                full_screen_btn = driver.find_element(By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen")
                full_screen_btn.click()
                print("Clicked fullscreen button")
            except:
                print("Button click attempt")
                
            try:
                # Check if fullscreen exists
                driver.find_element(By.CSS_SELECTOR, "div.image.fullscreen")
                print("Fullscreen detected")
            except:
                pass
                
        print("Taking screenshot...")
        driver.save_screenshot(output_file)
        print(f"Screenshot saved to {output_file}")
        return True
        
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        if driver:
            driver.save_screenshot(error_file)
            print(f"Error screenshot saved as {error_file}")
        return False
        
    finally:
        if driver:
            driver.quit()

def process_urls_from_file(input_file):
    try:
        with open(input_file, 'r') as f:
            content = f.read().strip()
            
        # Extract URLs using regex
        urls = re.findall(r'https://www\.morphosource\.org/concern/media/\d+', content)
        
        if not urls:
            print("No valid MorphoSource URLs found in file")
            return
        
        print(f"Found {len(urls)} MorphoSource URLs in file")
        successful_screenshots = 0
        
        for i, url in enumerate(urls, 1):
            print(f"\nProcessing URL {i}/{len(urls)}: {url}")
            if take_screenshot(url):
                successful_screenshots += 1
        
        print(f"\nScreenshot process complete")
        print(f"Successfully captured {successful_screenshots} out of {len(urls)} screenshots")
        
        if successful_screenshots != len(urls):
            sys.exit(1)
            
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <input_file>")
        sys.exit(1)
    
    process_urls_from_file(sys.argv[1])
