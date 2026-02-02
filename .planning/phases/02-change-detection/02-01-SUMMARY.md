---
phase: 02-change-detection
plan: 01
subsystem: image-generation
tags: [hashlib, sha256, change-detection, content-hash, subprocess]

# Dependency graph
requires:
  - phase: 01-subprocess-reliability
    provides: Subprocess isolation for image generation with timeout/error handling
provides:
  - Content-based change detection using SHA-256 hashing
  - image_content_hash device state for tracking visual changes
  - Automatic skipping of unnecessary PNG regenerations
affects: [03-configuration-management, future-optimization]

# Tech tracking
tech-stack:
  added: [hashlib (Python stdlib)]
  patterns: [Content hashing for change detection, Hash-then-compare flow, Conditional subprocess execution]

key-files:
  created: []
  modified:
    - UKTrains.indigoPlugin/Contents/Server Plugin/image_generator.py
    - UKTrains.indigoPlugin/Contents/Server Plugin/plugin.py
    - UKTrains.indigoPlugin/Contents/Server Plugin/Devices.xml

key-decisions:
  - "CHG-01: Hash computed from both board text and parameters file (color scheme)"
  - "CHG-02: Hash stored in image_content_hash device state for persistence"
  - "CHG-03: Image regeneration skipped when hash unchanged (performance optimization)"
  - "CHG-04: Hash updated only after successful generation (retry on failure)"
  - "CHG-05: SHA-256 used for collision-resistant hashing (industry standard)"

patterns-established:
  - "Hash-then-compare: Compute current hash, compare with stored hash, skip generation if identical"
  - "Conditional subprocess: Only spawn image generation subprocess when content changed"
  - "Hash storage: Device state as persistent storage for content hashes across plugin restarts"

# Metrics
duration: 4min
completed: 2026-02-02
---

# Phase 2 Plan 1: Change Detection Summary

**SHA-256 content hashing prevents unnecessary PNG regeneration by comparing board text and color parameters before spawning image generation subprocess**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-02T18:27:52Z
- **Completed:** 2026-02-02T18:31:52Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added SHA-256 content hash computation for departure board text and color parameters
- Integrated hash comparison into routeUpdate to skip regeneration when content unchanged
- Added image_content_hash device state for persistent change tracking
- Image generation now executes only when Darwin API data or color scheme changes

## Task Commits

Each task was committed atomically:

1. **Task 1: Add hash computation function and device state** - `2168f43` (feat)
2. **Task 2: Integrate hash comparison into routeUpdate** - `d72a576` (feat)

## Files Created/Modified
- `UKTrains.indigoPlugin/Contents/Server Plugin/image_generator.py` - Added compute_board_content_hash function using SHA-256, reads both board text and parameters file
- `UKTrains.indigoPlugin/Contents/Server Plugin/plugin.py` - Integrated hash comparison before image generation, updates hash only after successful generation
- `UKTrains.indigoPlugin/Contents/Server Plugin/Devices.xml` - Added image_content_hash state for persistent hash storage

## Decisions Made

- **CHG-01**: Hash computed from board text content plus first 5 comma-separated values from parameters file (color scheme) - ensures both data and visual parameter changes trigger regeneration
- **CHG-02**: Hash stored as string in image_content_hash device state - provides persistence across plugin restarts via Indigo's state management
- **CHG-03**: Regeneration skipped when hash unchanged - reduces unnecessary CPU/disk I/O when Darwin API returns identical departure data
- **CHG-04**: Hash updated only after successful generation - failed generations don't update hash, ensuring retry on next poll cycle
- **CHG-05**: SHA-256 algorithm chosen over MD5/SHA-1 - collision-resistant, industry standard, Python stdlib (no dependencies)

## Deviations from Plan

**1. [Rule 3 - Blocking] Used parameters file instead of ColorScheme object**
- **Found during:** Task 1 (Hash function implementation)
- **Issue:** Plan assumed hash function would receive runtime_config.color_scheme ColorScheme object, but routeUpdate already uses paths.get_parameters_file() for subprocess
- **Fix:** Changed function signature to accept parameters_file_path: Path, read and parse file content (first 5 CSV values are colors)
- **Files modified:** image_generator.py, plugin.py
- **Verification:** Function correctly parses 'fg,bg,issue,title,calling_points' from trainparameters.txt
- **Committed in:** 2168f43 (Task 1), d72a576 (Task 2)

---

**Total deviations:** 1 auto-fixed (blocking issue)
**Impact on plan:** Essential adaptation to existing architecture. Parameters file is already used for subprocess communication, more consistent to read it directly than convert ColorScheme object to string.

## Issues Encountered

None - plan executed smoothly with one architectural adaptation (using parameters file directly).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Change detection complete, ready for Phase 3 (Configuration Management)
- Hash comparison reduces unnecessary image generation from 60s polling to only when data changes
- Device state properly tracks content hash for persistence across restarts
- Logging provides visibility into when regeneration is skipped vs executed

---
*Phase: 02-change-detection*
*Completed: 2026-02-02*
