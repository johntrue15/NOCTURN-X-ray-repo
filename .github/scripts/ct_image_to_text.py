#!/usr/bin/env python3
import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import base64
import io
try:
    from openai import OpenAI
except ImportError:
    print("Error: The 'openai' library is missing.")
    sys.exit(1)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

def setup_webdriver():
    """Set up Chrome webdriver with headless mode."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def take_screenshots(url, output_folder):
    """Navigate to URL and take screenshots of CT scan views."""
    driver = setup_webdriver()
    screenshots = []
    
    try:
        driver.get(url)
        
        # Wait for the 3D viewer to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "viewer-container"))
        )
        
        # Allow time for 3D model to fully render
        time.sleep(5)
        
        # Take screenshots from different angles
        angles = [
            ("front", None),
            ("side", "rotate-right"),
            ("top", "rotate-up"),
            ("perspective", "rotate-diagonal")
        ]
        
        for angle_name, button_class in angles:
            if button_class:
                try:
                    button = driver.find_element(By.CLASS_NAME, button_class)
                    button.click()
                    time.sleep(2)  # Wait for rotation animation
                except:
                    print(f"Warning: Could not find rotation button for {angle_name}")
            
            screenshot_path = os.path.join(output_folder, f"ct_view_{angle_name}.png")
            driver.save_screenshot(screenshot_path)
            screenshots.append(screenshot_path)
            
            # Optimize screenshot
            img = Image.open(screenshot_path)
            img = img.convert('RGB')
            img.save(screenshot_path, optimize=True, quality=85)
    
    finally:
        driver.quit()
    
    return screenshots

def encode_image(image_path):
    """Encode image as base64 string."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_images_with_openai(image_paths):
    """Analyze CT scan images using OpenAI's vision model."""
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY is missing."

    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # Prepare messages with images
    messages = [
        {
            "role": "system",
            "content": "You are an expert in analyzing CT scans and 3D medical imaging data. Provide detailed analysis of the structural characteristics, notable features, and potential scientific significance of the specimen shown in these images."
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Please analyze these CT scan views and provide a detailed report covering:\n1. Overall specimen description\n2. Notable structural features\n3. Preservation quality and any visible artifacts\n4. Scientific significance and potential research applications"
                }
            ]
        }
    ]
    
    # Add images to the message
    for image_path in image_paths:
        base64_image = encode_image(image_path)
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
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error analyzing images with OpenAI: {e}"

def main():
    """Main function to process URL and generate analysis."""
    if len(sys.argv) < 3:
        print("Usage: ct_image_to_text.py <morphosource_url> <output_folder>")
        sys.exit(1)
    
    url = sys.argv[1]
    output_folder = sys.argv[2]
    
    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)
    
    # Take screenshots
    print("Taking screenshots...")
    screenshot_paths = take_screenshots(url, output_folder)
    
    if not screenshot_paths:
        print("Error: No screenshots were captured.")
        sys.exit(1)
    
    # Analyze images
    print("Analyzing images with OpenAI...")
    analysis = analyze_images_with_openai(screenshot_paths)
    
    print(analysis)

if __name__ == "__main__":
    main()
