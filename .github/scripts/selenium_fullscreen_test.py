# selenium_fullscreen_test.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os

def test_fullscreen_screenshot():
    # 1. Launch the browser (in headless mode with Chrome options if needed)
    options = webdriver.ChromeOptions()
    # Comment out headless if you want to see the browser UI
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=options)

    try:
        # 2. Go to the MorphoSource page
        driver.get("https://www.morphosource.org/concern/media/000034986?locale=en")
        driver.maximize_window()

        # 3. Wait until the uv-iframe is available, then switch into it
        wait = WebDriverWait(driver, 30)
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
        time.sleep(10)

        # 6. Take a screenshot and save it
        screenshot_name = "fullscreen_screenshot.png"
        driver.save_screenshot(screenshot_name)
        print(f"Screenshot saved as {screenshot_name}")

        # 7. Pause briefly so you can observe the page (optional)
        time.sleep(3)

    finally:
        # 8. Quit the browser
        driver.quit()

# If you want to run this script directly (e.g. python selenium_fullscreen_test.py),
# you can include this clause:
if __name__ == "__main__":
    test_fullscreen_screenshot()
