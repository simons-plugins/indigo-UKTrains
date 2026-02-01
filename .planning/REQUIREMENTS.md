# Requirements: UK-Trains Departure Board Image Fix

**Defined:** 2026-02-01
**Core Value:** Reliable, high-quality departure board images across web, mobile push, and native iOS contexts

## v1 Requirements

Requirements for this fix/modernization release. Each maps to roadmap phases.

### Subprocess Reliability

- [ ] **SUB-01**: Subprocess execution has 10-second timeout to prevent unbounded hangs
- [ ] **SUB-02**: TimeoutExpired exceptions are caught and logged with device name
- [ ] **SUB-03**: Device state updates when subprocess times out
- [ ] **SUB-04**: Subprocess stderr is captured and written to plugin logs
- [ ] **SUB-05**: Subprocess uses `subprocess.run()` (not deprecated `call()`)

### Change Detection

- [ ] **CHG-01**: Content hash computed from board text data and color parameters
- [ ] **CHG-02**: Hash stored in device state as `image_content_hash`
- [ ] **CHG-03**: PNG regeneration skipped if hash unchanged from previous update
- [ ] **CHG-04**: Hash updated after successful PNG generation
- [ ] **CHG-05**: Hash computation uses SHA256 algorithm

### Error Handling

- [ ] **ERR-01**: text2png.py returns exit code 0 for success
- [ ] **ERR-02**: text2png.py returns exit code 1 for file I/O errors
- [ ] **ERR-03**: text2png.py returns exit code 2 for PIL/Pillow errors
- [ ] **ERR-04**: text2png.py returns exit code 3 for other errors
- [ ] **ERR-05**: Parent process checks exit codes and logs specific error type
- [ ] **ERR-06**: Device state updated with error message when generation fails
- [ ] **ERR-07**: Font fallback implemented when specified font missing

### PNG Quality

- [ ] **PNG-01**: PNG images display correctly in Indigo control pages
- [ ] **PNG-02**: PNG format compatible with Pushover notification delivery
- [ ] **PNG-03**: PNG images suitable for iOS UIImage display
- [ ] **PNG-04**: Color scheme from recent refactor properly applied to images
- [ ] **PNG-05**: Images saved to correct local folder path

### Bug Fixes

- [ ] **BUG-01**: Color definitions from constants.py correctly passed to text2png.py
- [ ] **BUG-02**: PNG generation executes when Darwin API data updates
- [ ] **BUG-03**: One PNG file generated per route device (not shared across devices)

## v2 Requirements

Deferred to future releases. Tracked but not in current scope.

### Performance Optimization

- **PERF-01**: Async queue pattern for image generation (only if >20 devices)
- **PERF-02**: Parallel image generation for multiple devices
- **PERF-03**: In-process PIL/Pillow (if library conflicts resolved)

### Enhanced Monitoring

- **MON-01**: Telemetry for image generation errors frequency
- **MON-02**: Metrics for change detection hit rate
- **MON-03**: Performance monitoring for subprocess spawn overhead

## Out of Scope

Explicitly excluded from this effort. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Arrivals board support | Known limitation, separate feature request |
| Real-time Pushover notifications | Separate integration, only ensure PNG format compatible |
| iOS app integration code | Separate iOS project, only ensure PNG format works |
| Increasing 10-train device limit | Current limit is intentional, no user request to change |
| Changing image format (SVG, WebP) | PNG works for all three contexts, no need |
| In-process PIL migration | Research shows subprocess isolation is correct pattern |
| Async queue implementation | Only needed at scale (>20 devices), defer until necessary |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SUB-01 | TBD | Pending |
| SUB-02 | TBD | Pending |
| SUB-03 | TBD | Pending |
| SUB-04 | TBD | Pending |
| SUB-05 | TBD | Pending |
| CHG-01 | TBD | Pending |
| CHG-02 | TBD | Pending |
| CHG-03 | TBD | Pending |
| CHG-04 | TBD | Pending |
| CHG-05 | TBD | Pending |
| ERR-01 | TBD | Pending |
| ERR-02 | TBD | Pending |
| ERR-03 | TBD | Pending |
| ERR-04 | TBD | Pending |
| ERR-05 | TBD | Pending |
| ERR-06 | TBD | Pending |
| ERR-07 | TBD | Pending |
| PNG-01 | TBD | Pending |
| PNG-02 | TBD | Pending |
| PNG-03 | TBD | Pending |
| PNG-04 | TBD | Pending |
| PNG-05 | TBD | Pending |
| BUG-01 | TBD | Pending |
| BUG-02 | TBD | Pending |
| BUG-03 | TBD | Pending |

**Coverage:**
- v1 requirements: 26 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 26 ⚠️

---
*Requirements defined: 2026-02-01*
*Last updated: 2026-02-01 after initial definition*
