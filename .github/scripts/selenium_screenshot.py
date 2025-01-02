# .github/scripts/selenium_screenshot.py
import sys
import re
import os
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def parse_morphosource_urls(file_path):
    """
    Example parser: Looks for lines like:
        Record #34986: https://www.morphosource.org/concern/media/000034986?locale=en
    Adjust this regex/logic to your actual release body format.
    Returns list of (record_id, url).
    """
    pattern = r'Record\s*#(\d+).*?(https:\/\/www\.morphosource\.org\/concern\/media\/\d+\?locale=en)'
    results = []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        matches = re.findall(pattern, content)
        for record_id, url in matches:
            results.append((record_id.strip(), url.strip()))
    return results

def take_fullscreen_screenshot(driver, url, output_path):
    """
    Navigates to the given MorphoSource URL, switches to the uv-iframe,
    clicks fullscreen, waits, then saves a screenshot to output_path.
    """
    driver.get(url)
    driver.maximize_window()

    wait = WebDriverWait(driver, 20)
    # Switch to iframe (if present)
    uv_iframe = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
    )
    driver.switch_to.frame(uv_iframe)

    # Click Full Screen
    full_screen_btn = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
    )
    full_screen_btn.click()

    # Let the fullscreen load.  Adjust as needed (112s is quite long; you might reduce it)
    time.sleep(15)

    driver.save_screenshot(output_path)

def main():
    if len(sys.argv) < 2:
        print("Usage: python selenium_screenshot.py <release_body.txt>")
        sys.exit(1)

    release_body_file = sys.argv[1]

    # 1. Parse the release body for (record_id, url) pairs
    records = parse_morphosource_urls(release_body_file)
    if not records:
        print("No MorphoSource URLs found in the release body.")
        sys.exit(0)

    # 2. Make sure screenshots folder exists
    os.makedirs("screenshots", exist_ok=True)

    # 3. Configure Selenium WebDriver (headless Chrome)
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)

    try:
        for record_id, url in records:
            screenshot_name = f"screenshots/{record_id}.png"
            print(f"Capturing screenshot for Record #{record_id} -> {url}")
            take_fullscreen_screenshot(driver, url, screenshot_name)
            print(f"Saved screenshot: {screenshot_name}")
            # Switch back out of iframe for the next iteration
            driver.switch_to.default_content()

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
