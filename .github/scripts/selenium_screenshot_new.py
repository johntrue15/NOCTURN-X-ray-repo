from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import sys

def test_fullscreen_screenshot(url):
    print(f"Loading URL: {url}")
    
    # 1. Enhanced Chrome options to handle renderer timeout
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--renderer-process-limit=1')
    options.add_argument('--single-process')
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    
    try:
        # 2. Load the page
        print(f"Attempting to load URL...")
        driver.get(url)
        driver.maximize_window()
        
        # 3. Wait for iframe with increased timeout
        wait = WebDriverWait(driver, 20)
        print("Waiting for iframe...")
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)
        
        # 4. Click fullscreen
        print("Looking for fullscreen button...")
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        print("Clicked fullscreen button")
        
        # 5. Wait for fullscreen
        print("Waiting for fullscreen animation...")
        time.sleep(12)
        
        # 6. Take screenshot
        screenshot_name = "fullscreen_screenshot.png"
        driver.save_screenshot(screenshot_name)
        print(f"Screenshot saved as {screenshot_name}")
        
    except Exception as e:
        print(f"Error during screenshot process: {str(e)}")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python selenium_screenshot_new.py <url_file>")
        sys.exit(1)
    
    with open(sys.argv[1], 'r') as file:
        url = file.read().strip()
        
    if not url:
        print("Error: URL file is empty")
        sys.exit(1)
    
    test_fullscreen_screenshot(url)
