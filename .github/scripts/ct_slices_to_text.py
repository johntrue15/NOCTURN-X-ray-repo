#!/usr/bin/env python3
import os
import sys
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import openai
from PIL import Image
import io
import base64

def extract_morphosource_url(release_body_file):
    """Extract MorphoSource URL from release body file."""
    try:
        with open(release_body_file, 'r') as f:
            content = f.read()
            
        # Look for MorphoSource URLs in the content
        matches = re.findall(r'https://www\.morphosource\.org/concern/media/\d+', content)
        if matches:
            return matches[0]
        else:
            print("No MorphoSource URL found in release body")
            return None
    except Exception as e:
        print(f"Error reading release body file: {e}")
        return None

def analyze_screenshot_with_gpt4(image_path, slice_index):
    """Analyze a CT slice screenshot using GPT-4 Vision."""
    try:
        # Read and encode the image
        with open(image_path, 'rb') as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')

        # Prepare the message for GPT-4 Vision
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"This is a CT slice image (slice index: {slice_index}) from a MorphoSource specimen. Please analyze the image and describe:\n1. What anatomical features are visible\n2. The quality and clarity of the scan\n3. Any notable artifacts or issues in the image"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_data}"
                        }
                    }
                ]
            }
        ]

        # Call GPT-4 Vision API
        response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=messages,
            max_tokens=500
        )

        return response.choices[0].message.content
    except Exception as e:
        print(f"Error analyzing image with GPT-4: {e}")
        return f"Error analyzing image: {str(e)}"

def capture_ct_slices(url, screenshots_dir):
    """Capture CT slice screenshots using Selenium."""
    # Chrome setup
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    driver.set_script_timeout(30)
    
    analyses = []
    
    try:
        # Navigate to URL
        print(f"Navigating to {url}")
        driver.get(url)
        
        # Switch to uv-iframe
        wait = WebDriverWait(driver, 20)
        uv_iframe = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
        )
        driver.switch_to.frame(uv_iframe)
        
        # Click Full Screen
        full_screen_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
        )
        full_screen_btn.click()
        
        # Wait for viewer to load
        time.sleep(180)
        
        # Find control panel
        host_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "al-control-panel"))
        )
        print("Found control panel")
        
        # Get settings element
        al_settings = driver.execute_script(
            "return arguments[0].shadowRoot.querySelector('al-settings')",
            host_element
        )
        if not al_settings:
            raise Exception("Could not find settings element")
        
        # Capture slices
        slice_values = [round(i * 0.1, 1) for i in range(1, 10)]
        for val in slice_values:
            # Set slice index
            driver.execute_script(
                "arguments[0].setAttribute('slices-index', arguments[1])",
                al_settings,
                str(val)
            )
            print(f"Set slice index to {val}")
            
            # Wait for slice to load
            time.sleep(2)
            
            # Take screenshot
            screenshot_path = os.path.join(screenshots_dir, f"slice_{val}.png")
            driver.save_screenshot(screenshot_path)
            print(f"Saved screenshot: {screenshot_path}")
            
            # Analyze screenshot
            analysis = analyze_screenshot_with_gpt4(screenshot_path, val)
            analyses.append({
                "slice_index": val,
                "analysis": analysis
            })
            
            time.sleep(2)
            
        return analyses
        
    except Exception as e:
        print(f"Error during CT slice capture: {e}")
        # Save error screenshot if possible
        try:
            driver.save_screenshot(os.path.join(screenshots_dir, "error_screenshot.png"))
        except:
            pass
        raise
        
    finally:
        driver.quit()

def main():
    if len(sys.argv) != 3:
        print("Usage: python ct_slices_to_text.py <release_body_file> <screenshots_dir>")
        sys.exit(1)
        
    release_body_file = sys.argv[1]
    screenshots_dir = sys.argv[2]
    
    # Ensure screenshots directory exists
    os.makedirs(screenshots_dir, exist_ok=True)
    
    # Extract URL
    url = extract_morphosource_url(release_body_file)
    if not url:
        print("Could not find MorphoSource URL")
        sys.exit(1)
    
    try:
        # Capture and analyze slices
        analyses = capture_ct_slices(url, screenshots_dir)
        
        # Print analyses
        print("\nCT Slice Analyses:")
        print("=================")
        for analysis in analyses:
            print(f"\nSlice Index: {analysis['slice_index']}")
            print("Analysis:")
            print(analysis['analysis'])
            print("-" * 80)
            
    except Exception as e:
        print(f"Error processing CT slices: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
