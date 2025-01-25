import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
import os

def try_request(url, headers, max_retries=3, delay=5):
    """Attempt to make a request with retries"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response
            print(f"Attempt {attempt + 1} failed with status code {response.status_code}")
        except Exception as e:
            print(f"Attempt {attempt + 1} failed with error: {e}")
        
        if attempt < max_retries - 1:  # Don't sleep on the last attempt
            time.sleep(delay)
    return None

def save_checkpoint(data, checkpoint_file):
    """Save current progress to a checkpoint file"""
    with open(checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Checkpoint saved: {len(data)} records")

def load_checkpoint(checkpoint_file):
    """Load progress from checkpoint file if it exists"""
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def get_morphosource_data(base_url, max_records=10000, checkpoint_interval=100):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    checkpoint_file = 'data/morphosource_checkpoint.json'
    os.makedirs('data', exist_ok=True)  # Create data directory if it doesn't exist
    
    all_records = load_checkpoint(checkpoint_file)
    start_page = (len(all_records) // 100) + 1
    
    print(f"Starting from page {start_page} with {len(all_records)} existing records")
    
    page = start_page
    records_processed = len(all_records)
    
    while records_processed < max_records:
        page_url = f"{base_url}&page={page}"
        print(f"\nProcessing page {page} ({records_processed} records so far)")
        
        response = try_request(page_url, headers)
        if not response:
            print(f"Failed to fetch page {page} after all retries. Saving progress and exiting.")
            break
        
        soup = BeautifulSoup(response.text, 'html.parser')
        records = soup.find_all('div', class_='search-result-wrapper')
        
        if not records:
            print("No more records found. Ending search.")
            break
        
        for record in records:
            try:
                # Extract title and media type
                title_elem = record.find('div', class_='search-results-title-row')
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                # Extract URL and ID
                link_elem = record.find('a', href=True)
                record_url = f"https://www.morphosource.org{link_elem['href']}" if link_elem else ""
                record_id = record_url.split('/')[-1].split('?')[0] if record_url else ""
                
                # Extract metadata fields
                metadata = {}
                fields = record.find_all('div', class_='index-field-item')
                
                for field in fields:
                    field_text = field.get_text(strip=True)
                    if ':' in field_text:
                        key, value = field_text.split(':', 1)
                        metadata[key.strip()] = value.strip()
                
                record_data = {
                    'title': title,
                    'url': record_url,
                    'id': record_id,
                    'metadata': metadata,
                    'scraped_date': datetime.now().isoformat(),
                    'page_number': page
                }
                
                all_records.append(record_data)
                records_processed += 1
                
                if records_processed >= max_records:
                    print(f"Reached maximum records limit ({max_records})")
                    break
                
                # Save checkpoint at intervals
                if records_processed % checkpoint_interval == 0:
                    save_checkpoint(all_records, checkpoint_file)
                    
            except Exception as e:
                print(f"Error processing record: {e}")
        
        page += 1
        time.sleep(2)  # Polite delay between pages
    
    # Final save
    save_checkpoint(all_records, checkpoint_file)
    
    # Save complete dataset
    final_file = 'data/morphosource_data_complete.json'
    with open(final_file, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)
    
    print(f"\nProcess completed. Total records: {len(all_records)}")
    print(f"Data saved to {final_file}")
    return all_records

if __name__ == "__main__":
    # URL to scrape
    base_url = "https://www.morphosource.org/catalog/media?locale=en&per_page=100&q=X-Ray+Computed+Tomography&search_field=all_fields&sort=system_create_dtsi+desc"
    
    # Run the scraper with parameters
    data = get_morphosource_data(
        base_url,
        max_records=10000,  # Adjustable maximum records
        checkpoint_interval=100  # Save progress every 100 records
    )
