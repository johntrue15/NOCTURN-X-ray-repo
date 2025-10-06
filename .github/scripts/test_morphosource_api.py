#!/usr/bin/env python3
"""
Unit tests for the MorphoSource API client.

These tests validate the API client structure and normalization logic
without making actual network requests.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
from morphosource_api import MorphoSourceAPI, MorphoSourceAPIError, MorphoSourceTemporarilyUnavailable


class TestMorphoSourceAPI(unittest.TestCase):
    """Test cases for the MorphoSource API client"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.api = MorphoSourceAPI()
        
        # Sample API response data
        self.sample_api_response = {
            'data': [
                {
                    'id': '000123456',
                    'title_sms': ['Test Specimen - Skull'],
                    'taxonomy_class_sms': ['Mammalia'],
                    'taxonomy_order_sms': ['Primates'],
                    'taxonomy_genus_sms': ['Homo'],
                    'taxonomy_species_sms': ['sapiens'],
                    'element_sms': ['skull'],
                    'object_id_sms': ['M-12345'],
                    'publication_status_sms': ['published'],
                    'institution_name_sms': ['Test Museum'],
                    'data_manager_sms': ['Test Manager'],
                    'date_uploaded_sms': ['2024-01-01'],
                }
            ],
            'meta': {
                'pages': {
                    'total_count': 108000,
                    'current_page': 1,
                    'limit_value': 20,
                    'total_pages': 5400
                }
            },
            'response': {
                'numFound': 108000
            }
        }
    
    def test_api_initialization(self):
        """Test that API client initializes correctly"""
        self.assertIsNotNone(self.api)
        self.assertIsNotNone(self.api.session)
        self.assertEqual(self.api.BASE_URL, "https://www.morphosource.org")
        self.assertEqual(self.api.API_ENDPOINT, "/catalog.json")
    
    def test_parse_api_response(self):
        """Test parsing of API response"""
        parsed = self.api._parse_api_response(self.sample_api_response)
        
        self.assertIn('data', parsed)
        self.assertIn('meta', parsed)
        self.assertEqual(len(parsed['data']), 1)
        self.assertEqual(parsed['meta']['total'], 108000)
        self.assertEqual(parsed['meta']['page'], 1)
        self.assertEqual(parsed['meta']['per_page'], 20)
        self.assertEqual(parsed['meta']['total_pages'], 5400)
    
    def test_normalize_record(self):
        """Test record normalization"""
        api_record = self.sample_api_response['data'][0]
        normalized = self.api.normalize_record(api_record)
        
        # Check required fields
        self.assertIn('id', normalized)
        self.assertIn('title', normalized)
        self.assertIn('url', normalized)
        self.assertIn('metadata', normalized)
        
        # Check ID extraction
        self.assertEqual(normalized['id'], '000123456')
        
        # Check title
        self.assertEqual(normalized['title'], 'Test Specimen - Skull')
        
        # Check URL format
        self.assertTrue(normalized['url'].startswith('https://www.morphosource.org'))
        self.assertIn('000123456', normalized['url'])
        
        # Check metadata fields
        metadata = normalized['metadata']
        self.assertIn('Taxonomy', metadata)
        self.assertIn('Object', metadata)
        self.assertIn('Publication Status', metadata)
        
        # Check taxonomy concatenation
        self.assertIn('Mammalia', metadata['Taxonomy'])
        self.assertIn('sapiens', metadata['Taxonomy'])
    
    @patch('morphosource_api.requests.Session.get')
    def test_search_media_success(self, mock_get):
        """Test successful search_media call"""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_api_response
        mock_get.return_value = mock_response
        
        # Call the method
        result = self.api.search_media(query="X-Ray Computed Tomography")
        
        # Verify
        self.assertIn('data', result)
        self.assertIn('meta', result)
        self.assertEqual(len(result['data']), 1)
        mock_get.assert_called_once()
    
    @patch('morphosource_api.requests.Session.get')
    def test_search_media_server_error(self, mock_get):
        """Test handling of server errors"""
        import requests
        # Mock a 500 error
        mock_response = Mock()
        mock_response.status_code = 500
        http_error = requests.exceptions.HTTPError("Server Error")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response
        
        # Should raise MorphoSourceTemporarilyUnavailable
        with self.assertRaises(MorphoSourceAPIError):
            self.api.search_media(query="X-Ray Computed Tomography")
    
    @patch('morphosource_api.requests.Session.get')
    def test_get_total_count(self, mock_get):
        """Test getting total count of records"""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_api_response
        mock_get.return_value = mock_response
        
        # Call the method
        count = self.api.get_total_count(query="X-Ray Computed Tomography")
        
        # Verify
        self.assertEqual(count, 108000)
    
    @patch('morphosource_api.requests.Session.get')
    def test_get_latest_records(self, mock_get):
        """Test getting latest records"""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.sample_api_response
        mock_get.return_value = mock_response
        
        # Call the method
        records = self.api.get_latest_records(n=1, query="X-Ray Computed Tomography")
        
        # Verify
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['id'], '000123456')
    
    def test_normalize_record_with_list_values(self):
        """Test normalization handles list values correctly"""
        api_record = {
            'id': 'test123',
            'title_sms': ['Test Title'],
            'taxonomy_class_sms': ['Class1', 'Class2'],
            'object_id_sms': ['OBJ-001', 'OBJ-002']
        }
        
        normalized = self.api.normalize_record(api_record)
        
        # Should handle lists properly
        self.assertEqual(normalized['title'], 'Test Title')
        self.assertIn('Taxonomy', normalized['metadata'])
        self.assertIn('Object', normalized['metadata'])
    
    def test_normalize_record_with_missing_fields(self):
        """Test normalization handles missing fields gracefully"""
        api_record = {
            'id': 'test456',
            'title': 'Minimal Record'
        }
        
        normalized = self.api.normalize_record(api_record)
        
        # Should still create a valid record
        self.assertEqual(normalized['id'], 'test456')
        self.assertIn('title', normalized)
        self.assertIn('metadata', normalized)
        self.assertIsInstance(normalized['metadata'], dict)


class TestBackwardCompatibility(unittest.TestCase):
    """Test that the API client maintains backward compatibility"""
    
    def setUp(self):
        self.api = MorphoSourceAPI()
    
    def test_normalized_record_format(self):
        """Test that normalized records match the old scraping format"""
        api_record = {
            'id': '000789012',
            'title_sms': ['Test Record'],
            'taxonomy_class_sms': ['Aves'],
            'element_sms': ['wing'],
            'object_id_sms': ['BIRD-123'],
            'publication_status_sms': ['published'],
            'data_manager_sms': ['John Doe']
        }
        
        normalized = self.api.normalize_record(api_record)
        
        # Check old format fields exist
        expected_fields = ['id', 'title', 'url', 'detail_url', 'metadata']
        for field in expected_fields:
            self.assertIn(field, normalized)
        
        # Check metadata has expected keys
        metadata = normalized['metadata']
        self.assertIn('Element or Part', metadata)
        self.assertIn('Object', metadata)
        self.assertIn('Publication Status', metadata)
        self.assertIn('Data Manager', metadata)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMorphoSourceAPI))
    suite.addTests(loader.loadTestsFromTestCase(TestBackwardCompatibility))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    import sys
    sys.exit(run_tests())
