# Roadmap: UK-Trains Departure Board Image Fix

## Overview

Fix and modernize the UK-Trains plugin's broken departure board PNG generation through three focused phases: restore subprocess reliability with timeout enforcement, add intelligent change detection to skip unnecessary regenerations, and implement comprehensive error handling with proper color scheme application. Each phase builds on the previous to deliver progressively better image generation quality and reliability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Subprocess Reliability** - Prevent unbounded hangs with timeout enforcement
- [x] **Phase 2: Change Detection** - Skip unnecessary regenerations with content hashing
- [ ] **Phase 3: Error Handling & PNG Quality** - Comprehensive error handling and image quality fixes

## Phase Details

### Phase 1: Subprocess Reliability
**Goal**: Subprocess image generation executes safely with timeout enforcement and error reporting
**Depends on**: Nothing (first phase)
**Requirements**: SUB-01, SUB-02, SUB-03, SUB-04, SUB-05, BUG-01
**Success Criteria** (what must be TRUE):
  1. Subprocess execution never hangs indefinitely (10-second timeout enforced)
  2. Device state updates when subprocess times out or fails
  3. Subprocess stderr appears in plugin logs for debugging
  4. Color definitions from constants.py correctly passed to text2png.py
**Plans**: 1 plan

Plans:
- [x] 01-01-PLAN.md - Add timeout, error handling, and stderr capture to subprocess execution

### Phase 2: Change Detection
**Goal**: Image regeneration only occurs when departure board data actually changes
**Depends on**: Phase 1
**Requirements**: CHG-01, CHG-02, CHG-03, CHG-04, CHG-05, BUG-02
**Success Criteria** (what must be TRUE):
  1. Content hash computed from board text and color parameters before generation
  2. PNG regeneration skipped when hash matches previous generation
  3. Hash stored in device state and updated after successful generation
  4. PNG generation executes when Darwin API data updates
**Plans**: 1 plan

Plans:
- [x] 02-01-PLAN.md - Add SHA-256 content hashing to detect board data changes

### Phase 3: Error Handling & PNG Quality
**Goal**: Comprehensive error handling with proper exit codes and high-quality PNG output across all display contexts
**Depends on**: Phase 2
**Requirements**: ERR-01, ERR-02, ERR-03, ERR-04, ERR-05, ERR-06, ERR-07, PNG-01, PNG-02, PNG-03, PNG-04, PNG-05, BUG-03
**Success Criteria** (what must be TRUE):
  1. text2png.py returns specific exit codes for different failure types (0=success, 1=file I/O, 2=PIL error, 3=other)
  2. Device state displays meaningful error messages when image generation fails
  3. Font fallback works when specified font file is missing
  4. PNG images display correctly in Indigo control pages
  5. PNG format compatible with Pushover notification delivery
  6. PNG images suitable for iOS UIImage display
  7. Color scheme properly applied to all generated images
  8. One PNG file generated per route device (not shared)
**Plans**: TBD

Plans:
- [ ] 03-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Subprocess Reliability | 1/1 | Complete | 2026-02-02 |
| 2. Change Detection | 1/1 | Complete | 2026-02-02 |
| 3. Error Handling & PNG Quality | 0/TBD | Not started | - |
