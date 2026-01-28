#!/usr/bin/env python3
"""
Test ZEEP connection to Darwin API

This verifies ZEEP can successfully create a client and connect.
"""

import sys
sys.path.insert(0, '.')

from nredarwin.webservice import DarwinLdbSession

def test_zeep_client():
    """Test ZEEP client creation"""
    wsdl = 'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx'

    # Use a dummy API key for connection test (won't make actual calls)
    api_key = 'test_key_12345'

    try:
        print("Creating Darwin session with ZEEP...")
        session = DarwinLdbSession(wsdl=wsdl, api_key=api_key, timeout=10)
        print("✅ ZEEP client created successfully")
        print(f"   SOAP client type: {type(session._soap_client)}")

        # Try to list available operations
        try:
            service_binding = session._soap_client.bind('LDBServiceSoap')
            operations = list(service_binding._operations.keys())[:5]
            print(f"   Available services: {operations}")
        except Exception as e:
            print(f"   Could not list operations: {e}")

        return True
    except Exception as e:
        print(f"❌ ZEEP client creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_zeep_client()
    sys.exit(0 if success else 1)
