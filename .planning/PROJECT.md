# UK-Trains Plugin: Departure Board Image Fix

## What This Is

A fix and modernization effort for the UK-Trains Indigo plugin's departure board PNG generation functionality. The plugin displays real-time UK train departure information from National Rail's Darwin API. PNG departure boards used to generate correctly but broke during a recent color refactoring. This project will fix the generation and modernize the approach to support multiple display contexts: Indigo control pages, Pushover mobile notifications, and a new iOS app.

## Core Value

Reliable, high-quality departure board images that display train information across web, mobile push, and native iOS contexts.

## Requirements

### Validated

Capabilities delivered and verified in production:

- ✓ Darwin API integration with authentication and retry logic — existing
- ✓ Route device management tracking up to 10 trains per station — existing
- ✓ Device state updates with scheduled/estimated times, delays, operators — existing
- ✓ Departure board text file generation (.txt format) — existing
- ✓ Concurrent polling at configurable intervals (default 60s) — existing
- ✓ Station-level issue aggregation (delays/cancellations) — existing
- ✓ UK timezone handling with BST support — existing
- ✓ PNG departure board generation working (1 per route device) — 2025.1.4
- ✓ Image generation only runs when data changes (SHA-256 hashing) — 2025.1.4
- ✓ Subprocess image generation with timeout enforcement — 2025.1.4
- ✓ PNG quality suitable for Indigo control page display — 2025.1.4
- ✓ PNG format compatible with Pushover notifications — 2025.1.4
- ✓ PNG format suitable for iOS app integration — 2025.1.4
- ✓ Color scheme properly applied (fixed regression) — 2025.1.4

### Active

No active requirements - 2025.1.4 milestone complete. See `.planning/milestones/2025.1.4-REQUIREMENTS.md` for full v1 details.

### Out of Scope

Explicitly excluded from this effort:

- Arrivals board support — known limitation, defer to future
- Real-time push notifications to Pushover — separate feature, not part of image fix
- iOS app integration logic — separate iOS project, only ensure image format works
- Adding more than 10 trains per device — current limit is intentional
- Darwin API schema changes — handle existing schema only

## Current State

**Version:** 2025.1.4 shipped 2026-02-02

**Codebase:** Production-ready PNG departure board generation
- 3 phases, 4 plans, 26 requirements satisfied
- Comprehensive error handling with timeout enforcement
- Change detection with SHA-256 hashing
- Cross-platform PNG compatibility verified

**Known Issues:** None blocking

**Display Contexts:**
1. **Indigo Control Pages** - Production, web display in home automation interface
2. **Pushover Notifications** - Ready, PNG format compatible (<100KB)
3. **iOS App** - Ready, PNG format suitable for UIImage display

## Constraints

- **Tech stack**: Python 3.10+, Indigo Plugin SDK, must work within Indigo's embedded Python environment
- **Timeline**: Fix is urgent — currently no visual departure boards working
- **Compatibility**: Must maintain backward compatibility with existing route devices and configuration
- **Dependencies**: PIL/Pillow for image generation, existing Darwin API integration unchanged
- **Image format**: PNG format required for all three display contexts

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep PNG format | Required for Indigo, works with Pushover, compatible with iOS | ✓ Good - 2025.1.4 verified |
| Keep subprocess approach | Isolation prevents PIL library conflicts, timeout enforcement added | ✓ Good - 2025.1.4 modernized |
| 10-second timeout | Generous buffer for I/O-bound operations, prevents hangs | ✓ Good - 2025.1.4 |
| SHA-256 content hashing | Change detection skips unnecessary regeneration | ✓ Good - 2025.1.4 performance |
| Standardized exit codes | Parent process categorizes errors (0/1/2/3) | ✓ Good - 2025.1.4 debugging |
| Font fallback pattern | Graceful degradation when TrueType fonts unavailable | ✓ Good - 2025.1.4 reliability |

---
*Last updated: 2026-02-02 after 2025.1.4 milestone completion*
