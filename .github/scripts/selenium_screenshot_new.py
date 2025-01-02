from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import sys

def test_fullscreen_screenshot(url):
    print(f"Debug - Received URL type: {type(url)}")
    print(f"Debug - URL content: |{url}|")

    # 1. Launch the browser
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    
    try:
        print(f"Debug - Attempting to load URL: |{url}|")
        driver.get(url)
        driver.maximize_window()
        
        # 3. Wait until the uv-iframe is available
        wait = WebDriverWait(driver, 5)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)
        
        # 4. Click the Full Screen button
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        
        # 5. Wait for fullscreen
        time.sleep(12)
        
        # 6. Take screenshot
        screenshot_name = "fullscreen_screenshot.png"
        driver.save_screenshot(screenshot_name)
        print(f"Screenshot saved as {screenshot_name}")
        
        time.sleep(3)
        
    except Exception as e:
        print(f"Error during screenshot process: {str(e)}")
        raise
    finally:
        driver.quit()

if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            print("Usage: python selenium_screenshot_new.py <url_file>")
            sys.exit(1)
        
        # Read and debug URL from file
        with open(sys.argv[1], 'r') as file:
            url = file.read().strip()
        
        print(f"Debug - URL from file type: {type(url)}")
        print(f"Debug - URL from file content: |{url}|")
            
        if not url:
            print("Error: URL file is empty")
            sys.exit(1)
            
        test_fullscreen_screenshot(url)
        
    except Exception as e:
        print(f"Error in main: {str(e)}")
        sys.exit(1)
