# [Previous imports and code remain the same]

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
    
    # Create metadata file for attestation
    metadata = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python_version": sys.version,
        "openai_model": "gpt-4-vision-preview"
    }
    
    with open(os.path.join(screenshots_dir, "analysis_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    
    # [Rest of the main function remains the same]

if __name__ == "__main__":
    main()