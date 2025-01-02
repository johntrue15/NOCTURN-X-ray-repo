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
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    return driver

def take_screenshot(url, output_file="fullscreen_screenshot.png"):
    driver = None
    try:
        driver = setup_driver()
        driver.maximize_window()
        
        print(f"Loading URL: {url}")
        driver.get(url)
        
        wait = WebDriverWait(driver, 5)
        print("Looking for iframe...")
        uv_iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe")))
        
        print("Switching to iframe...")
        driver.switch_to.frame(uv_iframe)
        
        print("Looking for fullscreen button...")
        full_screen_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen")))
        full_screen_btn.click()

        time.sleep(30) #need to make longer to accomodate load, eventually dynamic (PULL REQUEST)
        print("Taking screenshot...")
        driver.save_screenshot(output_file)
        print(f"Screenshot saved to {output_file}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        if driver:
            driver.save_screenshot("error_screenshot.png")
            print("Error screenshot saved")
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
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
