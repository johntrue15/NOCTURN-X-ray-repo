#https://claude.ai/chat/7e5795ce-34c7-4311-b301-22950dc5435c
def take_screenshot(url):
    driver = None
    file_id = extract_id_from_url(url)
    output_file = f"{file_id}.png"
    error_file = f"error_{file_id}.png"
    
    try:
        driver = setup_driver()
        driver.maximize_window()
        
        print(f"\nProcessing URL for ID {file_id}")
        print(f"Loading URL: {url}")
        driver.get(url)
        
        wait = WebDriverWait(driver, 5)
        print("Looking for iframe...")
        uv_iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe")))
        
        print("Switching to iframe...")
        driver.switch_to.frame(uv_iframe)
        
        print("Looking for fullscreen button...")
        full_screen_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen")))
        full_screen_btn.click()

        # Split 8 second sleep into smaller chunks with actions in between
        print("First wait period...")
        time.sleep(2)
        
        # Try to keep renderer active
        driver.switch_to.default_content()
        time.sleep(2)
        
        print("Second wait period...")
        driver.switch_to.frame(uv_iframe)
        time.sleep(2)
        
        print("Final wait period...")
        driver.switch_to.default_content()
        driver.switch_to.frame(uv_iframe)
        time.sleep(2)
        
        print("Taking screenshot...")
        driver.save_screenshot(output_file)
        print(f"Screenshot saved to {output_file}")
        return True
        
    except Exception as e:
        print(f"Error processing {url}: {str(e)}")
        if driver:
            driver.save_screenshot(error_file)
            print(f"Error screenshot saved as {error_file}")
        return False
        
    finally:
        if driver:
            driver.quit()
