from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
import os

def test_fullscreen_screenshot():
    # Set up Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    # Additional stable options for CI environment
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')

    try:
        # Initialize Chrome with webdriver-manager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        print("Starting screenshot process...")
        
        # Navigate to MorphoSource
        url = "https://www.morphosource.org/concern/media/000034986?locale=en"
        print(f"Navigating to: {url}")
        driver.get(url)
        driver.maximize_window()

        # Wait for and switch to the UV iframe
        print("Waiting for UV iframe...")
        wait = WebDriverWait(driver, 20)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)

        # Wait for and click the fullscreen button
        print("Clicking fullscreen button...")
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()

        # Wait for fullscreen transition
        print("Waiting for fullscreen transition...")
        time.sleep(3)

        # Take the screenshot
        screenshot_name = "fullscreen_screenshot.png"
        print(f"Taking screenshot: {screenshot_name}")
        driver.save_screenshot(screenshot_name)
        print(f"Screenshot saved successfully as {screenshot_name}")
        
        # Optional: verify the file exists and has size
        if os.path.exists(screenshot_name):
            size = os.path.getsize(screenshot_name)
            print(f"Screenshot file size: {size} bytes")
        else:
            print("Warning: Screenshot file not found!")

    except TimeoutException as e:
        print(f"Timeout error: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise
    finally:
        if 'driver' in locals():
            print("Closing Chrome...")
            driver.quit()

if __name__ == "__main__":
    test_fullscreen_screenshot()
