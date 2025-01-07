# .github/scripts/ct_image_to_text.py

import sys
import os
import re
import time
import traceback
import logging
import base64
from datetime import datetime
from urllib3.exceptions import ReadTimeoutError
import urllib3
from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_driver(max_retries=3, retry_delay=5):
    """Configure and return a Chrome WebDriver instance with retry logic"""
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # WebGL and GPU settings
    chrome_options.add_argument('--use-angle=swiftshader')
    chrome_options.add_argument('--use-gl=angle')
    chrome_options.add_argument('--use-angle=gl')
    chrome_options.add_argument('--enable-webgl')
    chrome_options.add_argument('--enable-gpu-rasterization')
    chrome_options.add_argument('--enable-zero-copy')
    chrome_options.add_argument('--enable-features=VaapiVideoDecoder')
    chrome_options.add_argument('--ignore-gpu-blocklist')
    chrome_options.add_argument('--enable-native-gpu-memory-buffers')
    
    # Window size and display settings
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--hide-scrollbars')
    chrome_options.add_argument('--force-device-scale-factor=1')
    
    # Additional stability options
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-dev-tools')
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--no-default-browser-check')
    chrome_options.add_argument('--remote-debugging-port=9222')
    
    chrome_prefs = {
        'profile.default_content_settings.popups': 0,
        'profile.password_manager_enabled': False,
        'credentials_enable_service': False,
        'webgl.disabled': False,
        'webgl.force_enabled': True,
    }
    chrome_options.add_experimental_option('prefs', chrome_prefs)
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} to setup WebDriver")
            driver_path = ChromeDriverManager().install()
            service = Service(driver_path)
            
            urllib3.Timeout.DEFAULT_TIMEOUT = 300.0
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            driver.set_page_load_timeout(300)
            driver.set_script_timeout(300)
            driver.implicitly_wait(30)
            
            webgl_status = driver.execute_script("""
                try {
                    var canvas = document.createElement('canvas');
                    var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    var extension = gl.getExtension('WEBGL_debug_renderer_info');
                    return {
                        vendor: gl.getParameter(extension.UNMASKED_VENDOR_WEBGL),
                        renderer: gl.getParameter(extension.UNMASKED_RENDERER_WEBGL),
                        working: true
                    };
                } catch (e) {
                    return {
                        error: e.toString(),
                        working: false
                    };
                }
            """)
            
            logger.info(f"WebGL Status: {webgl_status}")
            return driver
            
        except Exception as e:
            logger.error(f"Error during WebDriver setup: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                raise

def extract_id_from_url(url):
    """Extract the media ID from a MorphoSource URL"""
    patterns = [
        r'/media/(\d+)',
        r'/media/0*(\d+)',
        r'media/0*(\d+)\?'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    numbers = re.findall(r'\d+', url)
    return numbers[0] if numbers else 'unknown'

def wait_for_model_load(driver, timeout=180):
    """Wait for the 3D model to be fully loaded"""
    try:
        time.sleep(10)
        
        for attempt in range(3):
            try:
                canvas = WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.TAG_NAME, "canvas"))
                )
                logger.info("Canvas element found")
                break
            except:
                if attempt < 2:
                    logger.warning(f"Canvas not found, attempt {attempt + 1}/3")
                    time.sleep(10)
                else:
                    raise
        
        time.sleep(20)
        return True
        
    except Exception as e:
        logger.error(f"Error waiting for model load: {str(e)}")
        traceback.print_exc()
        return False

def set_orientation(driver, actions, orientation):
    """Set the model orientation"""
    try:
        logger.info(f"Setting orientation to: {orientation}")
        
        for attempt in range(3):
            try:
                orientation_label = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, "//label[text()='Orientation']"))
                )
                parent_div = orientation_label.find_element(By.XPATH, "./ancestor::div[contains(@class, 'grid gap-4')]")
                combobox = parent_div.find_element(By.CSS_SELECTOR, 'button[role="combobox"]')
                
                actions.move_to_element(combobox).click().perform()
                time.sleep(5)
                
                option = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{orientation}')]"))
                )
                actions.move_to_element(option).click().perform()
                time.sleep(10)
                
                return True
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"Attempt {attempt + 1} failed, retrying: {str(e)}")
                    time.sleep(5)
                else:
                    raise
        
        return False
        
    except Exception as e:
        logger.error(f"Error setting orientation: {str(e)}")
        return False

def take_screenshots(url, output_folder):
    """Take screenshots of the CT scan from different angles"""
    driver = None
    file_id = extract_id_from_url(url)
    screenshot_paths = []
    
    try:
        driver = setup_driver()
        wait = WebDriverWait(driver, 180)
        actions = ActionChains(driver)
        
        logger.info("Loading page...")
        driver.get(url)
        time.sleep(10)
        
        logger.info("Waiting for iframe...")
        iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(iframe)
        time.sleep(10)
        
        if not wait_for_model_load(driver):
            raise Exception("3D model failed to load properly")
        
        logger.info("Entering fullscreen mode...")
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        time.sleep(10)
        
        try:
            expand_button = driver.find_element(By.CSS_SELECTOR, '.expandButton[title="Expand Contents"]')
            if expand_button.is_displayed():
                actions.move_to_element(expand_button).click().perform()
                time.sleep(10)
        except Exception as e:
            logger.warning(f"Could not expand controls: {str(e)}")
        
        orientations = [
            'Default (Y+ Up)',
            'Upside Down (Y- Up)',
            'Forward 90° (Z- Up)',
            'Back 90° (Z+ Up)'
        ]
        
        for orientation in orientations:
            try:
                if set_orientation(driver, actions, orientation):
                    filename = os.path.join(output_folder, 
                        f"{file_id}_{orientation.replace(' ', '_').replace('(', '').replace(')', '').replace('+', 'plus').replace('°', '')}.png")
                    time.sleep(10)
                    driver.save_screenshot(filename)
                    screenshot_paths.append(filename)
                    logger.info(f"Saved screenshot: {filename}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error processing orientation {orientation}: {str(e)}")
        
        return screenshot_paths
        
    except Exception as e:
        logger.error(f"Error taking screenshots: {str(e)}")
        traceback.print_exc()
        raise
    
    finally:
        if driver:
            driver.quit()

def analyze_images_with_openai(image_paths):
    """Analyze CT scan images using OpenAI's vision model"""
    logger.info("Starting OpenAI analysis")
    client = OpenAI()
    
    if not image_paths:
        raise Exception("No screenshots available for analysis")
    
    messages = [
        {
            "role": "system",
            "content": "You are an expert in analyzing CT scans and 3D scientific specimens. Provide detailed analysis of the structural features and scientific significance of the specimen."
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Please analyze these CT scan views and provide a detailed report covering:\n1. Overall specimen description\n2. Notable features\n3. Preservation quality\n4. Scientific significance"
                }
            ]
        }
    ]
    
    for image_path in image_paths:
        logger.info(f"Adding image to analysis: {image_path}")
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf8')
            messages[1]["content"].append({
                "type": "image",
                "image": base64_image
            })

    try:
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=messages,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error during OpenAI analysis: {e}")
        raise

def main():
    if len(sys.argv) != 3:
        logger.error("Usage: ct_image_to_text.py <url> <output_folder>")
        sys.exit(1)
    
    url = sys.argv[1]
    output_folder = sys.argv[2]
    os.makedirs(output_folder, exist_ok=True)
    
    try:
        logger.info(f"Processing URL: {url}")
        screenshot_paths = take_screenshots(url, output_folder)
        
        if not screenshot_paths:
            logger.error("No screenshots were captured")
            sys.exit(1)
        
        logger.info(f"Captured {len(screenshot_paths)} screenshots")
        
        logger.info("Starting image analysis")
        analysis = analyze_images_with_openai(screenshot_paths)
        print(analysis)
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
