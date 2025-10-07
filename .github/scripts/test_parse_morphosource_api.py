#!/usr/bin/env python3
"""
Test script for parse_morphosource_api.py to verify sort parameter is included.
"""

import unittest
from unittest.mock import patch, Mock
import sys
import os

# Add the scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock environment before importing
os.environ['GITHUB_OUTPUT'] = '/tmp/test_github_output'

import parse_morphosource_api


class TestParseMorphoSourceAPI(unittest.TestCase):
    """Test cases for parse_morphosource_api script"""
    
    @patch('parse_morphosource_api.requests.get')
    def test_sort_parameter_included(self, mock_get):
        """Test that the sort parameter is included in the API request"""
        # Create a mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.url = "https://www.morphosource.org/api/media?test=1"
        mock_response.json.return_value = {
            "response": {
                "pages": {
                    "total_count": 100
                },
                "media": [
                    {
                        "id": "123456",
                        "title_ssi": "Test Record"
                    }
                ]
            }
        }
        mock_get.return_value = mock_response
        
        # Call main (will use mocked requests.get)
        try:
            parse_morphosource_api.main()
        except SystemExit:
            pass  # Expected when script completes normally
        
        # Verify the get method was called
        self.assertTrue(mock_get.called, "requests.get should have been called")
        
        # Get the call arguments
        call_args = mock_get.call_args
        
        # Check that params include sort parameter
        if call_args:
            # Check kwargs for params
            if 'params' in call_args.kwargs:
                params = call_args.kwargs['params']
                self.assertIn('sort', params, "sort parameter should be in params")
                self.assertEqual(params['sort'], 'system_create_dtsi desc', 
                               "sort parameter should be 'system_create_dtsi desc'")
                print("✓ Sort parameter is correctly included in API request")
            else:
                self.fail("params not found in request call")
    
    def test_params_structure(self):
        """Test that the params dictionary includes all required fields"""
        # This is a simple structural test
        expected_keys = ['utf8', 'search_field', 'q', 'sort']
        
        # We'll just verify the code contains the sort parameter
        # by reading the source file
        script_path = os.path.join(os.path.dirname(__file__), 'parse_morphosource_api.py')
        with open(script_path, 'r') as f:
            content = f.read()
        
        # Check that sort parameter is defined in params
        self.assertIn('"sort":', content, "sort parameter should be defined in params dictionary")
        self.assertIn('system_create_dtsi desc', content, "sort should use 'system_create_dtsi desc'")
        print("✓ Source code includes sort parameter")


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestParseMorphoSourceAPI))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
