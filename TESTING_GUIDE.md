# Phase 5 Testing Guide: ZEEP Migration

## Quick Start

**Status:** Code migration complete, ready for testing
**Risk Level:** HIGH - SOAP client replacement requires thorough testing

## Step 1: Install ZEEP Dependencies

```bash
cd "/Users/simon/vsCodeProjects/Indigo/UK-Trains/UKTrains.indigoPlugin/Contents/Server Plugin"

# Install using Indigo's Python
/Library/Frameworks/Python.framework/Versions/Current/bin/python3 -m pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed zeep-4.2.1 lxml-4.9.0 requests-2.31.0 ...
```

## Step 2: Test ZEEP Client Creation

```bash
cd "/Users/simon/vsCodeProjects/Indigo/UK-Trains/UKTrains.indigoPlugin/Contents/Server Plugin"
python3 test_zeep_connection.py
```

**Expected output:**
```
Creating Darwin session with ZEEP...
✅ ZEEP client created successfully
   SOAP client type: <class 'zeep.client.Client'>
   Available services: ['GetDepartureBoard', 'GetArrivalBoard', ...]
```

**If it fails:**
- Check internet connection (downloads WSDL)
- Verify ZEEP installed correctly: `python3 -c "import zeep; print(zeep.__version__)"`
- Check firewall isn't blocking HTTPS to nationalrail.co.uk

## Step 3: Test Module Imports

```bash
# Test webservice module
python3 -c "from nredarwin.webservice import DarwinLdbSession; print('✅ webservice OK')"

# Test darwin_api module
python3 -c "from darwin_api import nationalRailLogin; print('✅ darwin_api OK')"

# Test plugin module (may show Indigo warnings, that's OK)
python3 -c "import sys; sys.path.insert(0, '.'); from plugin import Plugin; print('✅ plugin OK')" 2>&1 | grep -E "(✅|error|import)"
```

## Step 4: Test Darwin API Login (Optional)

**IMPORTANT:** Requires a valid Darwin API key

```bash
python3 << 'PYEOF'
import sys
sys.path.insert(0, '.')
from darwin_api import nationalRailLogin

# Replace with your actual API key
API_KEY = "your_key_here"
WSDL = "https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx"

success, session = nationalRailLogin(wsdl=WSDL, api_key=API_KEY)
if success:
    print("✅ Darwin login successful!")
    print(f"   Session type: {type(session)}")
else:
    print("❌ Darwin login failed")
PYEOF
```

## Step 5: Install in Indigo (Full Integration Test)

### 5.1 Copy Plugin to Indigo

```bash
# Copy to disabled plugins folder first
cp -r "/Users/simon/vsCodeProjects/Indigo/UK-Trains/UKTrains.indigoPlugin" \
    "/Library/Application Support/Perceptive Automation/Indigo 2023.2/Plugins (Disabled)/"
```

### 5.2 Enable Plugin in Indigo

1. Open Indigo
2. Go to **Plugins → Manage Plugins**
3. Find "UK Trains" in disabled plugins
4. Click "Enable"
5. Configure with your Darwin API key

### 5.3 Monitor Indigo Logs

1. Open **View → Event Log Window**
2. Look for plugin startup messages
3. Check for ZEEP-related errors

**Expected log messages:**
```
UK Trains: Starting UK Trains Plugin
UK Trains: Successfully loaded station codes
UK Trains: Plugin initialized
```

**WARNING signs:**
```
UK Trains: ** Couldn't find zeep module: ...
UK Trains: WARNING ** Failed to log in to Darwin: ...
UK Trains: WARNING ** SOAP resolution failed: ...
```

### 5.4 Create Test Device

1. Go to **Devices → New Device**
2. Type: "UK Trains Plugin"
3. Model: "Train Timetable"
4. Configure:
   - **Departure Station:** WAT (London Waterloo)
   - **Destination Station:** VIC (London Victoria)
   - **Refresh Interval:** 60 seconds
5. Click **Save**

### 5.5 Verify Device Updates

**Check device states:**
1. Select the device
2. Click **Edit Device Settings**
3. Go to **States** tab
4. Verify states are updating:
   - `Train01Dest` should show "London Victoria"
   - `Train01Op` should show operator name
   - `Train01Sch` should show departure time
   - `Train01Est` should show "On time" or estimated time

**Check image generation:**
1. Device should create PNG image in:
   `/Users/simon/Documents/IndigoWebServer/images/`
2. File named like: `WAT_VIC_departures.png`

## Step 6: Test Error Handling

### Test 6.1: Invalid CRS Code
1. Edit device
2. Set Destination to "XXX" (invalid)
3. Save and wait for update
4. **Expected:** Error logged, device continues working

### Test 6.2: Network Timeout
1. Disconnect internet
2. Wait for device update
3. **Expected:** Retry attempts logged, graceful failure
4. Reconnect internet
5. **Expected:** Next update succeeds

### Test 6.3: Invalid API Key
1. Edit plugin config
2. Set invalid API key
3. Reload plugin
4. **Expected:** Login failure logged, plugin handles gracefully

## Step 7: Performance Check

Compare ZEEP vs SUDS performance:

1. **Response time:** Check device update duration in logs
2. **Memory usage:** Monitor Indigo Server memory
3. **CPU usage:** Watch for spikes during updates

**Typical benchmarks:**
- Station board fetch: < 2 seconds
- Service details fetch: < 1 second
- Image generation: < 1 second

## Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'zeep'"
**Solution:**
```bash
/Library/Frameworks/Python.framework/Versions/Current/bin/python3 -m pip install zeep
```

### Problem: "TypeError: ... got an unexpected keyword argument '_soapheaders'"
**Cause:** ZEEP version mismatch
**Solution:**
```bash
pip install --upgrade zeep>=4.2.1
```

### Problem: WSDL download fails
**Symptoms:** "Error fetching WSDL"
**Solutions:**
1. Check internet connection
2. Verify URL accessible: `curl -I https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx`
3. Check firewall settings

### Problem: SOAP header authentication fails
**Symptoms:** "Access denied" or "Invalid token"
**Solutions:**
1. Verify API key is correct
2. Check Darwin API key is active at: https://developer.nationalrail.co.uk/
3. Review SOAP header in debug logs (if enabled)

### Problem: Response parsing errors
**Symptoms:** AttributeError when accessing service data
**Solutions:**
1. Enable debug logging in plugin config
2. Check if Darwin API response format changed
3. Compare ZEEP response structure with expected structure

## Rollback Procedure

If ZEEP migration fails and you need to revert to SUDS:

```bash
cd "/Users/simon/vsCodeProjects/Indigo/UK-Trains/UKTrains.indigoPlugin/Contents/Server Plugin"

# Restore original files from git (if committed)
git checkout HEAD -- nredarwin/webservice.py
git checkout HEAD -- darwin_api.py
git checkout HEAD -- plugin.py
git checkout HEAD -- requirements.txt

# Or restore from Phase 4 backup
# (assuming you created backups before Phase 5)

# Reinstall SUDS
pip uninstall -y zeep lxml
pip install suds==1.1.2

# Reload plugin in Indigo
```

## Success Criteria

Check all boxes before considering migration successful:

- [ ] ZEEP installs without errors
- [ ] test_zeep_connection.py succeeds
- [ ] All module imports work
- [ ] Darwin API login succeeds
- [ ] Plugin loads in Indigo without errors
- [ ] Device creates successfully
- [ ] Device states update with live data
- [ ] Departure board image generates
- [ ] Error handling works (tested invalid input)
- [ ] Performance is acceptable (< 3s per update)
- [ ] No memory leaks after 100+ updates
- [ ] Multiple devices work simultaneously

## Next Steps After Testing

Once all tests pass:

1. **Document any issues found**
   - Create GitHub issues for bugs
   - Note any behavioral differences from SUDS

2. **Update documentation**
   - Update CLAUDE.md with ZEEP requirements
   - Update README with new dependencies

3. **Commit changes** (only after all tests pass!)
   ```bash
   git add .
   git commit -m "Phase 5: Migrate from SUDS to ZEEP

   - Replace unmaintained SUDS (2010) with modern ZEEP (4.2.1+)
   - Update SOAP client implementation in webservice.py
   - Update exception handling throughout codebase
   - Add lxml and requests dependencies
   - All tests passing

   Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
   ```

4. **Tag release**
   ```bash
   git tag -a phase5-zeep-migration -m "SUDS to ZEEP migration complete"
   ```

## Support Resources

- **ZEEP Documentation:** https://docs.python-zeep.org/
- **Darwin API Docs:** https://developer.nationalrail.co.uk/
- **Indigo Developer Forum:** https://forums.indigodomo.com/viewforum.php?f=18

## Notes

- Keep `test_zeep_connection.py` until thoroughly tested in production
- Monitor Indigo logs for first 24 hours after deployment
- Have rollback plan ready (keep SUDS version tagged in git)
- Consider gradual rollout (test on non-critical devices first)

---

**Last Updated:** 2026-01-28
**Phase:** 5 (ZEEP Migration)
**Author:** Claude Sonnet 4.5
