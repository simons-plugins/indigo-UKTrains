# Codebase Concerns

**Analysis Date:** 2026-02-01

## Tech Debt

**Hardcoded Python Path:**
- Issue: Python executable path is hardcoded in old codebase references but now relies on `sys.executable` in `constants.py` line 57, which could differ across environments
- Files: `constants.py:57`, references in subprocess calls `image_generator.py:79-81`
- Impact: May fail on systems where Python is installed in non-standard locations or when running under different Python interpreters
- Fix approach: Already partially addressed with `sys.executable`, but document this dependency clearly and test across Python versions

**Module-Level Pytz Availability Check:**
- Issue: Global `_MODULE_FAILPYTZ` flag set at import time (line 143 in `plugin.py`) runs before plugin instantiation, making it difficult to handle gracefully if pytz import fails during plugin operation
- Files: `plugin.py:143,226,229`, `text_formatter.py:15,18,31`
- Impact: Plugin cannot recover from pytz import failures; timezone handling falls back to GMT only without explicit warning to user
- Fix approach: Move pytz check into runtime configuration object and allow user to force timezone handling mode via preferences

**Subprocess Shell Integration Dependency:**
- Issue: Image generation relies on separate subprocess (`text2png.py`) spawned from main plugin process to avoid shared library conflicts with Indigo's embedded Python
- Files: `image_generator.py:79-89`, `plugin.py` (historic subprocess.call usage)
- Impact: Debugging is fragile (output logged to separate files), process lifecycle not fully managed, no timeout enforcement on subprocess
- Fix approach: Implement subprocess timeout with `subprocess.TimeoutExpired` handling, consolidate image generation into main plugin if possible

**Incomplete Tenacity Error Handling:**
- Issue: Retry decorator gracefully degrades to no-op if tenacity unavailable (lines 47-78 in `darwin_api.py`), but transient errors like timeouts are not retried in this case
- Files: `darwin_api.py:47-78`, `plugin.py:50-56`
- Impact: When tenacity unavailable, API calls fail immediately without retry, reducing reliability
- Fix approach: Implement fallback retry logic using built-in retry mechanism if tenacity missing

## Known Bugs

**HTML Stripping Not Implemented:**
- Symptoms: NRCC messages from Darwin API may contain HTML tags (noted in webservice.py line 207-208)
- Files: `nredarwin/webservice.py:207`, `device_manager.py:88-89`
- Trigger: When special messages are fetched from Darwin API for display on control pages
- Workaround: User must manually clean HTML from displayed messages; `formatSpecials()` attempts cleanup but is incomplete

**Service Details Fetch May Return None:**
- Symptoms: Calling points not displayed if service details API call fails; trains show incomplete information
- Files: `device_manager.py:221-224`, `darwin_api.py:125-146`
- Trigger: Transient API failures or network timeouts during `GetServiceDetails` call
- Workaround: Retry occurs automatically with tenacity, but if max retries exceeded, calling points silently omitted

**AttributeError Risk in Device State Updates:**
- Symptoms: Plugin crashes if Darwin API response contains unexpected schema (e.g., missing optional fields)
- Files: `device_manager.py:156-171`, `image_generator.py:112-116`
- Trigger: Darwin API schema change or malformed response from National Rail service
- Workaround: Extensive use of `getattr()` with defaults mitigates but not comprehensive; exception logs to stderr only

## Security Considerations

**API Key Exposure in Logs:**
- Risk: Darwin API key stored in plugin preferences and passed through function calls; risk of appearing in error logs or debug output
- Files: `config.py:41,58,158,164`, `darwin_api.py:150`
- Current mitigation: API key validation in config but no log sanitization; subprocess errors written to separate files outside plugin log
- Recommendations: Add explicit log message filtering to sanitize API keys before writing to logs; review error output in `myImageErrors.txt` and `myImageOutput.txt` for key leakage

**Subprocess Command Injection Risk:**
- Risk: File paths passed to subprocess without shell escaping; if user image path contains special characters or commands, could potentially be exploited
- Files: `image_generator.py:79-85`
- Current mitigation: Path objects used and converted to strings, but no shell=True so direct injection unlikely
- Recommendations: Continue avoiding shell=True; add validation to user-provided paths that subprocess will receive

**Environment Variable Dependency:**
- Risk: Darwin WSDL URL and API key can fall back to environment variables if not provided (webservice.py:33-35), potentially allowing injection attacks if environment is compromised
- Files: `nredarwin/webservice.py:33-35`
- Current mitigation: Function parameters override environment variables
- Recommendations: Document that environment variables are fallback only; consider removing this feature in favor of explicit parameter passing

## Performance Bottlenecks

**Repeated Station Code Dictionary Builds:**
- Problem: Station dictionary loaded from file and built fresh every time user opens device configuration (createStationDict() called during validation)
- Files: `plugin.py:446,1172-1236`
- Cause: No caching of station codes; full file parse on each device config validation
- Improvement path: Cache station dictionary in plugin instance during startup; refresh only on explicit user action or periodic interval

**Sequential Darwin API Calls:**
- Problem: Plugin polls each device sequentially in concurrent thread (line 784-830 in plugin.py); if Darwin API is slow, entire refresh cycle delays
- Files: `plugin.py:804,830`
- Cause: Single-threaded polling loop with no parallelization
- Improvement path: Use ThreadPoolExecutor or asyncio to fetch multiple station boards concurrently; currently limited by Indigo's single-threaded model

**Image Generation on Every Update:**
- Problem: PNG image generated on every refresh cycle (even when data unchanged) if createMaps enabled
- Files: `plugin.py:762-770`, `image_generator.py:52-89`
- Cause: No change detection; subprocess spawned regardless of whether board data changed
- Improvement path: Cache previous board state and only regenerate image if content differs; track modification timestamp

**Station Board Row Limit:**
- Problem: Only 10 services requested from Darwin API (DARWIN_ROW_LIMIT in constants.py:23) but max 5 displayed on images
- Files: `constants.py:13-14,23`
- Cause: Historical limitation; no clear reason why 10 tracked vs 5 displayed
- Improvement path: Clarify requirements and reduce row limit if 10 not needed, or increase display count

## Fragile Areas

**Darwin SOAP Response Parsing:**
- Files: `nredarwin/webservice.py` (entire file), `device_manager.py:156-171`
- Why fragile: Uses dynamic attribute access (getattr) on ZEEP SOAP objects; any schema change from National Rail breaks parsing. Calling points extraction (lines 106-134 in device_manager.py) chains multiple getattr calls with minimal error handling
- Safe modification: Add unit tests for SOAP response parsing with mock Darwin responses; document expected schema; consider schema validation
- Test coverage: Integration tests exist but mock responses may not cover all API variations

**Timezone Handling Fallback:**
- Files: `plugin.py:143,226-229`, `text_formatter.py:15-31`
- Why fragile: Pytz unavailability falls back silently to GMT; no user notification; calling code assumes timezone context always available
- Safe modification: Make timezone handling explicit in configuration; test with and without pytz installed; add startup warning if fallback active
- Test coverage: No test for pytz unavailability scenario

**Color Validation:**
- Files: `plugin.py:575-613`
- Why fragile: Validates colors by checking for '#' character only; allows invalid hex colors (e.g., "#ZZZ", "#12") to pass through
- Safe modification: Use regex pattern to validate hex color format (#[0-9A-Fa-f]{3} or #[0-9A-Fa-f]{6})
- Test coverage: Unit tests needed for color validation

**Calling Points String Formatting:**
- Files: `device_manager.py:97-134`, `image_generator.py:92-153`
- Why fragile: Wraps calling points at word boundaries by finding ')' character; fails if station name format changes or contains special characters
- Safe modification: Use proper text wrapping library (textwrap module); implement tests with various station names
- Test coverage: No unit tests for calling points formatting

## Scaling Limits

**Single Route Per Device:**
- Current capacity: One device = one origin-to-destination route; users must create multiple devices for multiple routes
- Limit: Number of route devices limited by Indigo server performance; polling all devices in single thread
- Scaling path: Implement device grouping or batch polling; use async/concurrent execution for multiple routes

**API Rate Limiting:**
- Current capacity: Unknown (National Rail does not publish rate limits)
- Limit: Plugin makes continuous requests on refresh cycle; could be throttled by Darwin API
- Scaling path: Implement request rate limiting and exponential backoff with jitter; monitor response codes for rate limit indicators

**Image File Accumulation:**
- Current capacity: One PNG per device per refresh; no cleanup of old images
- Limit: User disk space; if refresh interval is 60s, generates 1440 images per device per day
- Scaling path: Implement image rotation/cleanup policy; move to in-memory image buffer if possible, or use delta encoding

**Concurrent Thread Workload:**
- Current capacity: Single concurrent thread handles all polling; CPU-bound due to SOAP parsing and image generation
- Limit: Plugin thread blocks Indigo server thread during timeouts; long refresh cycles cause lag
- Scaling path: Implement thread pool; use non-blocking I/O for Darwin API calls; offload image generation to separate worker process

## Dependencies at Risk

**Zeep 4.x Dependency:**
- Risk: Zeep is SOAP client library; not widely used in modern Python; vendor lock-in to particular SOAP schema implementation
- Impact: If Zeep abandons SOAP support or introduces breaking changes, plugin breaks; no alternative SOAP clients in Python ecosystem are mainstream
- Migration plan: Monitor Zeep releases; keep detailed SOAP schema documentation; consider migrating to REST API if National Rail offers one in future

**Pillow (PIL) Dependency:**
- Risk: Text2png.py uses Pillow for image generation; subprocess invocation means plugin and text2png must use compatible Pillow versions
- Impact: Version conflicts between plugin's Indigo Python environment and text2png's environment could cause image generation failures
- Migration plan: Version lock Pillow in requirements.txt; document compatible versions; consider migrating to lightweight drawing library

**Pydantic Optional Dependency:**
- Risk: Config validation uses Pydantic if available but gracefully degrades to no validation (lines 41-46 in plugin.py, 411-422)
- Impact: Without Pydantic, invalid configurations not caught until runtime; users can set invalid values (e.g., negative refresh intervals)
- Migration plan: Make Pydantic required dependency for cleaner code; alternatively, implement comprehensive validation without Pydantic

**National Rail Darwin API:**
- Risk: External service dependency; API can change schema, add rate limits, or shut down
- Impact: Plugin becomes non-functional if Darwin API changes; no alternative data sources integrated
- Migration plan: Monitor Darwin API documentation; implement comprehensive schema validation; document fallback options

## Missing Critical Features

**No Arrival Board Support:**
- Problem: Plugin only displays departures; cannot show arriving trains
- Blocks: Users cannot track incoming train schedules; feature request likely from users wanting to know when trains arrive
- Priority: Medium - partially designed for in webservice.py but not exposed through plugin UI

**No Historical Data:**
- Problem: Plugin only shows current snapshot; no history of delays, cancellations, or patterns
- Blocks: Users cannot analyze reliability trends; no reporting capabilities
- Priority: Low - out of scope for real-time display plugin

**No Mobile/Remote Access:**
- Problem: Plugin data only accessible through Indigo control pages; no REST API or mobile app integration
- Blocks: Users cannot check train status outside home or on mobile devices
- Priority: High - Indigo-iOS app could consume plugin data via REST endpoint

**No Custom Alerts:**
- Problem: Plugin updates device states but no built-in alert actions (SMS, email, notifications)
- Blocks: Users must create separate Indigo triggers for alerts; cannot configure alert thresholds easily
- Priority: Medium - standard Indigo action pattern could be used

## Test Coverage Gaps

**Darwin API Response Variations:**
- What's not tested: Real Darwin API returns many optional fields and status strings; mock tests use simplified responses
- Files: `tests/mocks/mock_darwin.py:213`, `tests/integration/test_live_darwin_api.py`
- Risk: Code may fail when encountering actual API responses with missing fields or unexpected values
- Priority: High

**Edge Cases in Time Parsing:**
- What's not tested: Darwin returns times as strings like "On time", "Cancelled", "--:--", etc.; parser may fail on variations
- Files: `text_formatter.py` (delayCalc function), `device_manager.py:156-171`
- Risk: Malformed time values could crash time parsing or display garbled times to users
- Priority: High

**Subprocess Failures:**
- What's not tested: Image generation subprocess can fail for many reasons (permissions, disk full, font missing, Pillow version conflict)
- Files: `image_generator.py:79-89`
- Risk: Subprocess errors silently logged to external files; plugin continues as if image generation succeeded
- Priority: High

**Station Code Validation:**
- What's not tested: Invalid CRS codes (non-3-letter codes, fake codes) passed to Darwin API
- Files: `plugin.py:469-473,491-494`
- Risk: Darwin API returns error response that may not be handled gracefully; user gets unclear error message
- Priority: Medium

**Timezone Edge Cases:**
- What's not tested: Daylight saving time transitions, timezones outside UK
- Files: `text_formatter.py:15-31`
- Risk: If pytz unavailable and DST active, times displayed in wrong timezone
- Priority: Medium

**Configuration Validation:**
- What's not tested: Boundary conditions for refresh interval (MIN_UPDATE_FREQ_SECONDS, MAX_UPDATE_FREQ_SECONDS); invalid color codes
- Files: `constants.py:17-19`, `plugin.py:575-613`
- Risk: Users can set invalid configurations that cause runtime errors
- Priority: Medium

**Concurrent Thread Safety:**
- What's not tested: Plugin preferences accessed from concurrent thread while user modifies settings in UI
- Files: `plugin.py:757-758`
- Risk: Race condition could cause plugin to read inconsistent preferences or crash with KeyError
- Priority: Low - Indigo likely handles thread-safe preference access but not explicitly tested

## Implementation Notes

### For Tech Debt Fixes
1. **Priority order:** API key log sanitization (security) → subprocess timeout enforcement (reliability) → station dict caching (performance)
2. **Regression risk:** Medium - changes to error handling and subprocess management require integration testing with real Darwin API

### For Bug Fixes
1. **HTML stripping:** Implement or integrate html2text library; test with actual NRCC messages
2. **Service details failures:** Already handled with graceful degradation; consider user notification if calling points consistently fail

### For Test Coverage
1. **Start with:** Darwin API response variations (use live API to capture real responses)
2. **Then add:** Timezone edge cases, subprocess failures, color validation
3. **Use:** pytest fixtures for mock Darwin responses; conftest.py already has mock infrastructure

---

*Concerns audit: 2026-02-01*
