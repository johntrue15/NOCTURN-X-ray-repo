from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import time
import sys

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')  # Use new headless mode
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--renderer-process-limit=1')
    chrome_options.add_argument('--renderer-startup-dialog')
    chrome_options.add_argument('--timeout=60000') 
    
    # Keep browser open
    chrome_options.add_experimental_option("detach", True)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    
    return driver

def take_screenshot(url, output_file="fullscreen_screenshot.png"):
    driver = None
    try:
        print("Setting up Chrome driver...")
        driver = setup_driver()
        
        print(f"Loading URL: {url}")
        
        # Initial get with catch
        try:
            driver.get(url)
            print("Initial page load complete")
        except TimeoutException:
            print("Initial timeout - retrying with javascript")
            # Try to load with JavaScript as fallback
            driver.execute_script(f'window.location.href = "{url}";')
        
        # Wait for page to be ready
        print("Waiting for page to be ready...")
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )
        
        # Take initial screenshot for debugging
        print("Taking initial screenshot...")
        driver.save_screenshot("debug_initial.png")
        print("Initial screenshot saved")
        
        return True
        
    except Exception as e:
        print(f"Error during screenshot process: {str(e)}")
        if driver:
            try:
                print("Attempting to save error screenshot...")
                driver.save_screenshot("error_state.png")
                print("Error state screenshot saved")
            except Exception as se:
                print(f"Could not save error screenshot: {str(se)}")
        return False
    finally:
        if driver:
            try:
                print("Cleaning up driver...")
                driver.close()
                driver.quit()
                print("Driver cleanup complete")
            except Exception as e:
                print(f"Warning during driver cleanup: {str(e)}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <input_file>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    try:
        with open(input_file, 'r') as f:
            url = f.read().strip()
            print(f"URL from file: {url}")
            success = take_screenshot(url)
            if not success:
                sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
