#!/usr/bin/env python3
"""
Test script to verify the MorphoSource API client can be imported and initialized.
This does not make actual API calls.
"""

import sys
import os

def test_api_client_import():
    """Test that the API client can be imported"""
    try:
        from morphosource_api import MorphoSourceAPIClient
        print("✓ Successfully imported MorphoSourceAPIClient")
        return True
    except ImportError as e:
        print(f"✗ Failed to import MorphoSourceAPIClient: {e}")
        return False

def test_api_client_init():
    """Test that the API client can be initialized"""
    try:
        from morphosource_api import MorphoSourceAPIClient
        
        # Initialize with a dummy key (won't make actual calls)
        client = MorphoSourceAPIClient("test_key_12345")
        print("✓ Successfully initialized MorphoSourceAPIClient")
        
        # Check that basic attributes exist
        assert hasattr(client, 'api_key'), "Client missing api_key attribute"
        assert hasattr(client, 'session'), "Client missing session attribute"
        assert hasattr(client, 'logger'), "Client missing logger attribute"
        print("✓ Client has all required attributes")
        
        return True
    except Exception as e:
        print(f"✗ Failed to initialize MorphoSourceAPIClient: {e}")
        return False

def test_api_client_methods():
    """Test that the API client has all required methods"""
    try:
        from morphosource_api import MorphoSourceAPIClient
        
        client = MorphoSourceAPIClient("test_key_12345")
        
        required_methods = [
            'search_media',
            'get_media_by_id',
            'get_all_xray_ct_records',
            'get_recent_records',
            'get_modified_records',
            'parse_record_to_legacy_format'
        ]
        
        for method in required_methods:
            assert hasattr(client, method), f"Client missing {method} method"
            print(f"✓ Client has {method} method")
        
        return True
    except Exception as e:
        print(f"✗ Failed method check: {e}")
        return False

def test_legacy_scripts_import():
    """Test that updated scripts can be imported"""
    scripts = [
        'scrape_morphosource',
        'daily',
        'monthly',
        'check_modified_morphosource'
    ]
    
    all_passed = True
    # Get the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    for script in scripts:
        try:
            # We don't actually import because they have main() calls
            # Just check the file exists and has correct syntax
            script_path = os.path.join(script_dir, f"{script}.py")
            if os.path.exists(script_path):
                with open(script_path, 'r') as f:
                    content = f.read()
                    if 'from morphosource_api import MorphoSourceAPIClient' in content:
                        print(f"✓ {script}.py imports MorphoSourceAPIClient")
                    else:
                        print(f"✗ {script}.py does not import MorphoSourceAPIClient")
                        all_passed = False
            else:
                print(f"✗ {script}.py not found at {script_path}")
                all_passed = False
        except Exception as e:
            print(f"✗ Error checking {script}.py: {e}")
            all_passed = False
    
    return all_passed

def main():
    print("=" * 60)
    print("MorphoSource API Client Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        ("Import Test", test_api_client_import),
        ("Initialization Test", test_api_client_init),
        ("Methods Test", test_api_client_methods),
        ("Legacy Scripts Import Test", test_legacy_scripts_import)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}")
        print("-" * 60)
        result = test_func()
        results.append((test_name, result))
        print()
    
    print("=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print()
    if all_passed:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
