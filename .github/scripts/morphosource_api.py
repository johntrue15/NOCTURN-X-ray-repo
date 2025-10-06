#!/usr/bin/env python3
"""
MorphoSource API Client

This module provides a Python client for interacting with the MorphoSource API
instead of web scraping. This approach is more reliable and less likely to
trigger bot detection mechanisms.
"""

import requests
import time
import random
from typing import Dict, List, Optional, Any
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter


class MorphoSourceAPIError(Exception):
    """Base exception for MorphoSource API errors"""
    pass


class MorphoSourceTemporarilyUnavailable(MorphoSourceAPIError):
    """Exception for when MorphoSource is temporarily unavailable"""
    pass


class MorphoSourceAPI:
    """
    Client for accessing MorphoSource data via their JSON API.
    
    MorphoSource uses Blacklight/Solr which provides JSON endpoints for catalog searches.
    This is the preferred method over web scraping as it:
    - Returns structured JSON data
    - Is more reliable and performant
    - Less likely to trigger bot detection
    - Officially supported by the platform
    """
    
    BASE_URL = "https://www.morphosource.org"
    API_ENDPOINT = "/catalog.json"
    
    def __init__(self, timeout: tuple = (10, 30)):
        """
        Initialize the API client.
        
        Args:
            timeout: Tuple of (connect_timeout, read_timeout) in seconds
        """
        self.timeout = timeout
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy"""
        session = requests.Session()
        
        # Conservative retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            respect_retry_after_header=True
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=1,
            pool_maxsize=1
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set headers to identify as API client
        session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'MorphoSource-Research-Bot/1.0 (GitHub Actions; Scientific Research)'
        })
        
        return session
    
    def search_media(
        self,
        query: str = "X-Ray Computed Tomography",
        sort: str = "system_create_dtsi desc",
        page: int = 1,
        per_page: int = 20,
        search_field: str = "all_fields"
    ) -> Dict[str, Any]:
        """
        Search for media records in MorphoSource.
        
        Args:
            query: Search query string
            sort: Sort field and direction (e.g., "system_create_dtsi desc")
            page: Page number (1-indexed)
            per_page: Number of results per page
            search_field: Field to search in (default: all_fields)
            
        Returns:
            Dictionary containing search results with keys:
            - data: List of record documents
            - meta: Metadata including pagination info
            - response: Raw response info
            
        Raises:
            MorphoSourceAPIError: If the API request fails
        """
        params = {
            'q': query,
            'search_field': search_field,
            'sort': sort,
            'page': page,
            'per_page': per_page
        }
        
        url = f"{self.BASE_URL}{self.API_ENDPOINT}"
        
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            return self._parse_api_response(data)
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code >= 500:
                raise MorphoSourceTemporarilyUnavailable(
                    f"MorphoSource server error: {e.response.status_code}"
                )
            raise MorphoSourceAPIError(f"API request failed: {e}")
        except requests.exceptions.RequestException as e:
            raise MorphoSourceAPIError(f"Network error: {e}")
        except ValueError as e:
            raise MorphoSourceAPIError(f"Invalid JSON response: {e}")
    
    def _parse_api_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the API response into a consistent format.
        
        Args:
            data: Raw JSON response from API
            
        Returns:
            Parsed response with normalized structure
        """
        # Blacklight JSON API typically returns:
        # - response: Contains numFound, start, docs
        # - facets: Facet information
        # - meta: Pagination and other metadata
        
        parsed = {
            'data': data.get('data', data.get('response', {}).get('docs', [])),
            'meta': {
                'total': data.get('meta', {}).get('pages', {}).get('total_count', 0),
                'page': data.get('meta', {}).get('pages', {}).get('current_page', 1),
                'per_page': data.get('meta', {}).get('pages', {}).get('limit_value', 20),
                'total_pages': data.get('meta', {}).get('pages', {}).get('total_pages', 1),
            },
            'response': data.get('response', {})
        }
        
        # Handle alternative response structures
        if 'response' in data and 'numFound' in data['response']:
            parsed['meta']['total'] = data['response']['numFound']
        
        return parsed
    
    def get_record_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific record by its ID.
        
        Args:
            record_id: The MorphoSource record ID
            
        Returns:
            Record data or None if not found
        """
        url = f"{self.BASE_URL}/concern/media/{record_id}.json"
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise MorphoSourceAPIError(f"Failed to fetch record {record_id}: {e}")
        except requests.exceptions.RequestException as e:
            raise MorphoSourceAPIError(f"Network error fetching record: {e}")
    
    def get_total_count(self, query: str = "X-Ray Computed Tomography") -> int:
        """
        Get the total count of records matching a query.
        
        Args:
            query: Search query string
            
        Returns:
            Total number of matching records
        """
        result = self.search_media(query=query, per_page=1)
        return result['meta']['total']
    
    def get_latest_records(
        self,
        n: int = 3,
        query: str = "X-Ray Computed Tomography"
    ) -> List[Dict[str, Any]]:
        """
        Get the N most recently created records.
        
        Args:
            n: Number of records to retrieve
            query: Search query string
            
        Returns:
            List of record dictionaries
        """
        result = self.search_media(
            query=query,
            sort="system_create_dtsi desc",
            per_page=n
        )
        return result['data']
    
    def get_latest_modified_record(
        self,
        query: str = "X-Ray Computed Tomography"
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recently modified record.
        
        Args:
            query: Search query string
            
        Returns:
            Most recently modified record or None
        """
        result = self.search_media(
            query=query,
            sort="system_modified_dtsi desc",
            per_page=1
        )
        records = result['data']
        return records[0] if records else None
    
    def iterate_all_records(
        self,
        query: str = "X-Ray Computed Tomography",
        per_page: int = 100,
        delay: float = 2.0,
        max_pages: Optional[int] = None
    ):
        """
        Generator that yields all records matching a query, page by page.
        
        Args:
            query: Search query string
            per_page: Number of records per page
            delay: Delay between requests in seconds (for rate limiting)
            max_pages: Maximum number of pages to fetch (None for all)
            
        Yields:
            Individual record dictionaries
        """
        page = 1
        
        while True:
            if max_pages and page > max_pages:
                break
            
            result = self.search_media(
                query=query,
                sort="system_create_dtsi desc",
                page=page,
                per_page=per_page
            )
            
            records = result['data']
            if not records:
                break
            
            for record in records:
                yield record
            
            # Check if we've reached the last page
            if page >= result['meta']['total_pages']:
                break
            
            page += 1
            
            # Rate limiting
            if delay > 0:
                time.sleep(delay + random.uniform(0, 1))
    
    def normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize an API record to match the format used by web scraping.
        
        This ensures backward compatibility with existing code.
        
        Args:
            record: Raw API record
            
        Returns:
            Normalized record dictionary
        """
        # Extract ID from various possible fields
        record_id = (
            record.get('id') or
            record.get('record_id') or
            record.get('ark_id', '').split('/')[-1] or
            'unknown'
        )
        
        # Build detail URL
        detail_url = f"{self.BASE_URL}/concern/media/{record_id}"
        
        # Extract metadata fields
        metadata = {}
        metadata_fields = [
            'taxonomy_class_sms',
            'taxonomy_order_sms', 
            'taxonomy_family_sms',
            'taxonomy_genus_sms',
            'taxonomy_species_sms',
            'element_sms',
            'institution_name_sms',
            'publication_status_sms',
            'license_sms',
            'data_manager_sms',
            'date_uploaded_sms',
        ]
        
        # Map API fields to human-readable metadata keys
        field_mapping = {
            'taxonomy_class_sms': 'Taxonomy',
            'element_sms': 'Element or Part',
            'institution_name_sms': 'Institution',
            'publication_status_sms': 'Publication Status',
            'license_sms': 'CC License',
            'data_manager_sms': 'Data Manager',
            'date_uploaded_sms': 'Date Uploaded',
        }
        
        for api_field, readable_name in field_mapping.items():
            if api_field in record:
                value = record[api_field]
                if isinstance(value, list):
                    value = ', '.join(str(v) for v in value)
                metadata[readable_name] = str(value)
        
        # Handle taxonomy specially
        taxonomy_parts = []
        for field in ['taxonomy_class_sms', 'taxonomy_order_sms', 'taxonomy_family_sms',
                      'taxonomy_genus_sms', 'taxonomy_species_sms']:
            if field in record:
                val = record[field]
                if isinstance(val, list):
                    val = val[0] if val else ''
                if val:
                    taxonomy_parts.append(str(val))
        if taxonomy_parts:
            metadata['Taxonomy'] = ' '.join(taxonomy_parts)
        
        # Get object/specimen ID
        if 'object_id_sms' in record:
            obj_id = record['object_id_sms']
            if isinstance(obj_id, list):
                obj_id = obj_id[0] if obj_id else ''
            metadata['Object'] = str(obj_id)
        
        return {
            'id': record_id,
            'title': record.get('title_sms', record.get('title', ['No Title']))[0] if isinstance(
                record.get('title_sms', record.get('title', 'No Title')), list
            ) else record.get('title_sms', record.get('title', 'No Title')),
            'url': detail_url,
            'detail_url': detail_url,
            'metadata': metadata,
            'raw_data': record  # Keep raw data for reference
        }


def create_api_client(**kwargs) -> MorphoSourceAPI:
    """
    Factory function to create an API client instance.
    
    Args:
        **kwargs: Arguments to pass to MorphoSourceAPI constructor
        
    Returns:
        Configured API client
    """
    return MorphoSourceAPI(**kwargs)
