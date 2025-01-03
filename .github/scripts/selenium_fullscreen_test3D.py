# selenium_fullscreen_test3D.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import os

def test_fullscreen_screenshot():
    # 1. Configure ChromeOptions
    options = webdriver.ChromeOptions()
    # Comment out headless if you want to see the browser UI
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    # Set an explicit window size to ensure the screenshot works in headless mode
    #options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(options=options)

    # Increase page load and script timeouts to avoid renderer timeout
    driver.set_page_load_timeout(30)     # extends the time to load a page
    driver.set_script_timeout(30)        # extends the time for scripts to finish

    try:
        # 2. Go to the MorphoSource page
        driver.get("https://www.morphosource.org/concern/media/000699150")
        driver.maximize_window()

        # 3. Wait until the uv-iframe is available, then switch into it
        wait = WebDriverWait(driver, 20)  # extend the wait to 20s
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)

        # 4. Click the Full Screen button
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()

        # 5. Wait a bit longer for the fullscreen animation
        time.sleep(660)

        # 6. Attempt to take a screenshot and save it
        screenshot_name = "fullscreen_screenshot_3D.png"
        try:
            driver.save_screenshot(screenshot_name)
        except TimeoutException:
            # If screenshot fails initially, wait and retry
            print("Initial screenshot timed out, retrying after short wait...")
            time.sleep(5)
            driver.save_screenshot(screenshot_name)

        print(f"Screenshot saved as {screenshot_name}")

        # 7. Pause briefly (optional observation)
        time.sleep(3)

    finally:
        # 8. Quit the browser
        driver.quit()

# If you want to run this script directly (e.g., `python selenium_fullscreen_test3D.py`),
# include this:
if __name__ == "__main__":
    test_fullscreen_screenshot()
