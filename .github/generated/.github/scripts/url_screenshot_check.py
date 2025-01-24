# ... (existing imports) ...

class NoFileUploaded(Exception):
    """Custom exception for when no file is uploaded on MorphoSource"""
    pass

# ... (existing functions) ...

def handle_no_file_error(url, driver):
    """Handle no file uploaded case and create status file"""
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
    logging.info("No file status file saved")

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
                if attempt == max_retries - 1:  # If this is the last attempt
                    return handle_server_error(url, driver)
                logging.warning(f"Server error detected (attempt {attempt + 1}), waiting 5 seconds before retry...")
                time.sleep(5)
                continue

            # Check for the not-ready message
            try:
                not_ready = driver.find_element(By.CSS_SELECTOR, 'div.not-ready')
                if "Media preview currently unavailable" in not_ready.text:
                    logging.info("Morphosource media error")
                    return handle_media_error(url, driver)
                elif "No file uploaded" in not_ready.text:
                    logging.info("No file uploaded on MorphoSource")
                    return handle_no_file_error(url, driver)
            except NoSuchElementException:
                pass

            # If no errors, proceed with screenshot
            wait = WebDriverWait(driver, 10)
            uv_iframe = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe#uv-iframe"))
            )

            driver.switch_to.frame(uv_iframe)

            full_screen_btn = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn.imageBtn.fullScreen"))
            )
            full_screen_btn.click()

            logging.info("Taking screenshot...")
            driver.save_screenshot(output_file)
            logging.info(f"Screenshot saved to {output_file}")
            return True

        except Exception as e:
            logging.error(f"Error on attempt {attempt + 1}: {str(e)}")
            if driver:
                try:
                    driver.save_screenshot(error_file)
                    logging.info(f"Error screenshot saved as {error_file}")
                except Exception as se:
                    logging.error(f"Failed to save error screenshot: {str(se)}")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    # If we got here and all attempts were server errors, handle it
    if server_error_count == max_retries:
        return handle_server_error(url)

    return False

# ... (existing code) ...