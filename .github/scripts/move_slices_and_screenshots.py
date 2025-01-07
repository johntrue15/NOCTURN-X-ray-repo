#!/usr/bin/env python3

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os

def move_slices_and_screenshots():
    """
    1. Goes to a MorphoSource page (currently 000695203).
    2. Switches into uv-iframe and clicks Full Screen.
    3. Locates <al-control-panel> and then <al-settings> in its shadow root.
    4. Loops slices-index from 0.1..0.9.
       - At each step, sets slices-index
       - Takes a screenshot: slice_<val>.png
    """

    # Chrome setup
    options = webdriver.ChromeOptions()

    # >>> IMPORTANT for GitHub Actions (headless) <<<
    options.add_argument("--headless")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)

    # Create a "screenshots" directory if it doesn't exist
    screenshots_dir = "screenshots"
    if not os.path.exists(screenshots_dir):
        os.makedirs(screenshots_dir)

    try:
        # 1. Navigate
        driver.get("https://www.morphosource.org/concern/media/000699452")
        driver.maximize_window()

        # 2. Switch into the uv-iframe
        wait = WebDriverWait(driver, 20)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)

        # Click the Full Screen button
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()

        # Give the viewer time to load fully in fullscreen
        time.sleep(360)

        # Locate <al-control-panel> in the DOM
        host_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "al-control-panel"))
        )
        print("Found <al-control-panel> (the shadow host).")

        # Get <al-settings> directly via JS from the shadow root
        al_settings = driver.execute_script(
            "return arguments[0].shadowRoot.querySelector('al-settings')",
            host_element
        )
        if not al_settings:
            print("No <al-settings> found in the shadow root.")
            return
        print("Found <al-settings>!")

        # 3. Loop from slices-index=0.1..0.9
        #slice_values = [round(i * 0.01, 2) for i in range(1, 100)]
        slice_values = [round(i * 0.1, 1) for i in range(1, 10)]
        for val in slice_values:
            # Set slices-index
            driver.execute_script(
                "arguments[0].setAttribute('slices-index', arguments[1])",
                al_settings,
                str(val)
            )
            print(f"Set slices-index to {val}")

            # Take a screenshot
            screenshot_name = os.path.join(screenshots_dir, f"slice_{val}.png")
            driver.save_screenshot(screenshot_name)
            print(f"Screenshot saved as {screenshot_name}")

            time.sleep(2)  # short pause to observe changes

        # 4. Optional final screenshot after entire loop
        final_screenshot = os.path.join(screenshots_dir, "move_slices.png")
        driver.save_screenshot(final_screenshot)
        print(f"Final screenshot saved as {final_screenshot}")

        # Wait briefly
        time.sleep(2)

    finally:
        driver.quit()

if __name__ == "__main__":
    move_slices_and_screenshots()
