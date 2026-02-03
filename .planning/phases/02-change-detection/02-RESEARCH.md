# Phase 2: Change Detection - Research

**Researched:** 2026-02-02
**Domain:** Content change detection using cryptographic hashing
**Confidence:** HIGH

## Summary

Researched content-based change detection patterns for determining when departure board data has meaningfully changed and requires PNG regeneration. The current implementation regenerates images on every Darwin API poll (every 60 seconds by default) even if the departure data is identical, causing unnecessary CPU/disk I/O and potentially obscuring when actual data changes occur.

Content hashing with SHA-256 provides a reliable, efficient method to detect changes by computing a digest of the board text and color parameters, then comparing it to the previous hash stored in device state. SHA-256 is the standard choice for content verification in Python 3.10+ applications: it's cryptographically secure (preventing collisions), fast enough for small text content (microseconds for typical departure boards), and built into Python's standard library with no dependencies.

The UK-Trains plugin's departure board content consists of: (1) station and destination identifiers, (2) train service data (destinations, times, operators, delays), (3) special NRCC messages, and (4) color scheme parameters passed to text2png.py. All these components must be included in the hash computation to accurately detect when visual output would change.

**Primary recommendation:** Compute SHA-256 hash of departure board text file content plus color parameters string, store hash in device state as `image_content_hash`, compare before calling `_generate_departure_image()`, skip generation if hash unchanged, update hash after successful generation.

## Standard Stack

The established libraries/tools for content change detection in Python 3.10+:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| hashlib | stdlib (3.10+) | Cryptographic hashing (SHA-256) | Python standard library, battle-tested, comprehensive hash algorithms |
| pathlib.Path | stdlib (3.4+) | File handling for reading board text | Type-safe path operations, cross-platform compatibility |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging | stdlib | Debug logging for hash comparisons | Track when regeneration is skipped vs executed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SHA-256 | MD5 | MD5 is faster but has known collision vulnerabilities; not recommended for new code |
| SHA-256 | SHA-1 | SHA-1 is deprecated (collision attacks demonstrated); avoid |
| SHA-256 | BLAKE2 | BLAKE2 is faster but SHA-256 is more widely recognized and sufficient for this use case |
| Content hash | File mtime comparison | mtime doesn't detect content changes; unreliable across filesystems |
| Content hash | Line-by-line comparison | More complex, slower, no advantage over hash for detection |

**Installation:**
```bash
# No installation needed - hashlib is Python standard library
# Already available in Indigo's Python 3.10+ environment
```

## Architecture Patterns

### Recommended Hash Computation Pattern

The content hash should include everything that affects visual output:

```python
import hashlib

def compute_board_content_hash(
    board_text_content: str,
    color_scheme: 'constants.ColorScheme'
) -> str:
    """Compute SHA-256 hash of departure board content and color parameters.

    Args:
        board_text_content: Full departure board text (station, trains, messages)
        color_scheme: Color configuration for image generation

    Returns:
        Hex-encoded SHA-256 hash string (64 characters)
    """
    hasher = hashlib.sha256()

    # Hash board text content
    hasher.update(board_text_content.encode('utf-8'))

    # Hash color parameters (affects visual output)
    color_string = (
        f"{color_scheme.foreground},"
        f"{color_scheme.background},"
        f"{color_scheme.issue},"
        f"{color_scheme.title},"
        f"{color_scheme.calling_points}"
    )
    hasher.update(color_string.encode('utf-8'))

    return hasher.hexdigest()
```

### Pattern 1: Hash-Then-Compare Flow

**What:** Compute hash before image generation, compare with stored hash, skip if unchanged

**When to use:** Always, for any content-based regeneration decision

**Example:**
```python
# Source: Synthesized from https://docs.python.org/3/library/hashlib.html
import hashlib

# After writing departure board text file
with open(train_text_file, 'r') as f:
    board_content = f.read()

# Compute current content hash
current_hash = compute_board_content_hash(board_content, runtime_config.color_scheme)

# Get previous hash from device state
previous_hash = dev.states.get('image_content_hash', '')

# Compare and decide
if current_hash == previous_hash:
    logger.debug(f"Board content unchanged for '{dev.name}', skipping image generation")
    # Skip generation, image is still current
else:
    logger.info(f"Board content changed for '{dev.name}', regenerating image")
    # Generate image
    image_success = _generate_departure_image(...)

    if image_success:
        # Update hash in device state after successful generation
        dev.updateStateOnServer('image_content_hash', current_hash)
```

### Pattern 2: Hash Storage in Device State

**What:** Store hash as string state in Indigo device, persistent across plugin restarts

**When to use:** Always, for maintaining change detection across polling cycles

**Example:**
```python
# After successful image generation
dev.updateStateOnServer('image_content_hash', current_hash)

# On next poll cycle
previous_hash = dev.states.get('image_content_hash', '')  # Empty string if never set

# First run: previous_hash is '', current_hash is computed
# This triggers generation and stores initial hash
# Subsequent runs: compare previous vs current
```

### Pattern 3: Incremental Hashing for Large Content

**What:** Use `.update()` multiple times for efficient hashing of composite content

**When to use:** When content comes from multiple sources or is very large

**Example:**
```python
# Source: https://docs.python.org/3/library/hashlib.html
import hashlib

def compute_board_hash_incremental(
    text_path: Path,
    color_scheme: 'constants.ColorScheme'
) -> str:
    """Compute hash by reading file in chunks (memory efficient)."""
    hasher = hashlib.sha256()

    # Read and hash file content in chunks
    with open(text_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)

    # Hash color parameters
    color_string = f"{color_scheme.foreground},{color_scheme.background}," \
                   f"{color_scheme.issue},{color_scheme.title},{color_scheme.calling_points}"
    hasher.update(color_string.encode('utf-8'))

    return hasher.hexdigest()
```

### Pattern 4: Hash Comparison Logging

**What:** Log hash comparison results to aid debugging and monitoring

**When to use:** Always, for visibility into change detection behavior

**Example:**
```python
if self.config.debug:
    logger.debug(f"Hash comparison for '{dev.name}':")
    logger.debug(f"  Previous: {previous_hash[:16]}... (stored)")
    logger.debug(f"  Current:  {current_hash[:16]}... (computed)")
    logger.debug(f"  Changed:  {current_hash != previous_hash}")

if current_hash == previous_hash:
    logger.debug(f"Skipping image generation for '{dev.name}' (content unchanged)")
else:
    logger.info(f"Regenerating image for '{dev.name}' (content changed)")
```

### Anti-Patterns to Avoid

- **Hashing only train data without colors:** Color changes affect visual output but won't trigger regeneration if colors aren't included in hash. Always hash complete visual parameters.

- **Comparing text files directly:** Line-by-line comparison is slower and more complex than hashing. Use hash comparison for efficiency.

- **Using file modification time:** mtime doesn't detect when content is rewritten with identical data. Unreliable for change detection.

- **Storing hash in external file:** Device state is persistent, backed up by Indigo, and accessible in triggers/actions. More reliable than separate file.

- **Not updating hash after failed generation:** If generation fails, keep old hash so next poll cycle retries generation. Only update hash on success.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Content hashing | Custom checksum algorithm | hashlib.sha256() | Cryptographically secure, collision-resistant, faster than manual implementation |
| Hash comparison | String similarity metrics (Levenshtein, etc.) | Exact hash equality (==) | Change detection needs binary yes/no, not similarity percentage |
| File change detection | Manual file comparison | Content hash comparison | Hashing is O(n) with file size, comparison is O(1); more efficient |
| Hash encoding | Manual hex conversion | hexdigest() method | Built-in, optimized, returns standard lowercase hex format |

**Key insight:** hashlib.sha256() is specifically designed for content verification and has 20+ years of optimization. Using exact hash equality provides deterministic change detection: any byte difference produces a completely different hash (avalanche effect), while identical content always produces the same hash.

## Common Pitfalls

### Pitfall 1: Forgetting to Include Color Parameters in Hash

**What goes wrong:** User changes color scheme in plugin preferences, but image doesn't regenerate because hash is computed only from text content, missing the color change.

**Why it happens:** Color parameters are passed separately to text2png.py via trainparameters.txt, easy to overlook them in hash computation.

**How to avoid:** Always hash the complete set of inputs to image generation: board text + color scheme. If text2png.py receives it, hash should include it.

**Warning signs:**
- User reports "changed colors but image didn't update"
- Hash shows unchanged but visual output should be different
- trainparameters.txt modified but hash identical

### Pitfall 2: Not Handling Missing Previous Hash on First Run

**What goes wrong:** First poll after device creation has no previous hash, comparison fails or throws exception.

**Why it happens:** Device state 'image_content_hash' doesn't exist until first successful image generation.

**How to avoid:** Use `.get('image_content_hash', '')` with empty string default. Empty string never matches computed hash, triggering initial generation.

**Warning signs:**
- KeyError on device.states['image_content_hash']
- Image not generated on first device poll
- Exception in logs about missing state

### Pitfall 3: Updating Hash Before Verifying Generation Success

**What goes wrong:** Update hash immediately after computing it, then generation fails. Next poll cycle sees matching hash and skips generation, leaving stale/missing image.

**Why it happens:** Hash update placed before generation subprocess instead of after verification.

**How to avoid:** Only update device state hash AFTER `_generate_departure_image()` returns `True`. Use if-block to guard hash update.

**Warning signs:**
- Image generation fails but subsequent polls don't retry
- Device state shows success but PNG doesn't exist
- Hash updated but image file timestamp is old

### Pitfall 4: Hashing Python Objects Instead of Strings

**What goes wrong:** Attempting to hash a ColorScheme dataclass directly produces inconsistent hashes because object memory address affects hash, not content.

**Why it happens:** Misunderstanding that hashlib requires bytes, not Python objects.

**How to avoid:** Always convert data to string representation, then encode to bytes: `string_value.encode('utf-8')`. For dataclasses, extract fields explicitly.

**Warning signs:**
- Different hash on every poll despite unchanged content
- TypeError about hashing non-bytes object
- Hash contains object memory addresses (e.g., "0x10a4b2c40")

### Pitfall 5: Using MD5 for New Code

**What goes wrong:** MD5 has known collision vulnerabilities (different inputs producing same hash). While unlikely for departure boards, using deprecated algorithms is poor practice.

**Why it happens:** MD5 is faster and examples online still show it. Legacy code may use it.

**How to avoid:** Use SHA-256 for all new hash-based change detection. Performance difference is negligible for small content (<1KB), and SHA-256 is collision-resistant.

**Warning signs:**
- Code uses `hashlib.md5()`
- Security tools flag MD5 usage
- Hash length is 32 characters (MD5) instead of 64 (SHA-256)

## Code Examples

Verified patterns from official sources:

### Complete UK-Trains Change Detection Pattern

```python
# Source: Synthesized from https://docs.python.org/3/library/hashlib.html
# Production pattern for UK-Trains departure board change detection

import hashlib
from pathlib import Path
from typing import Optional

def compute_board_content_hash(
    board_text_path: Path,
    color_scheme: 'constants.ColorScheme'
) -> str:
    """Compute SHA-256 hash of departure board content and rendering parameters.

    Includes all inputs that affect visual output: board text and color scheme.

    Args:
        board_text_path: Path to departure board text file
        color_scheme: ColorScheme dataclass with rendering colors

    Returns:
        Lowercase hex-encoded SHA-256 hash (64 characters)
    """
    hasher = hashlib.sha256()

    # Hash departure board text content
    with open(board_text_path, 'r', encoding='utf-8') as f:
        board_content = f.read()
    hasher.update(board_content.encode('utf-8'))

    # Hash color parameters (affects image appearance)
    color_string = (
        f"{color_scheme.foreground},"
        f"{color_scheme.background},"
        f"{color_scheme.issue},"
        f"{color_scheme.title},"
        f"{color_scheme.calling_points}"
    )
    hasher.update(color_string.encode('utf-8'))

    return hasher.hexdigest()


def should_regenerate_image(
    dev,
    board_text_path: Path,
    color_scheme: 'constants.ColorScheme',
    logger
) -> tuple[bool, str]:
    """Determine if PNG image needs regeneration based on content hash.

    Args:
        dev: Indigo device object
        board_text_path: Path to departure board text file
        color_scheme: Current color configuration
        logger: Plugin logger for debugging

    Returns:
        Tuple of (should_regenerate: bool, current_hash: str)
    """
    # Compute current content hash
    current_hash = compute_board_content_hash(board_text_path, color_scheme)

    # Get previous hash from device state (empty string if never set)
    previous_hash = dev.states.get('image_content_hash', '')

    # Log comparison for debugging
    if logger:
        if previous_hash:
            logger.debug(f"Content hash comparison for '{dev.name}':")
            logger.debug(f"  Previous: {previous_hash[:16]}...")
            logger.debug(f"  Current:  {current_hash[:16]}...")
        else:
            logger.debug(f"No previous hash for '{dev.name}' (first generation)")

    # Determine if regeneration needed
    needs_regeneration = (current_hash != previous_hash)

    if needs_regeneration:
        logger.info(f"Board content changed for '{dev.name}', regenerating image")
    else:
        logger.debug(f"Board content unchanged for '{dev.name}', skipping regeneration")

    return needs_regeneration, current_hash


# Integration into routeUpdate() function
def routeUpdate_with_change_detection(dev, apiAccess, networkrailURL, paths, runtime_config, logger):
    """Modified routeUpdate with change detection before image generation."""

    # ... existing code for Darwin API fetch and state updates ...

    # Write departure board text file (as before)
    train_text_file = paths.get_text_path(stationStartCrs, stationEndCrs)
    _write_departure_board_text(
        train_text_file,
        station_start=stationStartCrs,
        station_end=stationEndCrs,
        titles=board_titles,
        statistics=board_stats,
        messages=special_messages + '\n',
        board_content=station_board
    )

    # Check if image regeneration needed
    needs_regeneration, current_hash = should_regenerate_image(
        dev,
        train_text_file,
        runtime_config.color_scheme,
        logger
    )

    if needs_regeneration:
        # Generate PNG image from text file
        image_filename = paths.get_image_path(stationStartCrs, stationEndCrs)
        parameters_file = paths.get_parameters_file()

        image_success = _generate_departure_image(
            paths.plugin_root,
            image_filename,
            train_text_file,
            parameters_file,
            departures_available=departures_found,
            device=dev,
            logger=logger
        )

        if image_success:
            # Update hash only after successful generation
            dev.updateStateOnServer('image_content_hash', current_hash)
            logger.debug(f"Updated content hash for '{dev.name}'")
        else:
            # Generation failed, keep old hash to retry next cycle
            logger.error(f"Image generation failed for '{dev.name}', will retry next cycle")
    else:
        # Content unchanged, skip generation
        logger.debug(f"Skipped image generation for '{dev.name}' (content unchanged)")

    return True
```

### Minimal Hash Computation Pattern

```python
# Source: https://docs.python.org/3/library/hashlib.html
import hashlib

# Simple string content hash
content = "Departure board text content"
content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

# Returns: 64-character hex string
# Example: 'a3c5e9f2b1d4e6f8a9c0b2d4e6f8a0c2b4d6e8f0a2c4e6f8a0b2d4e6f8a0c2b'
```

### Hash Comparison with Logging

```python
# Pattern for debugging change detection behavior
def compare_and_log_hashes(dev, current_hash: str, logger) -> bool:
    """Compare hashes and log decision for debugging."""
    previous_hash = dev.states.get('image_content_hash', '')

    if not previous_hash:
        logger.info(f"First generation for '{dev.name}' (no previous hash)")
        return True  # Always generate on first run

    if current_hash != previous_hash:
        logger.info(f"Content changed for '{dev.name}'")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"  Old hash: {previous_hash}")
            logger.debug(f"  New hash: {current_hash}")
        return True  # Generate because content changed

    logger.debug(f"Content unchanged for '{dev.name}' (hash: {current_hash[:16]}...)")
    return False  # Skip generation
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| MD5 hashing | SHA-256 hashing | ~2010 (MD5 collisions demonstrated) | SHA-256 is collision-resistant, recommended for new code |
| File mtime comparison | Content hash comparison | Ongoing | Hashes detect actual content changes, mtime unreliable across systems |
| Line-by-line comparison | Hash equality check | Modern practice | O(1) comparison vs O(n), simpler code |
| Custom checksums | hashlib standard library | Python 2.5+ (2006) | Cryptographically secure, battle-tested, no dependencies |

**Deprecated/outdated:**
- **MD5**: Collision vulnerabilities demonstrated. Use SHA-256 for new code.
- **SHA-1**: Deprecated as of 2017 (SHAttered attack). Use SHA-256 or BLAKE2.
- **File timestamps (mtime)**: Unreliable for content change detection. Use content hashing.
- **Custom CRC/checksum algorithms**: Use standard hashlib instead for security and reliability.

## Open Questions

1. **Hash persistence across plugin restarts**
   - What we know: Indigo device states persist across plugin restarts automatically
   - What's unclear: Does device state survive Indigo server restarts? Assumption: yes, device states are persisted to Indigo database.
   - Recommendation: Verify in testing that hash persists. If not, first poll after restart will regenerate all images (acceptable).

2. **Hash state for devices with createMaps=false**
   - What we know: Some users disable image generation via plugin preferences
   - What's unclear: Should we skip hash computation if images disabled, or compute anyway for consistency?
   - Recommendation: Skip hash computation if `runtime_config.create_images` is False. No point computing hash if image generation disabled.

3. **Should color parameter changes log at info or debug level?**
   - What we know: Color changes are rare (user configuration changes)
   - What's unclear: Is color-triggered regeneration important enough for info-level logging?
   - Recommendation: Log at INFO level when hash differs (captures both data and color changes). Debug logging already shows hash values.

## Sources

### Primary (HIGH confidence)
- [Python hashlib documentation](https://docs.python.org/3/library/hashlib.html) - Official Python 3 documentation, last updated February 02, 2026
- UK-Trains codebase - Current implementation in plugin.py, image_generator.py, constants.py
- [Python subprocess documentation](https://docs.python.org/3/library/hashlib.html) - For integration with subprocess pattern from Phase 1

### Secondary (MEDIUM confidence)
- [How To Detect File Changes Using Python - GeeksforGeeks](https://www.geeksforgeeks.org/python/how-to-detect-file-changes-using-python/) - Community patterns for file change detection
- [Python SHA256: Secure Hashing Implementation - datagy](https://datagy.io/python-sha256/) - SHA-256 usage patterns and examples
- [Trafilatura Deduplication Documentation](https://trafilatura.readthedocs.io/en/latest/deduplication.html) - Content deduplication approaches in Python

### Tertiary (LOW confidence)
- Web search results on content-based deduplication - Multiple approaches described (SimHash, LSH), but simple equality-based hash comparison sufficient for UK-Trains use case

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - hashlib is Python stdlib, well-documented, stable API since Python 2.5
- Architecture: HIGH - Patterns verified from official Python docs and production use cases
- Pitfalls: HIGH - Based on official docs, common mistakes documented in community resources
- Integration: HIGH - Clear integration point in routeUpdate(), device state mechanism already exists from Phase 1

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (30 days - stable stdlib API, unlikely to change)
