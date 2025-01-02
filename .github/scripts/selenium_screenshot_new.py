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

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    # Increase various timeout settings
    chrome_options.add_argument('--browser-timeout=60000')
    chrome_options.add_argument('--page-load-timeout=60000')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Set page load timeout to 60 seconds
    driver.set_page_load_timeout(60)
    # Set script timeout to 60 seconds
    driver.set_script_timeout(60)
    
    return driver

def take_screenshot(url, output_file="fullscreen_screenshot.png"):
    driver = None
    try:
        print(f"Loading URL: {url}")
        driver = setup_driver()
        
        print("Attempting to load URL...")
        driver.get(url)
        
        # Wait for specific elements to be present (adjust selectors as needed)
        wait = WebDriverWait(driver, 60)  # 60 second timeout
        driver.maximize_window()
        
        # Wait for and switch to UV iframe
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)
        
        # Wait for and click the fullscreen button
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        
        # Additional wait to ensure page is fully loaded
        print("Waiting for page to stabilize...")
        time.sleep(10)  # Add an extra delay
        
        # Get page dimensions
        #total_height = driver.execute_script("return document.documentElement.scrollHeight")
        #total_width = driver.execute_script("return document.documentElement.scrollWidth")
        
        # Set viewport size
        #driver.set_window_size(total_width, total_height)
        
        # Additional wait after resizing
        time.sleep(5)
        
        #print(f"Taking screenshot (dimensions: {total_width}x{total_height})")
        driver.save_screenshot(output_file)
        print(f"Screenshot saved to {output_file}")
        
    except TimeoutException as e:
        print(f"Timeout while loading page: {str(e)}")
        if driver:
            print("Attempting to save partial screenshot...")
            try:
                driver.save_screenshot("timeout_partial_screenshot.png")
                print("Partial screenshot saved")
            except Exception as se:
                print(f"Could not save partial screenshot: {str(se)}")
        raise
    except Exception as e:
        print(f"Error during screenshot process: {str(e)}")
        raise
    finally:
        if driver:
            driver.quit()

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <input_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    try:
        with open(input_file, 'r') as f:
            url = f.read().strip()
            print(f"URL from file: {url}")
            take_screenshot(url)
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
