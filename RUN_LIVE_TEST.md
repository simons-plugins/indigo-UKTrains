# Running Live Darwin API Tests

## Quick Test (Main Diagnostic Tool)

The main diagnostic script tests all components:

```bash
cd /Users/simon/vsCodeProjects/Indigo/UK-Trains

# Run with your API key
python3 test_darwin_live.py "YOUR_DARWIN_API_KEY_HERE"

# Or set environment variable first
export DARWIN_API_KEY="YOUR_DARWIN_API_KEY_HERE"
python3 test_darwin_live.py
```

This tests:
1. ✅ ZEEP installation
2. ✅ Plugin module imports
3. ✅ Darwin session creation
4. ✅ nationalRailLogin() function
5. ✅ Station board retrieval
6. ✅ Filtered board (route-specific)
7. ✅ Service details
8. ✅ Delay calculation

## Pytest Integration Tests

For more comprehensive testing with pytest:

```bash
cd /Users/simon/vsCodeProjects/Indigo/UK-Trains

# Set API key
export DARWIN_API_KEY="YOUR_DARWIN_API_KEY_HERE"

# Run all live API tests
pytest -m live_api tests/integration/test_live_darwin_api.py -v -s

# Run specific test
pytest -m live_api tests/integration/test_live_darwin_api.py::TestLiveDarwinAPI::test_get_station_board_london_paddington -v -s
```

## Simple ZEEP Connection Test

Quick test to verify ZEEP can connect:

```bash
cd /Users/simon/vsCodeProjects/Indigo/UK-Trains/UKTrains.indigoPlugin/Contents/Server\ Plugin
python3 test_zeep_connection.py
```

## Troubleshooting "Awaiting Update" Issue

If plugin shows "awaiting update" and never updates:

### 1. Check Indigo Logs
```bash
tail -f "/Library/Application Support/Perceptive Automation/Indigo 2023.2/Logs/UKTrains.log"
```

### 2. Check Plugin Is Running
- Open Indigo → Plugins → Manage Plugins
- Verify UK-Trains plugin is **Enabled**
- Check "Concurrent Thread" is running

### 3. Verify Device Configuration
- Device Edit → Configuration
- Check CRS codes are valid (e.g., PAD, BRI, WAT)
- Check "Station Name" matches CRS code

### 4. Check Darwin API Key
- Plugins → UK-Trains → Configure
- Verify Darwin API key is entered correctly
- Get key from: https://www.nationalrail.co.uk/developers/

### 5. Force Device Update
In Indigo:
- Select the stuck device
- Actions → Device Actions → Refresh
- Or disable/enable the device

### 6. Check Python Dependencies
```bash
cd /Users/simon/vsCodeProjects/Indigo/UK-Trains/UKTrains.indigoPlugin/Contents/Server\ Plugin
/Library/Frameworks/Python.framework/Versions/Current/bin/python3 -c "import zeep; print('ZEEP OK')"
```

If error:
```bash
/Library/Frameworks/Python.framework/Versions/Current/bin/python3 -m pip install -r requirements.txt
```

### 7. Check Network/Firewall
```bash
curl -I https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx
```

Should return `HTTP/1.1 200 OK`

## Common Issues

### "Module 'zeep' not found"
```bash
/Library/Frameworks/Python.framework/Versions/Current/bin/python3 -m pip install zeep lxml requests
```

### "SOAP Fault: Invalid Token"
- Darwin API key is wrong or expired
- Get new key from National Rail

### "Connection timeout"
- Network firewall blocking HTTPS to nationalrail.co.uk
- Check proxy settings
- Try from different network

### "No services found"
- Normal late at night (no trains running)
- Check CRS codes are correct
- Try major station like PAD or VIC

## Getting Darwin API Key

1. Visit: https://www.nationalrail.co.uk/developers/
2. Register for free account
3. Create new API token
4. Copy the token (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
5. Add to Indigo plugin configuration
