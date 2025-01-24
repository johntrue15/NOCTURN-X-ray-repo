# Add to existing imports at the top

def handle_no_file_error(url, driver):
    """Handle case where no file has been uploaded"""
    file_id = extract_id_from_url(url)
    status_data = {
        'status': 'no_file',
        'url': url,
        'file_id': file_id,
        'timestamp': datetime.now().isoformat()
    }
    
    # Save the error state screenshot
    error_file = f"error_{file_id}_no_file.png"
    try:
        driver.save_screenshot(error_file)
        logging.info(f"No file error screenshot saved to {error_file}")
    except Exception as e:
        logging.error(f"Failed to save no file error screenshot: {str(e)}")
    
    # Save status file
    with open('url_check_status.json', 'w') as f:
        json.dump(status_data, f, indent=2)
    logging.info("No file status saved")
    
    return True

def take_screenshot(url):
    file_id = extract_id_from_url(url)
    output_file = f"{file_id}.png"
    error_file = f"error_{file_id}.png"
    max_retries = 3
    server_error_count = 0

    for attempt in range(max_retries):
        driver = None
        try:
            logging.info(f"\nAttempt {attempt + 1}/{max_retries} for ID {file_id}")
            logging.info(f"Loading URL: {url}")
            
            driver = setup_driver()
            driver.get(url)
            
            # Check for 500 error first
            if check_for_server_error(driver):
                server_error_count += 1
                if attempt == max_retries - 1:
                    return handle_server_error(url, driver)
                logging.warning(f"Server error detected (attempt {attempt + 1}), waiting 5 seconds before retry...")
                time.sleep(5)
                continue
            
            # Check for no file uploaded message
            try:
                no_file_msg = driver.find_element(By.CSS_SELECTOR, '.alert.alert-info')
                if "No files have been uploaded" in no_file_msg.text:
                    logging.info("No files have been uploaded to this media record")
                    return handle_no_file_error(url, driver)
            except NoSuchElementException:
                pass

            # Check for the not-ready message
            try:
                not_ready = driver.find_element(By.CSS_SELECTOR, 'div.not-ready')
                if "Media preview currently unavailable" in not_ready.text:
                    logging.info("morphosource media error")
                    print("morphosource media error")
                    return handle_media_error(url, driver)
            except NoSuchElementException:
                pass
            
            # Rest of the function remains unchanged...

# Rest of the file remains unchanged
