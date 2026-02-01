# Architecture Patterns: PIL/Pillow Image Generation Integration

**Domain:** Python plugin image generation with PIL/Pillow
**Researched:** 2026-02-01
**Confidence:** MEDIUM (based on training data + codebase analysis)

## Executive Summary

PIL/Pillow image generation can be integrated either **in-process** (import directly) or **subprocess** (spawn separate process). The UK-Trains plugin currently uses subprocess isolation to avoid shared library conflicts with Indigo's embedded Python environment. This research evaluates both approaches, error handling patterns, change detection strategies, and provides recommendations for the image generation fix.

**Key findings:**
- Subprocess isolation is appropriate when library conflicts exist (current case)
- In-process integration is faster but requires compatible library environments
- Change detection via content hashing prevents unnecessary regeneration
- Proper subprocess timeout and error handling are critical for reliability

## Recommended Architecture

### Integration Pattern: **Improved Subprocess with Change Detection**

**Rationale:** The existing subprocess approach is correct for avoiding library conflicts, but needs modernization:
1. Add subprocess timeout enforcement
2. Implement change detection to skip regeneration
3. Improve error handling and logging
4. Validate file paths before subprocess spawn

### Component Structure

```
Plugin Main Thread (plugin.py)
    ↓
Device Manager (device_manager.py)
    ↓
Image Generator (image_generator.py)
    ├── Change Detection (hash comparison)
    ├── Text File Writer (intermediate format)
    └── Subprocess Spawner (with timeout)
        ↓
    text2png.py (separate process)
        └── PIL/Pillow (isolated environment)
```

## Subprocess vs In-Process Comparison

### Pattern 1: In-Process Integration

**What:** Import PIL/Pillow directly into plugin code and call image generation functions synchronously.

**Implementation:**
```python
from PIL import Image, ImageDraw, ImageFont

def generate_image(text_data, output_path, params):
    """Generate image directly in plugin process."""
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, size)
    draw.text((x, y), text_data, font=font, fill=fg_color)
    img.save(output_path)
```

**Advantages:**
- Faster (no process spawn overhead)
- Simpler debugging (same process, same logs)
- Direct error handling (try/except in same scope)
- No IPC overhead (no text file intermediary)
- Better for frequent small image generation

**Disadvantages:**
- Library version conflicts (PIL/Pillow vs Indigo's Python environment)
- Shared memory space (crash in PIL crashes entire plugin)
- Harder to isolate dependencies (global imports)
- GIL contention if image generation is CPU-intensive
- May load unnecessary libraries into plugin process

**When to use:**
- Plugin controls Python environment (virtualenv, bundled interpreter)
- No known library conflicts with host environment
- Frequent image generation (performance critical)
- Small images (milliseconds to generate)

**When NOT to use:**
- Host environment has library conflicts (current UK-Trains case)
- Plugin runs in embedded Python (Indigo, Maya, Blender)
- Image generation is CPU-intensive (blocks main thread)
- Stability is critical (crash isolation needed)

### Pattern 2: Subprocess Integration (Current)

**What:** Spawn separate Python process to run PIL/Pillow image generation, communicate via files.

**Current Implementation:**
```python
result = subprocess.run(
    [sys.executable,
     str(plugin_root / 'text2png.py'),
     image_file, text_file, params_file, flag],
    capture_output=True,
    text=True
)
```

**Advantages:**
- Library isolation (PIL/Pillow version independent of plugin)
- Crash isolation (subprocess failure doesn't crash plugin)
- Dependency isolation (PIL loaded only when needed)
- Clean process lifecycle (start, run, exit)
- Can enforce timeouts and resource limits

**Disadvantages:**
- Process spawn overhead (slower startup)
- IPC complexity (communicate via files or pipes)
- Harder debugging (separate process, separate logs)
- More failure modes (spawn failure, timeout, file I/O)
- Not suitable for frequent small generations

**When to use:**
- Library conflicts exist (current case)
- Crash isolation needed (stability critical)
- Infrequent generation (startup overhead acceptable)
- Plugin runs in embedded/controlled environment

**When NOT to use:**
- Performance critical (frequent small images)
- No library conflicts (unnecessary complexity)
- Debugging is difficult (adds process boundary)

### Pattern 3: Hybrid Approach

**What:** Try in-process first, fall back to subprocess if conflicts detected.

**Implementation:**
```python
def generate_image_safe(text_data, output_path, params):
    """Try in-process, fall back to subprocess if conflict detected."""
    if can_use_inprocess():  # Check for library conflicts
        try:
            return generate_image_inprocess(text_data, output_path, params)
        except ImportError as e:
            logger.warning(f"In-process failed: {e}, falling back to subprocess")
            mark_inprocess_unavailable()

    return generate_image_subprocess(text_data, output_path, params)
```

**When to use:**
- Library conflict status unknown at deploy time
- Want performance when possible but reliability guaranteed
- Complex deployment environments (multiple versions)

**Trade-offs:**
- Added complexity (two code paths)
- Harder testing (must test both paths)
- Conflict detection logic needed

## Recommended: Improved Subprocess Pattern

### Architecture

```
┌─────────────────────────────────────────┐
│ Plugin Main Thread                      │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ Device Manager                    │ │
│  │  - Poll Darwin API                │ │
│  │  - Format departure board text    │ │
│  └───────────────┬───────────────────┘ │
│                  │                      │
│  ┌───────────────▼───────────────────┐ │
│  │ Image Generator                   │ │
│  │  1. Hash current board data       │ │
│  │  2. Compare with previous hash    │ │
│  │  3. Skip if unchanged             │ │
│  │  4. Write text file               │ │
│  │  5. Spawn subprocess (timeout)    │ │
│  │  6. Handle errors                 │ │
│  │  7. Update hash cache             │ │
│  └───────────────┬───────────────────┘ │
│                  │                      │
└──────────────────┼──────────────────────┘
                   │ subprocess.run()
                   ▼
┌─────────────────────────────────────────┐
│ text2png.py (Separate Process)          │
│                                         │
│  ┌───────────────────────────────────┐ │
│  │ 1. Import PIL/Pillow              │ │
│  │ 2. Read text file                 │ │
│  │ 3. Read parameters file           │ │
│  │ 4. Generate image                 │ │
│  │ 5. Save PNG                       │ │
│  │ 6. Exit with status code          │ │
│  └───────────────────────────────────┘ │
│                                         │
└─────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| Device Manager | Poll API, format text, trigger image generation | Image Generator |
| Image Generator | Change detection, subprocess lifecycle, error handling | text2png.py (subprocess) |
| text2png.py | Load PIL, render image, save file, exit | None (isolated process) |

### Data Flow

1. **Device Manager** formats departure board text
2. **Image Generator** hashes text content
3. **Change Detection** compares hash with previous
4. **If changed:**
   - Write text file to disk
   - Write parameters file to disk
   - Spawn subprocess with timeout
   - Wait for completion (timeout 10s)
   - Check exit code and stderr
   - Update hash cache
5. **If unchanged:** Skip generation, log skip event
6. **Subprocess** (text2png.py):
   - Import PIL/Pillow
   - Read text file
   - Read parameters file
   - Generate image
   - Save PNG
   - Exit(0) on success, Exit(1) on error

## Change Detection Strategies

### Strategy 1: Content Hashing (Recommended)

**What:** Hash the input data (departure board text + parameters), skip regeneration if hash unchanged.

**Implementation:**
```python
import hashlib

def compute_content_hash(text_data: str, params: dict) -> str:
    """Compute SHA256 hash of text + parameters."""
    content = f"{text_data}|{sorted(params.items())}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def should_regenerate_image(text_data: str, params: dict, device_id: str) -> bool:
    """Check if image needs regeneration."""
    current_hash = compute_content_hash(text_data, params)
    previous_hash = get_cached_hash(device_id)

    if current_hash == previous_hash:
        return False  # Skip regeneration

    update_cached_hash(device_id, current_hash)
    return True  # Regenerate needed
```

**Advantages:**
- Detects actual content changes (not just time-based)
- Works across plugin restarts (persist hash to disk/device state)
- Fast (SHA256 on small text is microseconds)
- Deterministic (same input = same hash)

**Disadvantages:**
- Need to hash parameters too (colors, fonts affect output)
- Persistence needed (store hash somewhere)
- Edge case: hash collision (astronomically unlikely)

**When to use:**
- Input data varies but may repeat (departure boards cycle)
- Want to skip unnecessary work (performance optimization)
- Can persist hash (device state or cache file)

### Strategy 2: Timestamp Comparison

**What:** Compare file modification times (text file vs PNG file), regenerate if text is newer.

**Implementation:**
```python
from pathlib import Path

def should_regenerate_image(text_file: Path, image_file: Path) -> bool:
    """Check if image is older than text file."""
    if not image_file.exists():
        return True  # No image yet

    text_mtime = text_file.stat().st_mtime
    image_mtime = image_file.stat().st_mtime

    return text_mtime > image_mtime  # Text newer than image
```

**Advantages:**
- Simple (no hashing needed)
- Filesystem native (uses mtime)
- No persistence needed (filesystem is the cache)

**Disadvantages:**
- Doesn't detect parameter changes (colors, fonts)
- Fails if text file rewritten with same content (mtime updates)
- Fragile (user touching files breaks detection)
- Doesn't work if text file deleted after generation

**When to use:**
- Simple make-like dependency checking
- Parameters rarely change
- Text file persists after generation

**When NOT to use:**
- Parameters change frequently (colors, fonts)
- Text file is temporary (deleted after use)
- Need precise change detection

### Strategy 3: Hybrid (Content Hash + Timestamp)

**What:** Use timestamp as fast check, fall back to hash if timestamps unclear.

**Implementation:**
```python
def should_regenerate_image(text_data: str, params: dict,
                           text_file: Path, image_file: Path,
                           device_id: str) -> bool:
    """Hybrid change detection."""
    # Fast path: image doesn't exist
    if not image_file.exists():
        return True

    # Fast path: text file newer (make-like)
    if text_file.exists():
        if text_file.stat().st_mtime > image_file.stat().st_mtime:
            return True

    # Slow path: content hash (parameters may have changed)
    current_hash = compute_content_hash(text_data, params)
    previous_hash = get_cached_hash(device_id)

    if current_hash != previous_hash:
        update_cached_hash(device_id, current_hash)
        return True

    return False  # No change detected
```

**When to use:**
- Want best of both (fast timestamp + precise hash)
- Willing to maintain more complex logic

**Trade-offs:**
- More complexity
- Harder to debug (multiple code paths)
- Hash still needed (parameters change)

## Recommendation: Content Hashing

For UK-Trains plugin, use **Strategy 1: Content Hashing** because:
1. Departure boards cycle (same trains repeat daily)
2. Parameters change (user adjusts colors, fonts)
3. Text file is temporary (can be deleted after generation)
4. Device state available for hash persistence
5. Performance matters (avoid unnecessary subprocess spawns)

**Implementation approach:**
- Hash: `SHA256(departure_text + sorted(params))`
- Store: In device state as `image_content_hash`
- Check: Before spawning subprocess
- Update: After successful generation

## Error Handling Patterns

### Pattern 1: Subprocess Lifecycle Management

**Current problem:** No timeout enforcement, unbounded subprocess execution.

**Solution:**
```python
import subprocess
from pathlib import Path

def generate_image_subprocess(
    text_file: Path,
    image_file: Path,
    params_file: Path,
    timeout: int = 10
) -> tuple[bool, str]:
    """Spawn subprocess with timeout and error handling.

    Returns:
        (success: bool, error_message: str)
    """
    try:
        result = subprocess.run(
            [sys.executable,
             str(plugin_root / 'text2png.py'),
             str(image_file),
             str(text_file),
             str(params_file)],
            capture_output=True,
            text=True,
            timeout=timeout  # Kill after N seconds
        )

        if result.returncode != 0:
            return False, f"text2png.py failed: {result.stderr}"

        if not image_file.exists():
            return False, "Image file not created"

        return True, ""

    except subprocess.TimeoutExpired:
        return False, f"Image generation timed out after {timeout}s"

    except FileNotFoundError:
        return False, "text2png.py not found (plugin installation corrupt?)"

    except Exception as e:
        return False, f"Unexpected error: {e}"
```

**Key improvements:**
- Timeout enforcement (default 10s, configurable)
- Capture stdout/stderr (debugging)
- Validate output file exists (detect silent failures)
- Return error messages (propagate to caller)

### Pattern 2: PIL/Pillow Error Handling (text2png.py)

**What:** Handle PIL-specific errors gracefully, exit with proper codes.

**Implementation:**
```python
# In text2png.py
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFile

def main():
    """Main entry point for subprocess."""
    try:
        # Parse command line arguments
        image_file, text_file, params_file = parse_args()

        # Load input data
        text_data = read_text_file(text_file)
        params = read_params_file(params_file)

        # Generate image
        generate_image(text_data, image_file, params)

        # Success
        sys.exit(0)

    except FileNotFoundError as e:
        print(f"ERROR: Input file not found: {e}", file=sys.stderr)
        sys.exit(1)

    except IOError as e:
        print(f"ERROR: Image save failed: {e}", file=sys.stderr)
        sys.exit(2)

    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(3)

def generate_image(text_data, image_file, params):
    """Generate PNG image from text data."""
    try:
        # Enable truncated image loading (handle corrupt images)
        ImageFile.LOAD_TRUNCATED_IMAGES = True

        # Create image
        img = Image.new('RGB', (params['width'], params['height']),
                       color=params['bg_color'])
        draw = ImageDraw.Draw(img)

        # Load font (with fallback)
        try:
            font = ImageFont.truetype(params['font_path'], params['font_size'])
        except IOError:
            print(f"WARNING: Font not found, using default", file=sys.stderr)
            font = ImageFont.load_default()

        # Draw text
        draw.text((params['x'], params['y']), text_data,
                 font=font, fill=params['fg_color'])

        # Save with error handling
        img.save(image_file, format='PNG', optimize=True)

    except Exception as e:
        # PIL-specific errors (corrupt font, invalid color, etc.)
        raise IOError(f"PIL generation failed: {e}") from e
```

**Key patterns:**
- Specific exit codes (0=success, 1=file error, 2=I/O, 3=other)
- Stderr for errors (plugin can capture and log)
- Font fallback (missing font doesn't crash)
- LOAD_TRUNCATED_IMAGES (handle edge cases)
- Re-raise with context (PIL errors are cryptic)

### Pattern 3: Caller Error Handling (image_generator.py)

**What:** Handle subprocess errors at call site, update device state, log appropriately.

**Implementation:**
```python
def update_departure_board_image(self, device, text_data, params):
    """Generate departure board image with error handling."""

    # Change detection (skip if unchanged)
    if not self.should_regenerate_image(device, text_data, params):
        self.logger.debug(f"Skipping image regeneration for {device.name} (unchanged)")
        return

    # Generate image via subprocess
    success, error_msg = self.generate_image_subprocess(
        text_data, device.image_path, params, timeout=10
    )

    if success:
        self.logger.info(f"Generated departure board image: {device.image_path}")
        device.updateStateOnServer('image_generation_status', 'success')
        device.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
    else:
        self.logger.error(f"Image generation failed for {device.name}: {error_msg}")
        device.updateStateOnServer('image_generation_status', 'failed')
        device.updateStateOnServer('image_generation_error', error_msg)
        device.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
        # Don't crash plugin, continue with stale image
```

**Key patterns:**
- Change detection first (avoid unnecessary work)
- Log outcome (success or failure)
- Update device state (expose status to triggers)
- Update device icon (visual feedback)
- Graceful degradation (stale image better than crash)

## Integration with Concurrent Thread

### Current Pattern

```python
# In plugin.py runConcurrentThread()
while True:
    for device in self.devices:
        # Poll Darwin API
        board_data = self.darwin_api.get_departures(device)

        # Format text
        text_data = self.format_departure_board(board_data)

        # Generate image (blocks thread)
        self.generate_image(device, text_data)

    self.sleep(update_interval)
```

**Problem:** Image generation blocks thread, delays other device updates.

### Recommended Pattern

```python
# In plugin.py runConcurrentThread()
while True:
    for device in self.devices:
        # Poll Darwin API
        board_data = self.darwin_api.get_departures(device)

        # Format text
        text_data = self.format_departure_board(board_data)

        # Generate image asynchronously (non-blocking)
        self.image_queue.put((device, text_data, params))

    self.sleep(update_interval)

# Separate image generation thread
def image_generation_thread(self):
    """Process image generation queue."""
    while True:
        try:
            device, text_data, params = self.image_queue.get(timeout=1)

            # Change detection
            if self.should_regenerate(device, text_data, params):
                # Subprocess spawn (blocks this thread, not main)
                self.generate_image_subprocess(device, text_data, params)

        except queue.Empty:
            continue
        except self.StopThread:
            break
```

**Advantages:**
- Main thread not blocked (continues polling other devices)
- Image generation parallelized (multiple devices)
- Queue handles bursts (devices update at different times)

**Disadvantages:**
- More complexity (two threads, queue)
- Harder debugging (async errors)
- Need thread lifecycle management

**When to use:**
- Multiple devices (>5)
- Image generation is slow (>1s)
- Update frequency is high (<30s interval)

**When NOT to use:**
- Single device (no parallelism benefit)
- Image generation is fast (<100ms)
- Simplicity preferred (current simple loop fine)

## Recommended Build Order

Based on current codebase and error patterns, implement in this order:

### Phase 1: Add Subprocess Timeout (Critical)
**Why first:** Prevents unbounded execution, most critical reliability fix.

**Changes:**
1. Add `timeout=10` parameter to `subprocess.run()`
2. Catch `subprocess.TimeoutExpired` exception
3. Log timeout errors with device name
4. Update device state on timeout

**Files:** `image_generator.py`
**Risk:** Low (additive change, backwards compatible)

### Phase 2: Implement Change Detection (High Value)
**Why second:** Prevents unnecessary subprocess spawns, improves performance.

**Changes:**
1. Add `compute_content_hash()` function
2. Store hash in device state `image_content_hash`
3. Add `should_regenerate_image()` check
4. Skip subprocess if hash unchanged
5. Update hash after successful generation

**Files:** `image_generator.py`, device state schema
**Risk:** Low (early return optimization)

### Phase 3: Improve Error Handling (Reliability)
**Why third:** Better diagnostics, graceful degradation.

**Changes:**
1. Capture subprocess stderr
2. Add specific exit codes to `text2png.py`
3. Update device state with error messages
4. Add font fallback in `text2png.py`
5. Validate file paths before subprocess

**Files:** `image_generator.py`, `text2png.py`
**Risk:** Medium (changes subprocess contract)

### Phase 4: Consider Async Queue (Optional)
**Why last:** Only if multiple devices and performance issues observed.

**Changes:**
1. Add `queue.Queue` for image generation
2. Spawn image generation thread
3. Main thread puts to queue, image thread processes
4. Add thread lifecycle management

**Files:** `plugin.py`, `image_generator.py`
**Risk:** High (architectural change, threading complexity)

## Anti-Patterns to Avoid

### Anti-Pattern 1: Shell=True in Subprocess

**What goes wrong:** Passing `shell=True` to `subprocess.run()` enables command injection.

**Why it happens:** Temptation to use shell features (pipes, wildcards).

**Consequences:** Security vulnerability if user-controlled paths in command.

**Prevention:**
```python
# BAD: Shell injection risk
subprocess.run(f"python {script} {user_path}", shell=True)

# GOOD: Direct execution, no shell
subprocess.run([sys.executable, script, user_path], shell=False)
```

### Anti-Pattern 2: Ignoring Exit Codes

**What goes wrong:** Subprocess fails silently, plugin assumes success.

**Why it happens:** Not checking `result.returncode`.

**Consequences:** Stale images, no error feedback.

**Prevention:**
```python
# BAD: Ignore exit code
subprocess.run([...])
# Assumes success

# GOOD: Check exit code
result = subprocess.run([...])
if result.returncode != 0:
    self.logger.error(f"Subprocess failed: {result.stderr}")
```

### Anti-Pattern 3: No Timeout

**What goes wrong:** Subprocess hangs indefinitely (network wait, infinite loop).

**Why it happens:** Missing `timeout` parameter.

**Consequences:** Plugin thread blocked, other devices not updated.

**Prevention:**
```python
# BAD: No timeout
subprocess.run([...])

# GOOD: Enforce timeout
subprocess.run([...], timeout=10)
```

### Anti-Pattern 4: Regenerating Unchanged Images

**What goes wrong:** Subprocess spawned even when data identical.

**Why it happens:** No change detection.

**Consequences:** Wasted CPU, disk I/O, subprocess overhead.

**Prevention:**
```python
# BAD: Always regenerate
generate_image(data)

# GOOD: Check if changed first
if content_hash != previous_hash:
    generate_image(data)
```

### Anti-Pattern 5: In-Process with Library Conflicts

**What goes wrong:** Import PIL/Pillow directly when conflicts exist.

**Why it happens:** Subprocess seems complex, in-process seems simpler.

**Consequences:** Import errors, version conflicts, crashes.

**Prevention:**
```python
# BAD: Import when conflicts exist
from PIL import Image  # Fails with Indigo's Python

# GOOD: Subprocess isolation
subprocess.run([sys.executable, 'text2png.py', ...])
```

## Scalability Considerations

| Concern | 1 device | 5 devices | 20 devices |
|---------|----------|-----------|------------|
| **Subprocess spawn** | Fine (1/minute) | Fine (5/minute) | Consider queue |
| **Change detection** | Nice-to-have | Recommended | Critical |
| **Timeout** | 10s OK | 10s OK | 5s better |
| **Queue/async** | Unnecessary | Optional | Recommended |

## Confidence Assessment

| Topic | Level | Reason |
|-------|-------|--------|
| Subprocess patterns | HIGH | Standard Python stdlib, well-documented |
| PIL/Pillow error modes | MEDIUM | Based on training data + common patterns |
| Change detection | HIGH | Standard hashing algorithms |
| Indigo integration | MEDIUM | Based on codebase analysis + Indigo SDK knowledge |
| Performance impact | MEDIUM | Training data on subprocess overhead |

## Sources

**Based on:**
- Python subprocess module documentation (training data)
- PIL/Pillow documentation and common patterns (training data)
- Codebase analysis: `image_generator.py`, `text2png.py`, `.planning/codebase/*.md`
- Indigo plugin patterns from SDK examples (training data)
- Security best practices for subprocess (training data)

**Not verified with:**
- Current 2026 PIL/Pillow documentation (WebSearch unavailable)
- Recent subprocess security advisories (WebSearch unavailable)
- Indigo 2023+ specific subprocess limitations (official docs not accessed)

**Gaps:**
- Actual Indigo embedded Python library conflicts (need testing)
- PIL/Pillow version compatibility matrix with Indigo (need verification)
- Subprocess spawn overhead benchmarks on macOS (need measurement)
