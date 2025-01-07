from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys 
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import re
import sys
import time

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--window-size=1920,1080')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)

    return driver

def extract_id_from_url(url):
    match = re.search(r'(\d+)$', url)
    return match.group(1) if match else 'unknown'

def set_orientation(driver, actions, orientation):
    """Set the orientation to the specified value and take a screenshot"""
    try:
        print(f"\nSetting orientation to: {orientation}")
        
        # Find the combobox
        orientation_label = driver.find_element(By.XPATH, "//label[text()='Orientation']")
        if not orientation_label:
            print("Could not find orientation label")
            return False
            
        parent_div = orientation_label.find_element(By.XPATH, "./ancestor::div[contains(@class, 'grid gap-4')]")
        if not parent_div:
            print("Could not find parent div")
            return False
            
        combobox = parent_div.find_element(By.CSS_SELECTOR, 'button[role="combobox"]')
        if not combobox:
            print("Could not find combobox")
            return False

        # Open dropdown
        print("Opening dropdown...")
        actions.move_to_element(combobox)
        actions.click()
        actions.perform()
        time.sleep(1)
        
        # Verify dropdown is open
        is_expanded = driver.execute_script("""
            const btn = document.querySelector('button[role="combobox"]');
            return btn && btn.getAttribute('aria-expanded') === 'true';
        """)
        
        if not is_expanded:
            print("Dropdown did not open, trying alternative methods...")
            actions.move_to_element(combobox)
            actions.click_and_hold()
            actions.pause(1)
            actions.release()
            actions.perform()
            time.sleep(1)

            actions.move_to_element(combobox)
            actions.click()
            actions.send_keys(Keys.ARROW_DOWN)
            actions.perform()
            time.sleep(1)
        
        # Look for and click the specified option
        try:
            option = driver.find_element(By.XPATH, f"//*[contains(text(), '{orientation}')]")
            if option:
                print(f"Found {orientation} option")
                actions.move_to_element(option)
                actions.click()
                actions.perform()
                time.sleep(2)  # Wait for view to update
                return True
        except Exception as e:
            print(f"Failed to find or click option: {str(e)}")
            return False

        return False
        
    except Exception as e:
        print(f"Error setting orientation: {str(e)}")
        return False

def take_screenshot(url):
    file_id = extract_id_from_url(url)
    orientations = [
        'Default (Y+ Up)',
        'Upside Down (Y- Up)',
        'Forward 90° (Z- Up)',
        'Back 90° (Z+ Up)'
    ]
    
    driver = None
    try:
        driver = setup_driver()
        driver.maximize_window()
        print(f"\nProcessing ID {file_id}")
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
        time.sleep(2)

        # Click expand button
        print("\nExpanding controls...")
        expand_button = driver.find_element(By.CSS_SELECTOR, '.expandButton[title="Expand Contents"]')
        actions = ActionChains(driver)
        if expand_button and expand_button.is_displayed():
            print("Clicking expand button...")
            actions.move_to_element(expand_button)
            actions.click()
            actions.perform()
            time.sleep(2)
        
        # Cycle through orientations and take screenshots
        successful_orientations = 0
        for orientation in orientations:
            if set_orientation(driver, actions, orientation):
                # Take screenshot
                screenshot_file = f"{file_id}_{orientation.replace(' ', '_').replace('(', '').replace(')', '').replace('+', 'plus').replace('°', '')}.png"
                try:
                    print(f"Taking screenshot for {orientation}...")
                    driver.save_screenshot(screenshot_file)
                    print(f"Saved {screenshot_file}")
                    successful_orientations += 1
                except Exception as e:
                    print(f"Error saving screenshot: {str(e)}")
            time.sleep(2)

        return successful_orientations == len(orientations)

    except Exception as e:
        print(f"Error processing URL: {str(e)}")
        if driver:
            try:
                error_file = f"error_{file_id}.png"
                driver.save_screenshot(error_file)
                print(f"Error screenshot saved as {error_file}")
            except:
                print("Could not save error screenshot")
        return False
    finally:
        if driver:
            driver.quit()

def process_urls_from_file(input_file):
    try:
        print(f"\nReading file: {input_file}")
        with open(input_file, 'r') as f:
            content = f.read().strip()
        
        print(f"\nFile contents:")
        print("-------------------")
        print(content)
        print("-------------------")
        print(f"File length: {len(content)} characters")

        urls = re.findall(r'https://www\.morphosource\.org/concern/media/\d+', content)

        if not urls:
            print("\nURL matching results:")
            print("- No valid MorphoSource URLs found in file")
            print("- Pattern searching for: https://www.morphosource.org/concern/media/\\d+")
            return

        print(f"\nFound {len(urls)} MorphoSource URLs in file:")
        for i, url in enumerate(urls, 1):
            print(f"{i}. {url}")

        successful_screenshots = 0

        for i, url in enumerate(urls, 1):
            print(f"\nProcessing URL {i}/{len(urls)}: {url}")
            if take_screenshot(url):
                successful_screenshots += 1

        print(f"\nScreenshot process complete")
        print(f"Successfully processed {successful_screenshots} out of {len(urls)} URLs")

        if successful_screenshots != len(urls):
            sys.exit(1)

    except Exception as e:
        print(f"Error reading file: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error details: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <input_file>")
        sys.exit(1)

    process_urls_from_file(sys.argv[1])
