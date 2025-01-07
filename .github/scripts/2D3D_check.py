from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import re
import sys
import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)
    return driver

def extract_id_from_url(url):
    match = re.search(r'(\d+)$', url)
    return match.group(1) if match else 'unknown'

def check_for_server_error(driver):
    try:
        title = driver.title
        if "MorphoSource temporarily unavailable (500)" in title:
            logging.warning("Detected MorphoSource 500 error page")
            return True
        if "MorphoSource temporarily unavailable (500)" in driver.page_source:
            logging.warning("Detected MorphoSource 500 error in page source")
            return True
        return False
    except Exception as e:
        if "MorphoSource temporarily unavailable (500)" in str(e):
            logging.warning("Detected MorphoSource 500 error in exception")
            return True
        return False

def create_status_file(status_data):
    with open('url_check_status.json', 'w') as f:
        json.dump(status_data, f, indent=2)
    logging.info("Status file saved")

def check_media_types(url):
    driver = None
    try:
        driver = setup_driver()
        driver.get(url)
        
        if check_for_server_error(driver):
            status_data = {
                'status': 'server_error',
                'url': url,
                'file_id': extract_id_from_url(url),
                'timestamp': datetime.now().isoformat(),
                'has_mesh': False,
                'has_volumetric_images': False
            }
            create_status_file(status_data)
            return False

        # Check for media error
        try:
            not_ready = driver.find_element(By.CSS_SELECTOR, 'div.not-ready')
            if "Media preview currently unavailable" in not_ready.text:
                status_data = {
                    'status': 'media_error',
                    'url': url,
                    'file_id': extract_id_from_url(url),
                    'timestamp': datetime.now().isoformat(),
                    'has_mesh': False,
                    'has_volumetric_images': False
                }
                create_status_file(status_data)
                return False
        except NoSuchElementException:
            pass

        # Look for type information
        has_mesh = False
        has_volumetric = False
        
        try:
            type_elements = driver.find_elements(By.CLASS_NAME, 'text-muted-value')
            for element in type_elements:
                text = element.text.lower()
                if 'mesh' in text:
                    has_mesh = True
                if 'volumetric image series' in text.lower():
                    has_volumetric = True
        except Exception as e:
            logging.error(f"Error checking types: {str(e)}")

        # Create success status file with type information
        status_data = {
            'status': 'success',
            'url': url,
            'file_id': extract_id_from_url(url),
            'timestamp': datetime.now().isoformat(),
            'has_mesh': has_mesh,
            'has_volumetric_images': has_volumetric
        }
        create_status_file(status_data)
        
        # Output for GitHub Actions
        with open(os.getenv('GITHUB_OUTPUT', 'github_output.txt'), 'a') as f:
            f.write(f"has_mesh={str(has_mesh).lower()}\n")
            f.write(f"has_volumetric_images={str(has_volumetric).lower()}\n")
            f.write("has_media_error=false\n")
            f.write("has_server_error=false\n")
        
        return True

    except Exception as e:
        logging.error(f"Error processing URL: {str(e)}")
        return False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

def process_urls_from_file(input_file):
    try:
        with open(input_file, 'r') as f:
            content = f.read().strip()

        urls = re.findall(r'https://www\.morphosource\.org/concern/media/\d+', content)
        if not urls:
            logging.error("No valid MorphoSource URLs found in file")
            return

        logging.info(f"Found {len(urls)} MorphoSource URLs in file")
        
        # Process only the first URL as we only need type information
        if urls:
            check_media_types(urls[0])

    except Exception as e:
        logging.error(f"Error processing file: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        logging.error("Usage: python script.py <input_file>")
        sys.exit(1)

    process_urls_from_file(sys.argv[1])
