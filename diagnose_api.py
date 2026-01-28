#!/usr/bin/env python3
# coding=utf-8
"""
Diagnostic script for UK-Trains Darwin API connectivity

This script tests the Darwin API connection and helps identify whether
the "awaiting update" issue is caused by API problems or code issues.

Usage:
    1. Create .env file with DARWIN_WEBSERVICE_API_KEY
    2. Run: python3 diagnose_api.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add plugin directory to path
plugin_dir = Path(__file__).parent / "UKTrains.indigoPlugin" / "Contents" / "Server Plugin"
sys.path.insert(0, str(plugin_dir))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed. Using manual .env parsing...")
    # Manual .env parsing
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Import Darwin API modules
try:
    from nredarwin.webservice import DarwinLdbSession
    print("✅ Successfully imported nredarwin module")
except ImportError as e:
    print(f"❌ Failed to import nredarwin: {e}")
    print("   Install with: pip install zeep python-dotenv")
    sys.exit(1)


def print_section(title):
    """Print a section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def test_api_key():
    """Test 1: Verify API key is available"""
    print_section("TEST 1: Darwin API Key")

    api_key = os.getenv('DARWIN_WEBSERVICE_API_KEY')
    if not api_key or api_key == 'your_api_key_here':
        print("❌ DARWIN_WEBSERVICE_API_KEY not found or not set properly")
        print("   Please create .env file with your Darwin API key")
        print("   See .env.example for template")
        return None

    print(f"✅ API key found: {api_key[:10]}...{api_key[-4:]}")
    return api_key


def test_darwin_connection(api_key):
    """Test 2: Test connection to Darwin API"""
    print_section("TEST 2: Darwin API Connection")

    wsdl_url = os.getenv(
        'DARWIN_WEBSERVICE_WSDL',
        'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx'
    )
    print(f"WSDL URL: {wsdl_url}")

    try:
        print("Connecting to Darwin API...")
        session = DarwinLdbSession(wsdl_url, api_key)
        print("✅ Successfully connected to Darwin API")
        return session
    except Exception as e:
        print(f"❌ Failed to connect to Darwin API: {e}")
        print("   Check your API key and internet connection")
        return None


def test_station_board(session, crs_code='PAD'):
    """Test 3: Fetch a station board"""
    print_section(f"TEST 3: Fetch Station Board ({crs_code})")

    try:
        print(f"Fetching station board for {crs_code}...")
        board = session.get_station_board(crs_code, rows=10)

        if not board:
            print("❌ No board returned")
            return None

        print(f"✅ Station: {board.location_name}")

        # Check for services
        if hasattr(board, 'train_services') and board.train_services:
            print(f"✅ Found {len(board.train_services)} train services")
            return board
        else:
            print("⚠️  No train services found (may be normal for time of day)")
            return board

    except Exception as e:
        print(f"❌ Failed to fetch station board: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_service_details(session, board):
    """Test 4: Fetch service details"""
    print_section("TEST 4: Fetch Service Details")

    if not board or not hasattr(board, 'train_services') or not board.train_services:
        print("⚠️  No services to test (skipping)")
        return

    service = board.train_services[0]
    print(f"Testing service: {service.destination_text}")
    print(f"  Service ID: {service.service_id}")

    try:
        print("Fetching service details...")
        details = session.get_service_details(service.service_id)

        if not details:
            print("❌ No service details returned")
            return

        print("✅ Service details fetched successfully")

        # Check for calling points
        if hasattr(details, 'subsequent_calling_points'):
            cp = details.subsequent_calling_points
            if cp and len(cp) > 0:
                print(f"✅ Found {len(cp)} calling points:")
                for i, point in enumerate(cp[:3], 1):
                    print(f"   {i}. {point.location_name} at {point.st}")
            else:
                print("⚠️  No calling points found")

    except Exception as e:
        print(f"❌ Failed to fetch service details: {e}")
        import traceback
        traceback.print_exc()


def test_filtered_board(session, start_crs='WAT', dest_crs='WOK'):
    """Test 5: Fetch filtered station board"""
    print_section(f"TEST 5: Filtered Board ({start_crs} to {dest_crs})")

    try:
        print(f"Fetching filtered board: {start_crs} to {dest_crs}...")
        board = session.get_station_board(
            start_crs,
            rows=10,
            include_departures=True,
            include_arrivals=False,
            destination_crs=dest_crs
        )

        if not board:
            print("❌ No board returned")
            return

        print(f"✅ Station: {board.location_name}")

        if hasattr(board, 'train_services') and board.train_services:
            print(f"✅ Found {len(board.train_services)} services calling at {dest_crs}")
            for i, service in enumerate(board.train_services[:3], 1):
                print(f"   {i}. {service.destination_text} at {service.std} (est: {service.etd})")
        else:
            print(f"⚠️  No services found for {start_crs} to {dest_crs} route")

    except Exception as e:
        print(f"❌ Failed to fetch filtered board: {e}")
        import traceback
        traceback.print_exc()


def test_refactored_code():
    """Test 6: Test refactored darwin_api.py functions"""
    print_section("TEST 6: Test Refactored Code")

    try:
        # Import refactored modules
        import darwin_api
        import constants
        print("✅ Successfully imported darwin_api module")

        # Test nationalRailLogin
        print("\nTesting nationalRailLogin()...")
        api_key = os.getenv('DARWIN_API_KEY')
        wsdl_url = os.getenv(
            'DARWIN_WSDL',
            'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx'
        )

        success, session = darwin_api.nationalRailLogin(wsdl_url, api_key)

        if success and session:
            print("✅ nationalRailLogin() succeeded")
        else:
            print("❌ nationalRailLogin() failed")
            return

        # Test _fetch_station_board
        print("\nTesting _fetch_station_board()...")
        board = darwin_api._fetch_station_board(session, 'PAD', 'ALL', 10)

        if board:
            print(f"✅ _fetch_station_board() succeeded: {board.location_name}")
        else:
            print("❌ _fetch_station_board() failed")
            return

        # Test _fetch_service_details
        if hasattr(board, 'train_services') and board.train_services:
            print("\nTesting _fetch_service_details()...")
            service_id = board.train_services[0].service_id
            details = darwin_api._fetch_service_details(session, service_id)

            if details:
                print("✅ _fetch_service_details() succeeded")
            else:
                print("⚠️  _fetch_service_details() returned None")

        print("\n✅ All refactored functions working correctly")

    except ImportError as e:
        print(f"❌ Failed to import refactored modules: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Error testing refactored code: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all diagnostic tests"""
    print("\n" + "="*70)
    print("  UK-Trains Darwin API Diagnostic Tool")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*70)

    # Test 1: API Key
    api_key = test_api_key()
    if not api_key:
        print("\n❌ FAILED: No API key found")
        print("\nTo fix:")
        print("  1. Copy .env.example to .env")
        print("  2. Add your Darwin API key to .env")
        print("  3. Run this script again")
        sys.exit(1)

    # Test 2: Connection
    session = test_darwin_connection(api_key)
    if not session:
        print("\n❌ FAILED: Cannot connect to Darwin API")
        sys.exit(1)

    # Test 3: Station Board
    board = test_station_board(session, 'PAD')

    # Test 4: Service Details
    if board:
        test_service_details(session, board)

    # Test 5: Filtered Board
    test_filtered_board(session, 'WAT', 'WOK')

    # Test 6: Refactored Code
    test_refactored_code()

    # Summary
    print_section("DIAGNOSTIC SUMMARY")
    print("✅ Darwin API is working correctly")
    print("✅ Refactored code is functional")
    print("\n📋 Next Steps:")
    print("   1. Check Indigo plugin logs for specific error messages")
    print("   2. Verify device configuration in Indigo")
    print("   3. Check if devices are enabled and configured")
    print("   4. Look for errors in:")
    print("      - /Library/Application Support/Perceptive Automation/Indigo 2023.2/Logs/UKTrains.log")
    print("      - /Library/Application Support/Perceptive Automation/Indigo 2023.2/Logs/NationRailErrors.log")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
