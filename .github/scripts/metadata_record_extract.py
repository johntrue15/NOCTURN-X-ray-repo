import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time

def get_morphosource_data(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    all_records = []
    page = 1
    
    while True:
        page_url = f"{url}&page={page}"
        response = requests.get(page_url, headers=headers)
        
        if response.status_code != 200:
            break
            
        soup = BeautifulSoup(response.text, 'html.parser')
        records = soup.find_all('div', class_='search-result-wrapper')
        
        if not records:
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
                    'scraped_date': datetime.now().isoformat()
                }
                
                all_records.append(record_data)
            
            except Exception as e:
                print(f"Error processing record: {e}")
        
        page += 1
        time.sleep(1)  # Respectful delay between requests
    
    return all_records

def main():
    base_url = "https://www.morphosource.org/catalog/media?locale=en&per_page=100&q=X-Ray+Computed+Tomography&search_field=all_fields&sort=system_create_dtsi+desc"
    
    data = get_morphosource_data(base_url)
    
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
