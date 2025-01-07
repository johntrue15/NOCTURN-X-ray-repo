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
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-gpu')
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def wait_for_element(driver, locator, timeout=30):
    """Wait for an element to be present and visible."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
        return element
    except TimeoutException:
        logger.error(f"Timeout waiting for element: {locator}")
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

def take_screenshots(url, output_folder):
    """Take screenshots of the CT scan from different angles"""
    driver = None
    file_id = extract_id_from_url(url)
    screenshots = []
    orientations = [
        ('Default (Y+ Up)', 'Default_Yplus_Up.png'),
        ('Upside Down (Y- Up)', 'Upside_Down_Y-_Up.png'),
        ('Forward 90° (Z- Up)', 'Forward_90_Z-_Up.png'),
        ('Back 90° (Z+ Up)', 'Back_90_Zplus_Up.png')
    ]
    
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
        
        logger.info("Entering fullscreen mode...")
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        time.sleep(2)
        
        try:
            expand_button = driver.find_element(By.CSS_SELECTOR, '.expandButton[title="Expand Contents"]')
            if expand_button.is_displayed():
                actions.move_to_element(expand_button).click().perform()
                time.sleep(10)
        except Exception as e:
            logger.warning(f"Could not expand controls: {str(e)}")
        
        for orientation_name, file_name in orientations:
            try:
                if set_orientation(driver, actions, orientation_name):
                    filepath = os.path.join(output_folder, file_name)
                    time.sleep(10)
                    driver.save_screenshot(filepath)
                    screenshots.append(filepath)
                    logger.info(f"Saved screenshot: {filepath}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error processing orientation {orientation_name}: {str(e)}")
        
        return screenshots
        
    except Exception as e:
        logger.error(f"Error taking screenshots: {str(e)}")
        traceback.print_exc()
        raise
    
    finally:
        if driver:
            driver.quit()

def set_orientation(driver, actions, orientation):
    """Set the model orientation"""
    try:
        logger.info(f"Setting orientation to: {orientation}")
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
        logger.error(f"Error setting orientation: {str(e)}")
        return False

def generate_text_with_images(image_paths):
    """Analyze CT scan images using OpenAI's model"""
    logger.info("Starting OpenAI analysis")
    
    if not os.environ.get("OPENAI_API_KEY"):
        raise Exception("OPENAI_API_KEY is missing")
    
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
        response = client.chat.completions.create(
            model="o1-mini",
            messages=[
                {
                    "role": "user",
                    "content": "\n".join(user_content)
                }
            ]
        )
        return response.choices[0].message.content.strip()
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
        analysis = generate_text_with_images(screenshot_paths)
        print(analysis)
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
