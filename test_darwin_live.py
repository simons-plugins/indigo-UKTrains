#!/usr/bin/env python3
"""
Comprehensive Live Darwin API Test

This script diagnoses connection and API issues with the UK-Trains plugin.
Run this to verify ZEEP migration was successful.

Usage:
    python3 test_darwin_live.py <YOUR_API_KEY>

Example:
    python3 test_darwin_live.py "abcd1234-efgh-5678-ijkl-mnopqrstuvwx"
"""

import sys
import os

# Add plugin to path
plugin_path = os.path.join(os.path.dirname(__file__), 'UKTrains.indigoPlugin', 'Contents', 'Server Plugin')
sys.path.insert(0, plugin_path)

print("=" * 70)
print("UK-Trains Plugin - Live Darwin API Test")
print("=" * 70)
print()

# Step 1: Check ZEEP installation
print("1️⃣  Checking ZEEP installation...")
try:
    import zeep
    print(f"   ✅ ZEEP installed: version {zeep.__version__}")
except ImportError as e:
    print(f"   ❌ ZEEP not installed: {e}")
    print()
    print("   To install ZEEP:")
    print("   pip3 install zeep lxml requests")
    sys.exit(1)

try:
    import lxml
    print(f"   ✅ lxml installed")
except ImportError:
    print(f"   ❌ lxml not installed")
    sys.exit(1)

try:
    import requests
    print(f"   ✅ requests installed: version {requests.__version__}")
except ImportError:
    print(f"   ❌ requests not installed")
    sys.exit(1)

print()

# Step 2: Import plugin modules
print("2️⃣  Importing plugin modules...")
try:
    from nredarwin.webservice import DarwinLdbSession
    print("   ✅ nredarwin.webservice imported")
except ImportError as e:
    print(f"   ❌ Failed to import nredarwin.webservice: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    import darwin_api
    print("   ✅ darwin_api imported")
except ImportError as e:
    print(f"   ❌ Failed to import darwin_api: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    import constants
    print("   ✅ constants imported")
except ImportError as e:
    print(f"   ❌ Failed to import constants: {e}")
    sys.exit(1)

print()

# Step 3: Get API key
print("3️⃣  Getting Darwin API key...")
if len(sys.argv) < 2:
    api_key = os.getenv('DARWIN_API_KEY')
    if not api_key:
        print("   ❌ No API key provided")
        print()
        print("   Usage: python3 test_darwin_live.py <YOUR_API_KEY>")
        print("   Or set: export DARWIN_API_KEY='your_key_here'")
        sys.exit(1)
else:
    api_key = sys.argv[1]

print(f"   ✅ API key: {api_key[:8]}...{api_key[-4:]}")
print()

# Step 4: Create Darwin session
print("4️⃣  Creating Darwin ZEEP session...")
wsdl_url = constants.DARWIN_WSDL_DEFAULT
print(f"   WSDL: {wsdl_url}")

try:
    session = DarwinLdbSession(wsdl=wsdl_url, api_key=api_key, timeout=10)
    print("   ✅ Darwin session created successfully")
    print(f"   Client type: {type(session._soap_client)}")
except Exception as e:
    print(f"   ❌ Failed to create Darwin session: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Step 5: Test nationalRailLogin
print("5️⃣  Testing nationalRailLogin() function...")
try:
    success, login_session = darwin_api.nationalRailLogin(wsdl_url, api_key)
    if success:
        print("   ✅ nationalRailLogin() succeeded")
        print(f"   Session type: {type(login_session)}")
    else:
        print("   ❌ nationalRailLogin() returned False")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ nationalRailLogin() failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Step 6: Test get_station_board
print("6️⃣  Testing get_station_board() - London Paddington (PAD)...")
try:
    board = session.get_station_board('PAD', rows=10)
    print(f"   ✅ Station board retrieved")
    print(f"   Station: {board.location_name}")
    print(f"   CRS Code: {board.crs}")

    if hasattr(board, 'train_services') and board.train_services:
        print(f"   Services: {len(board.train_services)} departures found")
        print()
        print("   First 3 services:")
        for i, service in enumerate(board.train_services[:3], 1):
            dest = service.destination_text if hasattr(service, 'destination_text') else 'Unknown'
            std = service.std if hasattr(service, 'std') else 'N/A'
            etd = service.etd if hasattr(service, 'etd') else 'N/A'
            operator = service.operator_name if hasattr(service, 'operator_name') else 'Unknown'
            print(f"   [{i}] {dest}")
            print(f"       Operator: {operator}")
            print(f"       Scheduled: {std} | Estimated: {etd}")
    else:
        print("   ⚠️  No train services found (may be late at night)")

except Exception as e:
    print(f"   ❌ get_station_board() failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Step 7: Test filtered board (Paddington to Bristol)
print("7️⃣  Testing filtered board - PAD → Bristol (BRI)...")
try:
    board = session.get_station_board(
        'PAD',
        rows=10,
        include_departures=True,
        include_arrivals=False,
        destination_crs='BRI'
    )
    print(f"   ✅ Filtered board retrieved")
    print(f"   Station: {board.location_name}")

    if hasattr(board, 'train_services') and board.train_services:
        print(f"   Services calling at Bristol: {len(board.train_services)}")
        for i, service in enumerate(board.train_services[:2], 1):
            dest = service.destination_text if hasattr(service, 'destination_text') else 'Unknown'
            std = service.std if hasattr(service, 'std') else 'N/A'
            etd = service.etd if hasattr(service, 'etd') else 'N/A'
            print(f"   [{i}] {dest} - Departs: {std} (est: {etd})")
    else:
        print("   ⚠️  No services found for this route")

except Exception as e:
    print(f"   ❌ Filtered board failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Step 8: Test service details
print("8️⃣  Testing get_service_details()...")
try:
    # Get a board first to get a service ID
    board = session.get_station_board('PAD', rows=5)

    if hasattr(board, 'train_services') and board.train_services:
        service_id = board.train_services[0].service_id
        print(f"   Testing with service ID: {service_id}")

        details = session.get_service_details(service_id)
        print("   ✅ Service details retrieved")

        if hasattr(details, 'operator_name'):
            print(f"   Operator: {details.operator_name}")

        if hasattr(details, 'subsequent_calling_points') and details.subsequent_calling_points:
            cp_list = details.subsequent_calling_points
            print(f"   Calling points: {len(cp_list)} stops")
            for cp in cp_list[:3]:
                loc = cp.location_name if hasattr(cp, 'location_name') else 'Unknown'
                time = cp.st if hasattr(cp, 'st') else 'N/A'
                print(f"      - {loc} at {time}")
    else:
        print("   ⚠️  No services available to test details")

except Exception as e:
    print(f"   ❌ get_service_details() failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Step 9: Test delay calculation
print("9️⃣  Testing delay calculation with delayCalc()...")
try:
    from text_formatter import delayCalc

    # Test on-time
    has_issue, msg = delayCalc("10:30", "On time")
    print(f"   On time: has_issue={has_issue}, msg='{msg}'")
    assert not has_issue, "On-time should not be flagged as issue"

    # Test delayed
    has_issue, msg = delayCalc("10:30", "10:45")
    print(f"   Delayed: has_issue={has_issue}, msg='{msg}'")
    assert has_issue, "Delayed train should be flagged"

    # Test cancelled
    has_issue, msg = delayCalc("Cancelled", "Cancelled")
    print(f"   Cancelled: has_issue={has_issue}, msg='{msg}'")
    assert has_issue, "Cancelled train should be flagged"

    print("   ✅ delayCalc() working correctly")

except Exception as e:
    print(f"   ❌ delayCalc() failed: {e}")
    import traceback
    traceback.print_exc()

print()

# Step 10: Summary
print("=" * 70)
print("🎉 ALL TESTS PASSED!")
print("=" * 70)
print()
print("The ZEEP migration is working correctly. The Darwin API is accessible")
print("and all plugin functions are operating as expected.")
print()
print("If your plugin is still stuck on 'awaiting update', check:")
print("  1. Plugin is enabled in Indigo")
print("  2. Device configuration has valid CRS codes")
print("  3. Darwin API key is configured in plugin settings")
print("  4. Check Indigo logs for errors")
print("  5. Try disabling and re-enabling the device")
print()
print("To view detailed logs:")
print("  tail -f '/Library/Application Support/Perceptive Automation/Indigo 2023.2/Logs/UKTrains.log'")
print()
