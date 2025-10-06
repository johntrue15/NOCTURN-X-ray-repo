#!/usr/bin/env python3
"""
MorphoSource API Client

This module provides a client for interacting with the MorphoSource REST API.
API Documentation: https://morphosource.stoplight.io/docs/morphosource-api/rm6bqdolcidct-morpho-source-rest-api
"""

import requests
import time
import logging
from typing import Dict, List, Optional
from urllib.parse import urlencode

class MorphoSourceAPIClient:
    """Client for interacting with the MorphoSource REST API"""
    
    BASE_URL = "https://www.morphosource.org/api/v1"
    
    def __init__(self, api_key: str):
        """
        Initialize the MorphoSource API client
        
        Args:
            api_key: MorphoSource API key for authentication
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.logger = logging.getLogger(__name__)
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None, method: str = 'GET', max_retries: int = 3) -> Dict:
        """
        Make an API request with retry logic
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
            method: HTTP method (GET, POST, etc.)
            max_retries: Maximum number of retry attempts
            
        Returns:
            JSON response as dictionary
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        for attempt in range(max_retries):
            try:
                if method.upper() == 'GET':
                    response = self.session.get(url, params=params, timeout=30)
                elif method.upper() == 'POST':
                    response = self.session.post(url, json=params, timeout=30)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    time.sleep(wait_time)
                else:
                    raise
    
    def search_media(self, 
                     query: str = "X-Ray Computed Tomography",
                     sort: str = "system_create_dtsi desc",
                     page: int = 1,
                     per_page: int = 100) -> Dict:
        """
        Search for media records
        
        Args:
            query: Search query (default: X-Ray Computed Tomography)
            sort: Sort order (default: system_create_dtsi desc for newest first)
            page: Page number (1-indexed)
            per_page: Results per page (max 100)
            
        Returns:
            Dictionary containing search results and metadata
        """
        params = {
            'q': query,
            'search_field': 'all_fields',
            'sort': sort,
            'page': page,
            'per_page': min(per_page, 100)  # API max is 100
        }
        
        return self._make_request('catalog/media', params=params)
    
    def get_media_by_id(self, media_id: str) -> Dict:
        """
        Get a specific media record by ID
        
        Args:
            media_id: MorphoSource media ID
            
        Returns:
            Dictionary containing media record details
        """
        return self._make_request(f'media/{media_id}')
    
    def get_all_xray_ct_records(self, 
                                  max_pages: Optional[int] = None,
                                  progress_callback: Optional[callable] = None) -> List[Dict]:
        """
        Get all X-ray CT records from MorphoSource
        
        Args:
            max_pages: Maximum number of pages to fetch (None for all)
            progress_callback: Optional callback function called with (page, total_pages, records_so_far)
            
        Returns:
            List of all media records
        """
        all_records = []
        page = 1
        
        while True:
            self.logger.info(f"Fetching page {page}...")
            result = self.search_media(page=page, per_page=100)
            
            # Extract records from response
            # API response structure may vary, adjust based on actual API
            records = result.get('data', result.get('results', []))
            
            if not records:
                break
            
            all_records.extend(records)
            
            if progress_callback:
                total_pages = result.get('meta', {}).get('pages', page)
                progress_callback(page, total_pages, len(all_records))
            
            # Check if there are more pages
            if 'meta' in result and 'next_page' in result['meta']:
                if result['meta']['next_page'] is None:
                    break
            elif len(records) < 100:
                # If we got less than a full page, we're done
                break
            
            if max_pages and page >= max_pages:
                break
            
            page += 1
            time.sleep(0.5)  # Rate limiting - be nice to the API
        
        return all_records
    
    def get_recent_records(self, count: int = 10) -> List[Dict]:
        """
        Get the most recent X-ray CT records
        
        Args:
            count: Number of records to fetch
            
        Returns:
            List of recent media records
        """
        pages_needed = (count // 100) + 1
        all_records = []
        
        for page in range(1, pages_needed + 1):
            result = self.search_media(page=page, per_page=100)
            records = result.get('data', result.get('results', []))
            all_records.extend(records)
            
            if len(all_records) >= count:
                break
        
        return all_records[:count]
    
    def get_modified_records(self, 
                            since: Optional[str] = None,
                            count: int = 10) -> List[Dict]:
        """
        Get recently modified X-ray CT records
        
        Args:
            since: ISO format date string to filter records modified since
            count: Number of records to fetch
            
        Returns:
            List of recently modified media records
        """
        # Sort by modification date instead of creation date
        result = self.search_media(
            sort="system_modified_dtsi desc",
            per_page=min(count, 100)
        )
        
        records = result.get('data', result.get('results', []))
        
        if since:
            # Filter records modified after the given date
            from datetime import datetime
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
            records = [
                r for r in records 
                if datetime.fromisoformat(r.get('modified_date', '').replace('Z', '+00:00')) > since_dt
            ]
        
        return records[:count]
    
    def parse_record_to_legacy_format(self, api_record: Dict) -> Dict:
        """
        Convert API record format to the legacy scraping format
        for backward compatibility with existing code
        
        Args:
            api_record: Record in API format
            
        Returns:
            Record in legacy format matching the old scraper output
        """
        from datetime import datetime
        
        # Extract metadata fields from API response
        # Note: Actual field names may differ based on API response structure
        legacy_record = {
            'title': api_record.get('title', api_record.get('name', 'No Title')),
            'url': f"https://www.morphosource.org/concern/media/{api_record.get('id', '')}",
            'id': api_record.get('id', ''),
            'metadata': {},
            'scraped_date': datetime.now().isoformat()
        }
        
        # Map API fields to legacy metadata structure
        field_mapping = {
            'object_id': 'Object',
            'taxonomy': 'Taxonomy',
            'element': 'Element or Part',
            'data_manager': 'Data Manager',
            'date_uploaded': 'Date Uploaded',
            'publication_status': 'Publication Status',
            'rights_statement': 'Rights Statement',
            'cc_license': 'CC License'
        }
        
        for api_field, legacy_field in field_mapping.items():
            if api_field in api_record:
                legacy_record['metadata'][legacy_field] = api_record[api_field]
        
        return legacy_record
