#!/usr/bin/env python3
"""
Test script for daily.py pagination and parquet functionality

This test verifies:
1. Full pagination mode fetches all records
2. Incremental mode stops at latest stored record  
3. Parquet files are created correctly
4. Error handling and retry logic works
"""
import sys
import os
import json
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from daily import DailyMorphoSourceExtractor

class TestDailyPaginationParquet(unittest.TestCase):
    """Test cases for daily.py pagination and parquet functionality"""
    
    def create_mock_api_response(self, page, per_page, total_records=250):
        """Create a mock API response for testing"""
        total_pages = (total_records + per_page - 1) // per_page
        
        # Calculate records for this page
        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total_records)
        
        records = []
        for i in range(start_idx, end_idx):
            records.append({
                'id': f'00078{8000 + i:04d}',
                'title_sms': [f'Test Record {i+1}'],
                'taxonomy_class_sms': ['Mammalia'],
                'element_sms': ['skull'],
            })
        
        return {
            'data': records,
            'meta': {
                'total': total_records,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages
            }
        }
    
    def test_full_pagination(self):
        """Test that fetch_all=True fetches all records"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = DailyMorphoSourceExtractor(data_dir=tmpdir)
            
            total_test_records = 250
            
            def mock_search_media(query, sort, page, per_page):
                return self.create_mock_api_response(page, per_page, total_test_records)
            
            with patch.object(extractor.api, 'search_media', side_effect=mock_search_media):
                records = extractor.get_all_records(fetch_all=True)
                
                self.assertEqual(len(records), total_test_records, 
                               f"Expected {total_test_records} records, got {len(records)}")
                self.assertEqual(records[0]['id'], '000788000', "First record ID incorrect")
                self.assertEqual(records[-1]['id'], '000788249', "Last record ID incorrect")
    
    def test_incremental_fetch(self):
        """Test that incremental fetch stops at latest stored record"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = DailyMorphoSourceExtractor(data_dir=tmpdir)
            
            total_test_records = 250
            latest_stored_id = '000788150'
            
            def mock_search_media(query, sort, page, per_page):
                return self.create_mock_api_response(page, per_page, total_test_records)
            
            with patch.object(extractor.api, 'search_media', side_effect=mock_search_media):
                records = extractor.get_all_records(latest_stored_id=latest_stored_id, fetch_all=False)
                
                # Should stop at or just after the stored record
                self.assertLessEqual(len(records), 151, 
                                   f"Expected <= 151 records, got {len(records)}")
                self.assertEqual(records[-1]['id'], latest_stored_id, 
                               "Did not stop at latest stored record")
    
    def test_parquet_creation(self):
        """Test that parquet files are created correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = DailyMorphoSourceExtractor(data_dir=tmpdir)
            
            test_records = [
                {
                    'id': '000123456',
                    'title': 'Test Record 1',
                    'url': 'https://www.morphosource.org/concern/media/000123456',
                    'metadata': {
                        'Taxonomy': 'Mammalia Primates',
                        'Element or Part': 'skull',
                        'Institution': 'Test University'
                    },
                    'scraped_date': '2024-01-01T00:00:00'
                }
            ]
            
            extractor.save_to_parquet(test_records)
            
            parquet_file = os.path.join(tmpdir, 'morphosource_data_complete.parquet')
            self.assertTrue(os.path.exists(parquet_file), "Parquet file not created")
            
            # Verify it can be read back
            try:
                import pandas as pd
                df = pd.read_parquet(parquet_file)
                self.assertEqual(len(df), 1, "Wrong number of records in parquet")
                self.assertIn('id', df.columns, "id column missing")
                self.assertIn('metadata_Taxonomy', df.columns, "metadata column missing")
            except ImportError:
                self.skipTest("pandas not available for parquet verification")
    
    def test_error_handling(self):
        """Test that API errors are handled with retry"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = DailyMorphoSourceExtractor(data_dir=tmpdir)
            
            call_count = [0]
            
            def mock_search_media_with_error(query, sort, page, per_page):
                call_count[0] += 1
                if call_count[0] <= 2:
                    # Fail first 2 times
                    from morphosource_api import MorphoSourceAPIError
                    raise MorphoSourceAPIError("Simulated API error")
                # Succeed on 3rd try
                return self.create_mock_api_response(page, per_page, 100)
            
            with patch.object(extractor.api, 'search_media', side_effect=mock_search_media_with_error):
                records = extractor.get_all_records(fetch_all=True)
                
                # Should eventually succeed after retries
                self.assertEqual(len(records), 100, "Should have recovered from errors")
                self.assertGreater(call_count[0], 1, "Should have retried after errors")
    
    def test_metadata_flattening(self):
        """Test that metadata is correctly flattened for parquet"""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = DailyMorphoSourceExtractor(data_dir=tmpdir)
            
            test_records = [
                {
                    'id': '000123456',
                    'title': 'Test',
                    'url': 'http://test.com',
                    'metadata': {
                        'Key With Spaces': 'value1',
                        'Key/With/Slash': 'value2'
                    },
                    'scraped_date': '2024-01-01T00:00:00'
                }
            ]
            
            extractor.save_to_parquet(test_records)
            
            try:
                import pandas as pd
                parquet_file = os.path.join(tmpdir, 'morphosource_data_complete.parquet')
                df = pd.read_parquet(parquet_file)
                
                # Check that column names are sanitized
                self.assertIn('metadata_Key_With_Spaces', df.columns, 
                            "Spaces should be replaced with underscores")
                self.assertIn('metadata_Key_With_Slash', df.columns, 
                            "Slashes should be replaced with underscores")
            except ImportError:
                self.skipTest("pandas not available for parquet verification")


if __name__ == '__main__':
    unittest.main(verbosity=2)
