from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import time
import sys
import re
import traceback
from datetime import datetime

def setup_driver():
    """Configure and return a Chrome WebDriver instance"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--use-gl=swiftshader')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--disable-gpu-driver-bug-workarounds')
    chrome_options.add_argument('--ignore-gpu-blocklist')
    chrome_options.add_argument('--window-size=1920,1080')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(60)
    driver.implicitly_wait(20)
    
    return driver

def wait_for_model_load(driver, wait):
    """Wait for the 3D model to be fully loaded"""
    try:
        # Wait for canvas
        canvas = wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "canvas"))
        )
        
        # Check if WebGL is available
        webgl_ready = driver.execute_script("""
            const canvas = document.querySelector('canvas');
            if (!canvas) return false;
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            return gl !== null;
        """)
        
        if not webgl_ready:
            print("Warning: WebGL context not available")
            return False
        
        # Additional wait for model rendering
        time.sleep(5)
        return True
        
    except Exception as e:
        print(f"Error waiting for model load: {str(e)}")
        return False

def set_orientation(driver, actions, orientation):
    """Set the model orientation"""
    try:
        print(f"\nSetting orientation to: {orientation}")
        
        # Find orientation controls
        orientation_label = driver.find_element(By.XPATH, "//label[text()='Orientation']")
        parent_div = orientation_label.find_element(By.XPATH, "./ancestor::div[contains(@class, 'grid gap-4')]")
        combobox = parent_div.find_element(By.CSS_SELECTOR, 'button[role="combobox"]')
        
        # Open dropdown
        actions.move_to_element(combobox).click().perform()
        time.sleep(2)
        
        # Select orientation
        option = driver.find_element(By.XPATH, f"//*[contains(text(), '{orientation}')]")
        actions.move_to_element(option).click().perform()
        time.sleep(5)  # Wait for view update
        
        return True
        
    except Exception as e:
        print(f"Error setting orientation: {str(e)}")
        return False

def process_url(url):
    """Process a single URL and take screenshots"""
    driver = None
    start_time = datetime.now()
    
    try:
        file_id = re.search(r'/(\d+)$', url).group(1)
        print(f"\nProcessing ID: {file_id}")
        print(f"URL: {url}")
        
        driver = setup_driver()
        wait = WebDriverWait(driver, 30)
        actions = ActionChains(driver)
        
        # Load page and wait for iframe
        driver.get(url)
        iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(iframe)
        
        # Wait for model to load
        if not wait_for_model_load(driver, wait):
            raise Exception("Model failed to load")
        
        # Enter fullscreen
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        time.sleep(3)
        
        # Expand controls if needed
        try:
            expand_button = driver.find_element(By.CSS_SELECTOR, '.expandButton[title="Expand Contents"]')
            if expand_button.is_displayed():
                actions.move_to_element(expand_button).click().perform()
                time.sleep(2)
        except:
            pass
        
        # Take screenshots for each orientation
        orientations = [
            'Default (Y+ Up)',
            'Upside Down (Y- Up)',
            'Forward 90° (Z- Up)',
            'Back 90° (Z+ Up)'
        ]
        
        for orientation in orientations:
            if set_orientation(driver, actions, orientation):
                filename = f"{file_id}_{orientation.replace(' ', '_').replace('(', '').replace(')', '').replace('+', 'plus').replace('°', '')}.png"
                driver.save_screenshot(filename)
                print(f"Saved screenshot: {filename}")
            time.sleep(2)
        
        return True
        
    except Exception as e:
        print(f"Error processing URL: {str(e)}")
        traceback.print_exc()
        if driver:
            try:
                error_file = f"error_{file_id if 'file_id' in locals() else 'unknown'}.png"
                driver.save_screenshot(error_file)
                print(f"Error screenshot saved as {error_file}")
                
                with open(f"error_{file_id if 'file_id' in locals() else 'unknown'}.txt", 'w') as f:
                    f.write(f"Error processing URL: {url}\n")
                    f.write(f"Error message: {str(e)}\n")
                    f.write(f"Traceback:\n{traceback.format_exc()}")
            except:
                print("Could not save error files")
        return False
        
    finally:
        if driver:
            driver.quit()
        duration = datetime.now() - start_time
        print(f"Processing time: {duration}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python screenshot_test.py <url_file>")
        sys.exit(1)
    
    try:
        with open(sys.argv[1], 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        print(f"Found {len(urls)} URLs to process")
        
        success_count = 0
        for i, url in enumerate(urls, 1):
            print(f"\nProcessing URL {i}/{len(urls)}")
            if process_url(url):
                success_count += 1
        
        print(f"\nProcessing complete")
        print(f"Successfully processed: {success_count}/{len(urls)}")
        
        if success_count != len(urls):
            sys.exit(1)
            
    except Exception as e:
        print(f"Error reading URL file: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
