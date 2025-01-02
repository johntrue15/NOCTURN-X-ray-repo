from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import sys

def test_fullscreen_screenshot(url):
    # Format URL with quotes
    formatted_url = f'"{url}"' if not url.startswith('"') else url
    print(f"Debug - Original URL: |{url}|")
    print(f"Debug - Formatted URL: |{formatted_url}|")

    # 1. Launch the browser
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    try:
        # First attempt with stripped quotes
        print("\nTrying with stripped quotes...")
        driver = webdriver.Chrome(options=options)
        try:
            print(f"Debug - Loading URL (stripped): |{formatted_url.strip('"')}|")
            driver.get(formatted_url.strip('"'))
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
            
            time.sleep(112)
            
            screenshot_name = "fullscreen_screenshot.png"
            driver.save_screenshot(screenshot_name)
            print(f"Screenshot saved as {screenshot_name}")
            
        except Exception as e:
            print(f"Error with stripped quotes: {str(e)}")
        finally:
            driver.quit()

        # Second attempt with quotes included
        print("\nTrying with quotes included...")
        driver = webdriver.Chrome(options=options)
        try:
            print(f"Debug - Loading URL (with quotes): |{formatted_url}|")
            driver.get(formatted_url)
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
            
            time.sleep(112)
            
            screenshot_name = "fullscreen_screenshot_with_quotes.png"
            driver.save_screenshot(screenshot_name)
            print(f"Screenshot saved as {screenshot_name}")
            
        except Exception as e:
            print(f"Error with quotes included: {str(e)}")
        finally:
            driver.quit()
            
    except Exception as e:
        print(f"Error during screenshot process: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            print("Usage: python selenium_screenshot_new.py <url_file>")
            sys.exit(1)
        
        with open(sys.argv[1], 'r') as file:
            url = file.read().strip()
        
        print(f"Debug - URL from file: |{url}|")
            
        if not url:
            print("Error: URL file is empty")
            sys.exit(1)
            
        test_fullscreen_screenshot(url)
        
    except Exception as e:
        print(f"Error in main: {str(e)}")
        sys.exit(1)
