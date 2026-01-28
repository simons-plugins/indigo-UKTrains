#!/usr/bin/env python3
"""
Inspect Darwin WSDL to see available services
"""

import sys
import os
from pathlib import Path

# Load .env
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

try:
    from zeep import Client
    from zeep.transports import Transport
    from requests import Session
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

def inspect_wsdl():
    """Inspect the Darwin WSDL and list available services"""
    wsdl = os.getenv('DARWIN_WSDL', 'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx')
    api_key = os.getenv('DARWIN_API_KEY')

    print(f"Inspecting WSDL: {wsdl}\n")

    # Create client
    session = Session()
    transport = Transport(session=session, timeout=10)
    client = Client(wsdl, transport=transport)

    # List all services
    print("Available Services:")
    print("=" * 60)
    for service_name in client.wsdl.services:
        print(f"\n📋 Service: {service_name}")
        service = client.wsdl.services[service_name]

        # List all ports in the service
        for port_name, port in service.ports.items():
            print(f"  └─ Port: {port_name}")
            print(f"     Binding: {port.binding.name.localname}")

            # List all operations
            binding = port.binding
            print(f"     Operations:")
            for operation_name in binding._operations:
                print(f"       • {operation_name}")

    print("\n" + "=" * 60)
    print("\n💡 Try these binding names:")
    for service_name in client.wsdl.services:
        service = client.wsdl.services[service_name]
        for port_name in service.ports:
            print(f"   client.bind('{port_name}')")

if __name__ == '__main__':
    try:
        inspect_wsdl()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
