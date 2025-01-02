from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import sys

def extract_url_from_file(filename):
    """Extract MorphoSource URL from the file."""
    with open(filename, 'r') as f:
        url = f.read().strip()
    print(f"Found MorphoSource URL: {url}")
    return url

def test_fullscreen_screenshot(url):
    # 1. Launch the browser (in headless mode with Chrome options if needed)
    options = webdriver.ChromeOptions()
    # Comment out headless if you want to see the browser UI
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=options)

    try:
        # 2. Go to the MorphoSource page
        driver.get(url)
        driver.maximize_window()

        # 3. Wait until the uv-iframe is available, then switch into it
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

        # 5. Wait a moment to let the fullscreen animation take effect
        time.sleep(112)

        # 6. Take a screenshot and save it
        screenshot_name = "fullscreen_screenshot.png"
        driver.save_screenshot(screenshot_name)
        print(f"Screenshot saved as {screenshot_name}")

        # 7. Pause briefly so you can observe the page (optional)
        time.sleep(3)

    finally:
        # 8. Quit the browser
        driver.quit()

# If you want to run this script directly
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python selenium_screenshot_new.py <release_body_file>")
        sys.exit(1)
    
    release_file = sys.argv[1]
    url = extract_url_from_file(release_file)
    test_fullscreen_screenshot(url)
