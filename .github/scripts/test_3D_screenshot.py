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
from urllib3.exceptions import ReadTimeoutError
import urllib3
import logging

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
    
    # Force GPU hardware acceleration
    chrome_options.add_argument('--ignore-gpu-blocklist')
    chrome_options.add_argument('--enable-gpu-rasterization')
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
    
    # Set Chrome preferences
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
            
            # Install ChromeDriver with increased timeout
            driver_path = ChromeDriverManager().install()
            service = Service(driver_path)
            
            # Create driver with custom connection timeout
            urllib3.Timeout.DEFAULT_TIMEOUT = 300.0  # 5 minutes
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Configure timeouts
            driver.set_page_load_timeout(300)  # 5 minutes
            driver.set_script_timeout(300)     # 5 minutes
            driver.implicitly_wait(30)         # 30 seconds
            
            # Verify WebGL is working
            webgl_working = driver.execute_script("""
                try {
                    var canvas = document.createElement('canvas');
                    var gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    var extension = gl.getExtension('WEBGL_debug_renderer_info');
                    var vendor = gl.getParameter(extension.UNMASKED_VENDOR_WEBGL);
                    var renderer = gl.getParameter(extension.UNMASKED_RENDERER_WEBGL);
                    return {
                        vendor: vendor,
                        renderer: renderer,
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
            
            if not webgl_working.get('working', False):
                raise Exception(f"WebGL not working: {webgl_working.get('error', 'Unknown error')}")
            
            logger.info("WebDriver setup successful")
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
        # Initial wait for any loading indicators
        time.sleep(10)
        
        # Wait for canvas with retries
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
        
        # Wait for loading indicators to disappear
        loading_wait_start = time.time()
        while time.time() - loading_wait_start < timeout:
            loading_elements = driver.find_elements(By.CLASS_NAME, "loading")
            if not loading_elements or not any(elem.is_displayed() for elem in loading_elements):
                logger.info("No visible loading indicators")
                break
            time.sleep(5)
            
        # Check WebGL context and rendering
        webgl_check = driver.execute_script("""
            try {
                const canvas = document.querySelector('canvas');
                if (!canvas) return { status: false, error: 'No canvas found' };
                
                const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                if (!gl) return { status: false, error: 'No WebGL context' };
                
                // Check if anything has been rendered
                const pixels = new Uint8Array(4);
                gl.readPixels(
                    canvas.width/2,
                    canvas.height/2,
                    1, 1,
                    gl.RGBA,
                    gl.UNSIGNED_BYTE,
                    pixels
                );
                
                // Check if any pixel values are non-zero
                const hasContent = pixels.some(value => value > 0);
                
                return {
                    status: hasContent,
                    pixels: Array.from(pixels),
                    canvasSize: {
                        width: canvas.width,
                        height: canvas.height
                    }
                };
            } catch (e) {
                return {
                    status: false,
                    error: e.toString()
                };
            }
        """)
        
        logger.info(f"WebGL check results: {webgl_check}")
        
        if not webgl_check.get('status', False):
            logger.error(f"WebGL check failed: {webgl_check.get('error', 'Unknown error')}")
            return False
            
        # Additional safety sleep
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
        
        # Find orientation controls with retry
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Find orientation label and controls
                orientation_label = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, "//label[text()='Orientation']"))
                )
                parent_div = orientation_label.find_element(By.XPATH, "./ancestor::div[contains(@class, 'grid gap-4')]")
                combobox = parent_div.find_element(By.CSS_SELECTOR, 'button[role="combobox"]')
                
                # Open dropdown
                actions.move_to_element(combobox).click().perform()
                time.sleep(5)
                
                # Select orientation
                option = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{orientation}')]"))
                )
                actions.move_to_element(option).click().perform()
                time.sleep(10)  # Wait for view update
                
                return True
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.warning(f"Attempt {attempt + 1} failed, retrying: {str(e)}")
                    time.sleep(5)
                else:
                    raise
        
        return False
        
    except Exception as e:
        logger.error(f"Error setting orientation: {str(e)}")
        return False

def process_url(url):
    """Process a single URL and take screenshots"""
    driver = None
    start_time = datetime.now()
    file_id = extract_id_from_url(url)
    
    logger.info(f"Starting processing of URL: {url}")
    logger.info(f"Extracted ID: {file_id}")
    
    try:
        driver = setup_driver(max_retries=3, retry_delay=5)
        wait = WebDriverWait(driver, 180)  # Increased timeout
        actions = ActionChains(driver)
        
        # Load page
        logger.info("Loading page...")
        driver.get(url)
        time.sleep(10)  # Initial wait for page load
        
        # Take initial screenshot
        driver.save_screenshot(f"initial_{file_id}.png")
        
        # Wait for and switch to iframe
        logger.info("Waiting for iframe...")
        iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        logger.info("Switching to iframe...")
        driver.switch_to.frame(iframe)
        time.sleep(10)  # Wait after iframe switch
        
        # Wait for model to load
        logger.info("Waiting for 3D model to load...")
        if not wait_for_model_load(driver):
            raise Exception("3D model failed to load properly")
            
        # Take post-model-load screenshot
        driver.save_screenshot(f"model_loaded_{file_id}.png")
        
        # Enter fullscreen
        logger.info("Entering fullscreen mode...")
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        time.sleep(10)  # Wait for fullscreen transition
        
        # Expand controls
        logger.info("Expanding controls...")
        try:
            expand_button = driver.find_element(By.CSS_SELECTOR, '.expandButton[title="Expand Contents"]')
            if expand_button.is_displayed():
                actions.move_to_element(expand_button).click().perform()
                time.sleep(10)
        except Exception as e:
            logger.warning(f"Could not expand controls: {str(e)}")
        
        # Take screenshots for each orientation
        orientations = [
            'Default (Y+ Up)',
            'Upside Down (Y- Up)',
            'Forward 90° (Z- Up)',
            'Back 90° (Z+ Up)'
        ]
        
        for orientation in orientations:
            try:
                logger.info(f"Processing orientation: {orientation}")
                if set_orientation(driver, actions, orientation):
                    filename = f"{file_id}_{orientation.replace(' ', '_').replace('(', '').replace(')', '').replace('+', 'plus').replace('°', '')}.png"
                    time.sleep(10)  # Wait for orientation change
                    driver.save_screenshot(filename)
                    logger.info(f"Saved screenshot: {filename}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error processing orientation {orientation}: {str(e)}")
                driver.save_screenshot(f"orientation_error_{file_id}_{orientation}.png")
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing URL: {str(e)}")
        traceback.print_exc()
        if driver:
            try:
                error_file = f"error_{file_id}.png"
                driver.save_screenshot(error_file)
                logger.info(f"Error screenshot saved as {error_file}")
                
                with open(f"error_{file_id}.txt", 'w') as f:
                    f.write(f"Error processing URL: {url}\n")
                    f.write(f"Error message: {str(e)}\n")
                    f.write(f"Traceback:\n{traceback.format_exc()}")
            except:
                logger.error("Could not save error files")
        return False
        
    finally:
        if driver:
            driver.quit()
        duration = datetime.now() - start_time
        logger.info(f"Processing time: {duration}")

def main():
    if len(sys.argv) != 2:
        logger.error("Usage: python screenshot_test.py <url_file>")
        sys.exit(1)
    
    try:
        with open(sys.argv[1], 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        logger.info(f"Found {len(urls)} URLs to process")
        
        success_count = 0
        for i, url in enumerate(urls, 1):
            logger.info(f"\nProcessing URL {i}/{len(urls)}")
            if process_url(url):
                success_count += 1
        
        logger.info(f"\nProcessing complete")
        logger.info(f"Successfully processed: {success_count}/{len(urls)}")
        
        if success_count != len(urls):
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error reading URL file: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
