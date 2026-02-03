---
phase: 03-error-handling-png-quality
plan: 02
subsystem: image-generation
tags: [exit-codes, device-states, error-handling, user-visibility]

# Dependency graph
requires:
  - phase: 03-error-handling-png-quality
    plan: 01
    provides: Standardized exit codes (0/1/2/3) from text2png.py subprocess
  - phase: 01-subprocess-reliability
    provides: Subprocess isolation with timeout and capture_output
  - phase: 02-change-detection
    provides: Device state infrastructure (imageGenerationStatus)
provides:
  - Parent process exit code handling with specific error categorization
  - Device state imageGenerationError for user-visible error messages
  - Indigo trigger support for error conditions
  - Control page display of specific error types
affects: [user-logging, indigo-triggers, control-pages, debugging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Exit code dispatch pattern: if returncode == 0/1/2/3 with specific error messages"
    - "Dual state update pattern: imageGenerationStatus + imageGenerationError on all paths"
    - "Clear-on-success pattern: Empty string for imageGenerationError on success"

key-files:
  created: []
  modified:
    - "UKTrains.indigoPlugin/Contents/Server Plugin/Devices.xml"
    - "UKTrains.indigoPlugin/Contents/Server Plugin/image_generator.py"

key-decisions:
  - "ERR-08: imageGenerationError state uses String type for human-readable messages"
  - "ERR-09: Error messages are concise and user-friendly (no technical jargon)"
  - "ERR-10: Success path clears imageGenerationError to empty string (not null)"
  - "ERR-11: Unknown exit codes handled with generic message including returncode"
  - "ERR-12: All error paths update both status and error states for consistency"

patterns-established:
  - "Error state lifecycle: Set on error, cleared on success, never null"
  - "Dual logging: Error message to Indigo log + device state for user visibility"
  - "Exit code dispatch with fallthrough: Specific codes first, unknown code last"

# Metrics
duration: 2min
completed: 2026-02-02
---

# Phase 03 Plan 02: Exit Code Handling & Device Error State Summary

**Parent process interprets text2png.py exit codes and exposes specific error messages via Indigo device states**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-02T22:30:40Z
- **Completed:** 2026-02-02T22:32:57Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added imageGenerationError device state for user-visible error messages
- Implemented exit code handling (0/1/2/3) in parent process _generate_departure_image()
- Changed subprocess.run() from check=True to check=False for manual exit code interpretation
- All error paths now update both imageGenerationStatus and imageGenerationError states
- Success path clears imageGenerationError to empty string
- Timeout and FileNotFoundError exceptions also update error state
- Users can now see specific error types in Indigo control pages and trigger on them

## Task Commits

1. **Task 1: Add imageGenerationError device state** - `55b1740` (feat)
2. **Task 2: Implement exit code handling in parent process** - `0ab25d6` (feat)

## Files Created/Modified

- `UKTrains.indigoPlugin/Contents/Server Plugin/Devices.xml` - Added imageGenerationError state with TriggerLabel and ControlPageLabel
- `UKTrains.indigoPlugin/Contents/Server Plugin/image_generator.py` - Refactored _generate_departure_image() with exit code dispatch

## Decisions Made

**ERR-08:** imageGenerationError uses String ValueType for human-readable messages
- Alternative considered: Integer error codes (harder for users to interpret)
- Rationale: Users see "File I/O error: cannot read input files" instead of error code 1
- Enables natural language in control pages and logs

**ERR-09:** Error messages are concise and user-friendly
- Examples: "PIL error: font loading or image creation failed" (not "PIL/Pillow exception in text2png.py line 145")
- Users understand the problem category without technical details
- Full technical details still logged to Indigo event log via stderr capture

**ERR-10:** Success path clears imageGenerationError to empty string
- Alternative considered: Leave previous error message (confusing when status changes to success)
- Empty string indicates "no error currently" vs null/undefined
- Consistent with Indigo device state conventions

**ERR-11:** Unknown exit codes handled with generic message including returncode
- Enables future-proofing if text2png.py adds new exit codes
- Message format: "Unknown error (exit code {N})"
- User can report specific code to developer for troubleshooting

**ERR-12:** All error paths update both imageGenerationStatus and imageGenerationError
- Status state provides machine-readable category (success/failed/timeout/error)
- Error state provides human-readable explanation
- Dual updates ensure consistency - never have status="success" with error message

## Deviations from Plan

None - plan executed exactly as written. All tasks completed as specified with no bugs encountered or missing critical functionality discovered.

## Issues Encountered

None - implementation proceeded smoothly. Both tasks passed verification on first attempt.

## User Setup Required

None - changes are transparent to existing deployments. Device states are backward compatible (new state ignored by older plugin versions).

## Next Phase Readiness

**Phase 3 complete:**
- ✅ text2png.py returns standardized exit codes (03-01)
- ✅ Parent process interprets exit codes and updates device states (03-02)
- ✅ Users see specific error messages in control pages
- ✅ Indigo triggers can fire on imageGenerationError state changes
- ✅ PNG optimization enabled with optimize=True

**Production-ready image generation:**
- Comprehensive error handling from subprocess through device states
- Font fallback prevents crashes when fonts missing
- Change detection prevents unnecessary regeneration
- Timeout protection prevents hung processes
- User-visible error messages enable self-service troubleshooting

**Potential future enhancements (out of scope):**
- Add imageGenerationError to control page templates (requires custom control page design)
- Email alerts on persistent image generation failures (requires Indigo action/trigger setup)
- Retry logic with exponential backoff (currently fails fast, retry on next poll cycle)

---
*Phase: 03-error-handling-png-quality*
*Completed: 2026-02-02*
