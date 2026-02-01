# UK-Trains Plugin: Departure Board Image Fix

## What This Is

A fix and modernization effort for the UK-Trains Indigo plugin's departure board PNG generation functionality. The plugin displays real-time UK train departure information from National Rail's Darwin API. PNG departure boards used to generate correctly but broke during a recent color refactoring. This project will fix the generation and modernize the approach to support multiple display contexts: Indigo control pages, Pushover mobile notifications, and a new iOS app.

## Core Value

Reliable, high-quality departure board images that display train information across web, mobile push, and native iOS contexts.

## Requirements

### Validated

These capabilities exist in the current codebase and work correctly:

- ✓ Darwin API integration with authentication and retry logic — existing
- ✓ Route device management tracking up to 10 trains per station — existing
- ✓ Device state updates with scheduled/estimated times, delays, operators — existing
- ✓ Departure board text file generation (.txt format) — existing
- ✓ Concurrent polling at configurable intervals (default 60s) — existing
- ✓ Station-level issue aggregation (delays/cancellations) — existing
- ✓ UK timezone handling with BST support — existing

### Active

Current scope for this fix/modernization effort:

- [ ] PNG departure board generation working again (1 per route device)
- [ ] Image generation only runs when data changes (not every refresh)
- [ ] Modern image generation approach (review subprocess vs in-process)
- [ ] PNG quality suitable for Indigo control page display
- [ ] PNG format compatible with Pushover notifications
- [ ] PNG format suitable for iOS app integration
- [ ] Color scheme properly applied (fixes regression from refactor)

### Out of Scope

Explicitly excluded from this effort:

- Arrivals board support — known limitation, defer to future
- Real-time push notifications to Pushover — separate feature, not part of image fix
- iOS app integration logic — separate iOS project, only ensure image format works
- Adding more than 10 trains per device — current limit is intentional
- Darwin API schema changes — handle existing schema only

## Context

**Recent History:**
- Plugin recently refactored to define color schemes in constants.py
- After refactor, PNG generation stopped working
- Text (.txt) file generation still works correctly
- No errors visible in Indigo logs or NationRailErrors.log

**Current Implementation:**
- Image generation uses text2png.py subprocess to avoid shared library conflicts
- Subprocess spawned with PIL/Pillow to convert text data to PNG
- Images saved to local folder for control page display
- Current approach generates images on every update (even if data unchanged)

**Codebase Quality:**
From .planning/codebase/CONCERNS.md:
- Subprocess integration is fragile (output logged to separate files)
- No timeout enforcement on subprocess
- Image generation lacks change detection
- Only 5 trains displayed despite tracking 10

**Display Contexts:**
1. **Indigo Control Pages** - Primary current use, web display in home automation interface
2. **Pushover Notifications** - Planned use for mobile delay alerts
3. **iOS App** - Planned use in new native iOS app being developed

## Constraints

- **Tech stack**: Python 3.10+, Indigo Plugin SDK, must work within Indigo's embedded Python environment
- **Timeline**: Fix is urgent — currently no visual departure boards working
- **Compatibility**: Must maintain backward compatibility with existing route devices and configuration
- **Dependencies**: PIL/Pillow for image generation, existing Darwin API integration unchanged
- **Image format**: PNG format required for all three display contexts

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep PNG format | Required for Indigo, works with Pushover, compatible with iOS | — Pending |
| Review subprocess approach | Current subprocess fragile, may be modernizable | — Pending |

---
*Last updated: 2026-02-01 after initialization*
