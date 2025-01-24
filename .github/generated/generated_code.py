import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def check_url(url):
    try:
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        wait = WebDriverWait(driver, 60)
        wait.until(EC.presence_of_element_located((By.ID, "uv-iframe")))
        print(f"INFO - Successfully loaded page")
        driver.quit()
    except Exception as e:
        print(f"ERROR - Error during CT slice capture: {e}")
        if "No file uploaded" in str(e):
            print("ERROR - No file uploaded for the given URL")
        driver.quit()
        return False
    return True

def main():
    with open("release_body.txt", "r") as f:
        release_body = f.read()

    morpho_url = None
    for line in release_body.split("\n"):
        if "MorphoSource" in line:
            morpho_url = line.split(":")[-1].strip()
            break

    if morpho_url is None:
        print("ERROR - No MorphoSource URL found in release body")
        return

    print(f"INFO - Found MorphoSource URL: {morpho_url}")

    if not check_url(morpho_url):
        print("ERROR - Error processing CT slices")
        return

    print("INFO - Starting CT slice capture")
    # Add your CT slice capture code here

if __name__ == "__main__":
    main()