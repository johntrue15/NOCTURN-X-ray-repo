#https://claude.ai/chat/7e5795ce-34c7-4311-b301-22950dc5435c

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import re
import sys

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')  # Helpful in headless
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--window-size=1920,1080')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Increase page load timeout and set implicit wait
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)

    return driver

def extract_id_from_url(url):
    match = re.search(r'(\d+)$', url)
    return match.group(1) if match else 'unknown'

def take_screenshot(url):
    file_id = extract_id_from_url(url)
    output_file = f"{file_id}.png"
    error_file = f"error_{file_id}.png"
    max_retries = 3

    for attempt in range(max_retries):
        driver = None
        try:
            driver = setup_driver()
            driver.maximize_window()
            print(f"\nAttempt {attempt + 1}/{max_retries} for ID {file_id}")
            print(f"Loading URL: {url}")
            driver.get(url)

            # Wait for iframe and switch
            wait = WebDriverWait(driver, 10)
            uv_iframe = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
            )

            driver.switch_to.frame(uv_iframe)

            # Wait for fullscreen button and click
            full_screen_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
            )
            full_screen_btn.click()

            print("Taking screenshot...")
            driver.save_screenshot(output_file)
            print(f"Screenshot saved to {output_file}")
            return True

        except Exception as e:
            print(f"Error on attempt {attempt + 1}: {str(e)}")
            if "timeout: Timed out receiving message from renderer" in str(e):
                print("Renderer timeout detected, retrying with fresh driver...")
                if driver:
                    try:
                        driver.save_screenshot(f"error_{file_id}_attempt_{attempt + 1}.png")
                        print(f"Error screenshot saved for attempt {attempt + 1}")
                    except:
                        print("Could not save error screenshot")
                    driver.quit()
                continue
            else:
                if driver:
                    driver.save_screenshot(error_file)
                    print(f"Error screenshot saved as {error_file}")
                break
        finally:
            if driver:
                driver.quit()

    return False

def process_urls_from_file(input_file):
    try:
        with open(input_file, 'r') as f:
            content = f.read().strip()

        # Extract MorphoSource URLs
        urls = re.findall(r'https://www\.morphosource\.org/concern/media/\d+', content)

        if not urls:
            print("No valid MorphoSource URLs found in file")
            return

        print(f"Found {len(urls)} MorphoSource URLs in file")
        successful_screenshots = 0

        for i, url in enumerate(urls, 1):
            print(f"\nProcessing URL {i}/{len(urls)}: {url}")
            if take_screenshot(url):
                successful_screenshots += 1

        print(f"\nScreenshot process complete")
        print(f"Successfully captured {successful_screenshots} out of {len(urls)} screenshots")

        if successful_screenshots != len(urls):
            sys.exit(1)

    except Exception as e:
        print(f"Error reading file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <input_file>")
        sys.exit(1)

    process_urls_from_file(sys.argv[1])
