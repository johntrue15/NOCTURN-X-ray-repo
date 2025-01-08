#!/usr/bin/env python3
import os
import sys
import time
import re
import json
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from openai import OpenAI
from PIL import Image
import io
import base64

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def extract_morphosource_url(release_body_file):
    """Extract MorphoSource URL from release body file."""
    logger.info(f"Reading release body from: {release_body_file}")
    try:
        with open(release_body_file, 'r') as f:
            content = f.read()
        logger.info("Successfully read release body file")
            
        # Look for MorphoSource URLs in the content
        matches = re.findall(r'https://www\.morphosource\.org/concern/media/\d+', content)
        if matches:
            logger.info(f"Found MorphoSource URL: {matches[0]}")
            return matches[0]
        else:
            logger.error("No MorphoSource URL found in release body")
            return None
    except Exception as e:
        logger.error(f"Error reading release body file: {e}")
        return None

def analyze_screenshot_with_gpt4(image_path, slice_index):
    """Analyze a CT slice screenshot using GPT-4 Vision."""
    logger.info(f"Analyzing screenshot for slice index {slice_index}")
    try:
        # Initialize OpenAI client
        client = OpenAI()
        
        # Read and encode the image
        def encode_image(image_path):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        
        # Getting the base64 string
        base64_image = encode_image(image_path)
        logger.info(f"Successfully encoded image: {image_path}")

        logger.info("Calling GPT-4 Vision API")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"This is a CT slice image (slice index: {slice_index}) from a MorphoSource specimen. Please analyze the image and describe: 1. What anatomical features are visible 2. The quality and clarity of the scan 3. Any notable artifacts or issues in the image"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        )
        logger.info("Successfully received GPT-4 Vision response")
        
        return response.choices[0].message.content
    except Exception as e:
        error_msg = f"Error analyzing image with GPT-4: {str(e)}"
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        logger.error(f"Error analyzing image with GPT-4: {e}")
        return f"Error analyzing image: {str(e)}"

def capture_ct_slices(url, screenshots_dir):
    """Capture CT slice screenshots using Selenium."""
    logger.info("Setting up Chrome options")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    logger.info("Initializing Chrome driver")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    
    analyses = []
    
    try:
        # Navigate to URL
        logger.info(f"Navigating to URL: {url}")
        driver.get(url)
        logger.info("Successfully loaded page")
        
        # Switch to uv-iframe
        logger.info("Waiting for uv-iframe")
        wait = WebDriverWait(driver, 20)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        logger.info("Found uv-iframe, switching to it")
        driver.switch_to.frame(uv_iframe)
        
        # Click Full Screen
        logger.info("Looking for full screen button")
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        logger.info("Clicking full screen button")
        full_screen_btn.click()
        
        # Wait for viewer to load
        logger.info("Waiting for viewer to load (180s)")
        time.sleep(180)
        
        # Find control panel
        logger.info("Looking for control panel")
        host_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "al-control-panel"))
        )
        logger.info("Found control panel")
        
        # Get settings element
        logger.info("Accessing settings element through shadow DOM")
        al_settings = driver.execute_script(
            "return arguments[0].shadowRoot.querySelector('al-settings')",
            host_element
        )
        if not al_settings:
            logger.error("Could not find settings element")
            raise Exception("Could not find settings element")
        logger.info("Successfully found settings element")
        
        # Capture slices
        slice_values = [round(i * 0.1, 1) for i in range(1, 10)]
        for val in slice_values:
            logger.info(f"Processing slice {val}")
            # Set slice index
            driver.execute_script(
                "arguments[0].setAttribute('slices-index', arguments[1])",
                al_settings,
                str(val)
            )
            logger.info(f"Set slice index to {val}")
            
            # Wait for slice to load
            time.sleep(2)
            
            # Take screenshot
            screenshot_path = os.path.join(screenshots_dir, f"slice_{val}.png")
            driver.save_screenshot(screenshot_path)
            logger.info(f"Saved screenshot: {screenshot_path}")
            
            # Analyze screenshot
            logger.info(f"Starting analysis for slice {val}")
            analysis = analyze_screenshot_with_gpt4(screenshot_path, val)
            analyses.append({
                "slice_index": val,
                "analysis": analysis
            })
            logger.info(f"Completed analysis for slice {val}")
            
            time.sleep(2)
            
        return analyses
        
    except Exception as e:
        logger.error(f"Error during CT slice capture: {e}")
        # Save error screenshot if possible
        try:
            error_path = os.path.join(screenshots_dir, "error_screenshot.png")
            driver.save_screenshot(error_path)
            logger.info(f"Saved error screenshot to {error_path}")
        except Exception as screenshot_error:
            logger.error(f"Failed to save error screenshot: {screenshot_error}")
        raise
        
    finally:
        logger.info("Closing Chrome driver")
        driver.quit()

def main():
    if len(sys.argv) != 3:
        logger.error("Incorrect number of arguments")
        print("Usage: python ct_slices_to_text.py <release_body_file> <screenshots_dir>")
        sys.exit(1)
        
    release_body_file = sys.argv[1]
    screenshots_dir = sys.argv[2]
    
    logger.info(f"Starting CT slice analysis with:")
    logger.info(f"Release body file: {release_body_file}")
    logger.info(f"Screenshots directory: {screenshots_dir}")
    
    # Ensure screenshots directory exists
    os.makedirs(screenshots_dir, exist_ok=True)
    logger.info("Created screenshots directory")
    
    # Extract URL
    url = extract_morphosource_url(release_body_file)
    if not url:
        logger.error("Could not find MorphoSource URL")
        sys.exit(1)
    
    try:
        # Capture and analyze slices
        logger.info("Starting CT slice capture and analysis")
        analyses = capture_ct_slices(url, screenshots_dir)
        
        # Print analyses
        print("\nCT Slice Analyses:")
        print("=================")
        for analysis in analyses:
            print(f"\nSlice Index: {analysis['slice_index']}")
            print("Analysis:")
            print(analysis['analysis'])
            print("-" * 80)
            
        logger.info("Successfully completed CT slice analysis")
            
    except Exception as e:
        logger.error(f"Error processing CT slices: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
