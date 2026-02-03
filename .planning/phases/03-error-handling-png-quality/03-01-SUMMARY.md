---
phase: 03-error-handling-png-quality
plan: 01
subsystem: image-generation
tags: [PIL, Pillow, PNG, subprocess, error-handling, exit-codes]

# Dependency graph
requires:
  - phase: 01-subprocess-reliability
    provides: Subprocess isolation with 10s timeout and capture_output=True
  - phase: 02-change-detection
    provides: Hash-based change detection for image regeneration
provides:
  - Standardized exit codes (0/1/2/3) for subprocess error categorization
  - Font fallback with load_font_safe() preventing crashes on missing fonts
  - PNG optimization with optimize=True for cross-platform compatibility
  - Comprehensive error handling for all PIL and file I/O operations
affects: [parent-process-error-handling, device-state-updates, user-logging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Exit code pattern: 0=success, 1=file I/O, 2=PIL error, 3=other"
    - "Font fallback pattern: try ImageFont.truetype(), except OSError -> ImageFont.load_default()"
    - "PNG save with optimize=True parameter for cross-platform compatibility"

key-files:
  created: []
  modified:
    - "UKTrains.indigoPlugin/Contents/Server Plugin/text2png.py"

key-decisions:
  - "ERR-01: Exit code 0 for successful PNG generation"
  - "ERR-02: Exit code 1 for file I/O errors (read/write failures)"
  - "ERR-03: Exit code 2 for PIL/Pillow errors (font, image creation)"
  - "ERR-04: Exit code 3 for other errors (arguments, configuration)"
  - "ERR-05: All 7 font loading operations use load_font_safe() with OSError handling"
  - "ERR-06: PNG saved with optimize=True for smaller file size and compatibility"
  - "ERR-07: All error messages written to stderr before sys.exit()"

patterns-established:
  - "load_font_safe(path, size, name): TrueType font loading with graceful fallback to default font"
  - "Structured error handling: specific exception types (OSError, ValueError) mapped to exit codes"
  - "Outer try-except catch-all prevents unhandled exceptions, always returns clean exit code"

# Metrics
duration: 2min
completed: 2026-02-02
---

# Phase 03 Plan 01: Error Handling & PNG Quality Summary

**Standardized exit codes (0/1/2/3) with font fallback and PNG optimization for production-ready subprocess image generation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-02T22:26:16Z
- **Completed:** 2026-02-02T22:28:08Z
- **Tasks:** 2 (combined in single cohesive refactor)
- **Files modified:** 1

## Accomplishments
- Eliminated print(sys.exit()) antipattern from line 79 that masked file I/O errors
- Added load_font_safe() helper preventing crashes when fonts missing or unreadable
- Implemented standardized exit codes enabling parent process to identify error types
- Added PNG optimization (optimize=True) for smaller files and cross-platform compatibility
- Wrapped all PIL operations in try-except with specific error categorization

## Task Commits

Tasks 1 and 2 were completed together in a single cohesive refactor:

1. **Tasks 1 & 2: Add standardized exit codes and comprehensive error handling** - `e3e9420` (refactor)

**Rationale for combined commit:** Splitting the refactor would create intermediate states with incomplete error handling. The font fallback, exit codes, and file I/O error handling are tightly coupled and belong in a single atomic change.

## Files Created/Modified
- `UKTrains.indigoPlugin/Contents/Server Plugin/text2png.py` - Complete refactor with standardized error handling, font fallback, and PNG optimization

## Decisions Made

**ERR-01:** Exit code 0 used exclusively for successful PNG generation
- Enables parent process to distinguish success from any failure mode
- Standard Unix convention (0=success)

**ERR-02:** Exit code 1 used for file I/O errors
- Covers parameter file read, text file read, PNG write failures
- Parent process can log "file access problem" vs other error types

**ERR-03:** Exit code 2 used for PIL/Pillow errors
- Covers PIL import failure, font loading (after fallback exhausted), image creation
- Indicates library-level issues distinct from file system problems

**ERR-04:** Exit code 3 used for other errors
- Covers argument validation, parameter parsing, unexpected exceptions
- Catch-all category for configuration and unknown errors

**ERR-05:** All 7 font loading operations use load_font_safe()
- Regular, title, status, depart, delay, calling, messages fonts
- Each attempts TrueType load, falls back to default font on OSError
- Warnings written to stderr but don't block image generation

**ERR-06:** PNG saved with optimize=True parameter
- Pillow performs extra compression pass for smaller file size
- Cross-platform compatibility (Indigo control pages, Pushover, iOS)
- No quality parameter needed (PNG is lossless)

**ERR-07:** All error messages written to stderr before sys.exit()
- Parent process captures stderr for logging to Indigo event log
- Error context preserved for debugging without cluttering stdout

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed print(sys.exit(22)) antipattern**
- **Found during:** Task 1 (reviewing existing error handling)
- **Issue:** Line 79 used `print(sys.exit(22))` which prints None and exits with code 0, masking file I/O errors as success
- **Fix:** Replaced with proper try-except block, stderr message, and sys.exit(1) directly
- **Files modified:** text2png.py lines 100-109
- **Verification:** Grep confirms no print(sys.exit()) patterns remain
- **Committed in:** e3e9420 (part of refactor)

**2. [Rule 2 - Missing Critical] Added parameter file validation**
- **Found during:** Task 1 (parameter reading refactor)
- **Issue:** Parameter file reading had no error handling for IndexError/ValueError when parsing
- **Fix:** Added try-except with exit code 3 for malformed parameter data
- **Files modified:** text2png.py lines 81-95
- **Verification:** Syntax check passes, proper exception handling in place
- **Committed in:** e3e9420 (part of refactor)

**3. [Rule 2 - Missing Critical] Added image creation error handling**
- **Found during:** Task 1 (comprehensive error review)
- **Issue:** Image.new() and ImageDraw.Draw() had no error handling, could fail on invalid colors or PIL limits
- **Fix:** Added try-except around image creation with exit code 2
- **Files modified:** text2png.py lines 166-174
- **Verification:** ValueError and Exception caught separately, both exit with code 2
- **Committed in:** e3e9420 (part of refactor)

**4. [Rule 2 - Missing Critical] Removed debug print statements**
- **Found during:** Task 1 (code review)
- **Issue:** Lines 31, 42-45 printed arguments to stdout, cluttering subprocess output captured by parent
- **Fix:** Removed all debug print statements (trainArguments, imageFileName, trainTextFile, parametersFileName, departuresAvailable)
- **Files modified:** text2png.py
- **Verification:** Grep confirms no debug prints remain
- **Committed in:** e3e9420 (part of refactor)

**5. [Rule 1 - Bug] Fixed text file reading loop bug**
- **Found during:** Task 1 (file I/O refactor)
- **Issue:** Line 85-86 iterated over trainTextFile string instead of routeInfo file handle, causing incorrect timeTable content
- **Fix:** Changed to `for line in routeInfo:` within with statement context
- **Files modified:** text2png.py lines 100-109
- **Verification:** File reading now uses proper with statement and file handle iteration
- **Committed in:** e3e9420 (part of refactor)

---

**Total deviations:** 5 auto-fixed (2 bugs, 3 missing critical)
**Impact on plan:** All auto-fixes necessary for correctness and production stability. No scope creep - every fix addresses error handling or code quality issues within phase scope.

## Issues Encountered

None - refactoring proceeded smoothly. All changes verified with syntax check.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for parent process integration:**
- text2png.py now returns meaningful exit codes parent process can interpret
- All error messages on stderr can be captured and logged to Indigo event log
- Font fallback ensures image generation succeeds even if font files missing
- PNG optimization enabled for smaller files and faster loading

**Next phase prerequisites:**
- Phase 03-02 will need to update parent process (plugin.py) to handle exit codes
- Device state updates for imageGenerationStatus based on exit code
- Logging integration for stderr output to Indigo event log

**Potential concerns:**
- Default font (when TrueType fonts fail) may not look as good as custom fonts
- No validation of color parameters before passing to PIL (could cause PIL errors)
- No size limit checking on generated PNG (Pushover has 5MB limit, but unlikely to hit with text-based boards)

---
*Phase: 03-error-handling-png-quality*
*Completed: 2026-02-02*
