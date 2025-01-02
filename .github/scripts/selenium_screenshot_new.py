from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import sys

def test_fullscreen_screenshot(url):
    print(f"Loading URL: {url}")
    
    # 1. Launch the browser with modified options
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')  # Use new headless mode
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--remote-debugging-port=9222')  # Enable debugging
    options.add_argument('--disable-gpu')  # Disable GPU usage
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    try:
        # Setup service with increased startup timeout
        service = Service(ChromeDriverManager().install())
        service.start()  # Start service explicitly
        
        # Create driver with the running service
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        
        print(f"Attempting to load URL...")
        driver.get(url)
        driver.maximize_window()
        
        wait = WebDriverWait(driver, 5)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)
        
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        
        time.sleep(12)
        
        screenshot_name = "fullscreen_screenshot.png"
        driver.save_screenshot(screenshot_name)
        print(f"Screenshot saved as {screenshot_name}")
        
        time.sleep(3)
        
    except Exception as e:
        print(f"Error during screenshot process: {str(e)}")
        raise
    finally:
        if 'driver' in locals():
            driver.quit()
        if 'service' in locals():
            service.stop()  # Explicitly stop the service

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python selenium_screenshot_new.py <url_file>")
        sys.exit(1)
    
    try:
        with open(sys.argv[1], 'r') as file:
            url = file.read().strip()
            
        if not url:
            print("Error: URL file is empty")
            sys.exit(1)
            
        print(f"URL from file: {url}")
        test_fullscreen_screenshot(url)
        
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        sys.exit(1)
