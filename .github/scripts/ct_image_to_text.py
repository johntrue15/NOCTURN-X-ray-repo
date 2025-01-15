import os
import sys
import re
import time
import traceback
from datetime import datetime
import logging
from urllib3.exceptions import ReadTimeoutError
import urllib3
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from openai import OpenAI

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
            
            webgl_working = driver.execute_script("""
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
            
            logger.info(f"WebGL Status: {webgl_working}")
            return driver
            
        except Exception as e:
            logger.error(f"Error during WebDriver setup: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                raise

def extract_url_from_file(filepath):
    """Extract MorphoSource URL from the release body file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            
        # Look for MorphoSource URL pattern
        url_match = re.search(r'https://www\.morphosource\.org/concern/media/\d+', content)
        if url_match:
            return url_match.group(0)
            
        # Alternative pattern if the first one doesn't match
        url_match = re.search(r'Detail Page URL:\s*(https://www\.morphosource\.org[^\s]+)', content)
        if url_match:
            return url_match.group(1)
            
        logger.error("No MorphoSource URL found in file")
        return None
    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")
        return None

def extract_id_from_url(url):
    """Extract the media ID from a MorphoSource URL"""
    patterns = [r'/media/(\d+)', r'/media/0*(\d+)', r'media/0*(\d+)\?']
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    numbers = re.findall(r'\d+', url)
    return numbers[0] if numbers else 'unknown'

def process_url(url, output_folder):
    """Process a single URL and take screenshots"""
    driver = None
    start_time = datetime.now()
    file_id = extract_id_from_url(url)
    screenshot_paths = []
    
    try:
        driver = setup_driver(max_retries=3, retry_delay=5)
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
            ('Default (Y+ Up)', 'Default_Yplus_Up.png'),
            ('Upside Down (Y- Up)', 'Upside_Down_Y-_Up.png'),
            ('Forward 90° (Z- Up)', 'Forward_90_Z-_Up.png'),
            ('Back 90° (Z+ Up)', 'Back_90_Zplus_Up.png')
        ]
        
        for orientation_name, filename in orientations:
            try:
                logger.info(f"Processing orientation: {orientation_name}")
                orientation_label = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, "//label[text()='Orientation']"))
                )
                parent_div = orientation_label.find_element(By.XPATH, "./ancestor::div[contains(@class, 'grid gap-4')]")
                combobox = parent_div.find_element(By.CSS_SELECTOR, 'button[role="combobox"]')
                
                actions.move_to_element(combobox).click().perform()
                time.sleep(5)
                
                option = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{orientation_name}')]"))
                )
                actions.move_to_element(option).click().perform()
                time.sleep(10)
                
                filepath = os.path.join(output_folder, filename)
                driver.save_screenshot(filepath)
                screenshot_paths.append(filepath)
                logger.info(f"Saved screenshot: {filepath}")
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error processing orientation {orientation_name}: {str(e)}")
                continue
        
        return screenshot_paths
        
    except Exception as e:
        logger.error(f"Error processing URL: {str(e)}")
        traceback.print_exc()
        return screenshot_paths
    
    finally:
        if driver:
            driver.quit()
        duration = datetime.now() - start_time
        logger.info(f"Processing time: {duration}")

def get_image_paths(folder_path):
    """Get specific image file paths from the given folder."""
    valid_suffixes = {
        "Forward_90_Z-_Up.png",
        "Default_Yplus_Up.png",
        "Upside_Down_Y-_Up.png",
        "Back_90_Zplus_Up.png"
    }
    return [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if any(f.endswith(suffix) for suffix in valid_suffixes)
    ]

def generate_text_with_images(image_paths):
    """Pass image paths and super prompt to the o1-mini model."""
    if not os.environ.get("OPENAI_API_KEY"):
        return "Error: OPENAI_API_KEY is missing."

    client = OpenAI()
    user_content = [
        "You are an advanced AI model tasked with analyzing 3D X-ray CT scan data from Morphosource.org. "
        "Below, I will describe the provided data and 3D orientation images. Your task is to extract meaningful "
        "details about the structure, material composition, and any observable anomalies or characteristics of the object. "
        "Provide a detailed textual analysis based on the images provided."
    ]

    user_content.append("The following images are provided:")
    for i, image_path in enumerate(image_paths, 1):
        user_content.append(f"{i}. {image_path}")

    user_content.append("""
        Input Details:
        1. Orientation Views: The object is presented in multiple perspectives.
        2. Image Details: The 3D scans reflect internal and external structures derived from high-resolution CT imaging.
        
        Expected Analysis:
        - Interpret structural characteristics (e.g., fractures, voids, density distributions).
        - Highlight material inconsistencies or patterns visible across orientations.
        - Describe potential applications or implications based on observed features.
        - Summarize any limitations of the imagery or areas requiring additional focus.
        
        Output Format:
        Provide a detailed textual analysis structured as:
        1. General Overview
        2. Observations from each orientation
        3. Synthesis of insights
        4. Potential applications or research directions
        5. Areas for further investigation
    """)

    try:
        resp = client.chat.completions.create(
            model="o1-mini",
            messages=[{
                "role": "user",
                "content": "\n".join(user_content)
            }]
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Error calling o1-mini model: {e}"

def main():
    if len(sys.argv) != 3:
        logger.error("Usage: ct_image_to_text.py <release_body_file> <output_folder>")
        sys.exit(1)
    
    release_body_file = sys.argv[1]
    output_folder = sys.argv[2]
    os.makedirs(output_folder, exist_ok=True)
    
    try:
        logger.info(f"Processing release body file: {release_body_file}")
        url = extract_url_from_file(release_body_file)
        
        if not url:
            logger.error("Could not extract URL from release body")
            sys.exit(1)
            
        logger.info(f"Extracted URL: {url}")
        screenshot_paths = process_url(url, output_folder)
        
        if not screenshot_paths:
            logger.error("No screenshots were captured")
            sys.exit(1)
        
        logger.info(f"Captured {len(screenshot_paths)} screenshots")
        
        logger.info("Starting image analysis")
        analysis = generate_text_with_images(screenshot_paths)
        print(analysis)
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
