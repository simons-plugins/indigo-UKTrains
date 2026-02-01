# Technology Stack - Image Generation

**Project:** UK-Trains Indigo Plugin - Departure Board Image Fix
**Researched:** 2026-02-01
**Focus:** Modern Python PIL/Pillow approaches for PNG generation, subprocess alternatives

## Executive Summary

The current implementation uses subprocess spawning to avoid shared library conflicts with Indigo's embedded Python. For Python 3.11.6 with Pillow 10.x in 2026, **in-process generation is now feasible and recommended** because Indigo uses the same Python framework that the subprocess uses. The subprocess approach was necessary in older Python 2/3 hybrid environments but creates unnecessary complexity now.

**Recommendation:** Migrate to in-process generation using modern Pillow 10.x+ APIs with proper error isolation.

## Recommended Stack

### Core Image Generation

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Pillow | >=10.4.0 | PNG image generation | Modern, maintained PIL fork; extensive font/drawing APIs; Python 3.11 compatible |
| Python | 3.11.6 | Runtime environment | Already used by Indigo 2023.2+; subprocess uses same version |

**Rationale for in-process:**
- Indigo Python 3.11.6 and subprocess both use `/Library/Frameworks/Python.framework`
- No library conflicts in Python 3.11 (historical issue was Python 2.7 vs 3.x mixing)
- Eliminates subprocess overhead, logging complexity, timeout issues
- Enables direct error handling in main plugin log
- Simplifies testing and debugging

### Font Rendering

| Technology | Version | Purpose | When to Use |
|------------|---------|---------|-------------|
| TrueType fonts (.ttf) | N/A | Custom monospaced fonts | Already bundled in `BoardFonts/MFonts/` |
| ImageFont.truetype() | Built-in | Font loading | For all custom fonts |
| ImageFont.load_default() | Built-in | Fallback font | Only if .ttf files missing (error state) |

**Current fonts in use:**
- `Lekton-Bold.ttf` - Regular departure text (monospaced)
- `sui generis rg.ttf` - Station titles
- `Hack-RegularOblique.ttf` - Calling points (italic)

### Text Measurement & Layout

| API | Purpose | Why Use |
|-----|---------|---------|
| `ImageFont.getbbox()` | Text dimension calculation | Modern API (Pillow 8.0+), replaces deprecated `getsize()` |
| `ImageDraw.textbbox()` | Context-aware text measurement | More accurate than font-only measurement |
| `ImageDraw.text()` | Text rendering with anchor | Pillow 8.0+ supports anchor parameter for alignment |

**Migration needed:** Current code uses deprecated `font.getsize()` (line 123 in text2png.py). Must migrate to `getbbox()`.

### Color Management

| Approach | Current | Recommended |
|----------|---------|-------------|
| Color format | String hex colors from constants.py | Same, but validate format |
| Color space | RGBA | Continue using RGBA for transparency support |
| Color parsing | Direct string to PIL | Add validation: `PIL.ImageColor.getrgb()` |

### PNG Optimization

| Technology | Version | Purpose | When to Use |
|------------|---------|---------|-------------|
| Pillow PNG encoder | Built-in | PNG compression | Always (built-in to `Image.save()`) |
| `optimize=True` parameter | N/A | Reduce file size | For Pushover/iOS where bandwidth matters |
| `compress_level=6` | N/A | Balance size/speed | Default 6 is good; 9 for max compression |

**Not recommended:**
- External PNG optimizers (pngquant, optipng): Adds dependency, minimal benefit for text images
- PIL-SIMD: Requires C compilation, not worth complexity for occasional image generation

## Alternatives Considered

### Subprocess Alternatives

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **In-process (recommended)** | Simple, fast, unified logging, better error handling | Requires ensuring no library conflicts | **Use this** - conflicts resolved in Python 3.11 |
| Async/threading | Non-blocking generation | Adds complexity, Indigo already uses concurrent thread | Skip - unnecessary |
| Queue-based worker | Decouples generation from updates | Over-engineered for 60s polling interval | Skip - too complex |
| Keep subprocess | Known working (once fixed) | Fragile, hard to debug, timeout issues | **Migrate away** - historical workaround no longer needed |

### Image Generation Libraries

| Library | Pros | Cons | Verdict |
|---------|------|------|---------|
| **Pillow (recommended)** | Standard, comprehensive, well-maintained | Larger dependency | **Use this** - already in requirements.txt |
| PIL (original) | N/A | Abandoned since 2011 | Never use - Pillow is the fork |
| cairo + pycairo | Vector graphics, high quality | C dependency, overkill for text | Skip - too heavy |
| Wand (ImageMagick) | Powerful | Large C dependency, harder to bundle | Skip - unnecessary |
| matplotlib | Good for data viz | Heavy dependency, not for UI images | Skip - wrong tool |
| reportlab | PDF-focused | Not optimized for PNG | Skip - wrong domain |

### Why Not Modern Alternatives?

**Playwright/Puppeteer (browser rendering):**
- Massive dependencies (entire Chromium browser)
- Overkill for text-to-image
- Fragile in headless macOS environment

**HTML Canvas + node-canvas:**
- Requires Node.js runtime
- Plugin is pure Python
- Unnecessary complexity

## Installation

```bash
# Core dependency (already in requirements.txt)
/Library/Frameworks/Python.framework/Versions/Current/bin/python3 -m pip install 'Pillow>=10.4.0'

# No additional dependencies needed for in-process approach
```

**Version pinning strategy:**
- Use `>=10.4.0` to get security fixes
- Pillow 10.x series maintains API compatibility
- Avoid `Pillow>=11.0.0` until tested (major version)

## Migration Path: Subprocess → In-Process

### Step 1: Verify No Library Conflicts

**Test approach:**
```python
# In plugin.py, add to startup():
try:
    from PIL import Image, ImageFont, ImageDraw
    self.logger.info("PIL import successful in main plugin process")
except ImportError as e:
    self.logger.error(f"PIL import failed: {e}")
```

**Expected result:** Success (both plugin and subprocess use same Python 3.11.6 framework)

### Step 2: Refactor text2png.py → image_generator.py

**Current architecture:**
```
plugin.py → image_generator._generate_departure_image() → subprocess.run([text2png.py])
```

**New architecture:**
```
plugin.py → image_generator.generate_departure_image() [direct function call]
```

**Changes needed:**
1. Convert text2png.py script into callable function
2. Move PIL imports to module level in image_generator.py
3. Replace file-based parameter passing with function parameters
4. Return result object instead of subprocess.CompletedProcess

### Step 3: Modernize Pillow APIs

**Deprecated APIs to replace:**

| Deprecated | Modern Replacement | Line in text2png.py |
|------------|-------------------|---------------------|
| `font.getsize(text)` | `font.getbbox(text)[2:4]` | Line 123 |
| N/A | `Image.save(optimize=True)` | Line 222 (add parameter) |

**Compatibility:**
- `getbbox()` returns `(left, top, right, bottom)` tuple
- Extract width/height: `bbox[2] - bbox[0]`, `bbox[3] - bbox[1]`
- Or use `textbbox()` for full context-aware measurement

## Code Quality Improvements

### Error Handling

**Current issues:**
- Subprocess failures written to separate error log files
- No timeout enforcement
- Silent failures possible

**Modern approach:**
```python
def generate_departure_image(...):
    """Generate PNG in-process with comprehensive error handling."""
    try:
        from PIL import Image, ImageFont, ImageDraw
        # ... generation logic ...
        return {"success": True, "path": image_path}
    except FileNotFoundError as e:
        # Font file missing
        return {"success": False, "error": f"Font not found: {e}"}
    except OSError as e:
        # Disk full, permissions, etc.
        return {"success": False, "error": f"File system error: {e}"}
    except Exception as e:
        # Unexpected errors
        logger.exception("Image generation failed")
        return {"success": False, "error": str(e)}
```

### Performance Optimization

**Change detection (prevent unnecessary generation):**
```python
import hashlib

def _hash_board_content(board_text: str) -> str:
    """Generate hash of board content for change detection."""
    return hashlib.md5(board_text.encode()).hexdigest()

# In device update logic:
new_hash = _hash_board_content(board_content)
if new_hash != device.states.get('boardContentHash'):
    # Content changed, regenerate image
    generate_departure_image(...)
    indigo.device.updateStateOnServer(dev, 'boardContentHash', new_hash)
```

**Font caching (avoid reloading):**
```python
# Module-level cache
_font_cache = {}

def _get_font(font_path: Path, size: int) -> ImageFont.FreeTypeFont:
    """Load font with caching."""
    cache_key = (str(font_path), size)
    if cache_key not in _font_cache:
        _font_cache[cache_key] = ImageFont.truetype(str(font_path), size)
    return _font_cache[cache_key]
```

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_image_generation.py
def test_generate_image_success():
    """Test successful image generation."""
    result = generate_departure_image(
        image_path=tmp_path / "test.png",
        board_content="Test content",
        colors=ColorScheme(...),
        fonts=FontConfig(...)
    )
    assert result["success"] is True
    assert (tmp_path / "test.png").exists()

def test_generate_image_missing_font():
    """Test graceful handling of missing font."""
    result = generate_departure_image(
        fonts=FontConfig(base_font=Path("/nonexistent/font.ttf"))
    )
    assert result["success"] is False
    assert "Font not found" in result["error"]
```

### Integration Tests

```python
# tests/integration/test_image_quality.py
def test_image_dimensions():
    """Verify generated image has expected dimensions."""
    img = Image.open(generated_png)
    assert img.width == 800  # Expected width
    assert img.format == "PNG"

def test_color_scheme_applied():
    """Verify colors from constants applied correctly."""
    img = Image.open(generated_png)
    pixels = img.load()
    # Sample pixel at title location should match title color
    assert pixels[10, 10] == expected_title_color
```

## Known Limitations

### Font Availability

**Issue:** TrueType fonts bundled in `BoardFonts/MFonts/` directory
**Risk:** If fonts missing, falls back to default (looks bad)
**Mitigation:** Validate font files exist in plugin startup, log warning if missing

### Color Format Assumptions

**Issue:** Code assumes hex color strings from constants.py (e.g., "#RRGGBB")
**Risk:** Malformed colors cause PIL exceptions
**Mitigation:** Validate colors with `PIL.ImageColor.getrgb()` before use

### Text Wrapping

**Current approach:** Manual word-by-word width calculation (line 123-137 in text2png.py)
**Modern approach:** Pillow 8.0+ has no built-in text wrapping
**Recommendation:** Keep manual wrapping, but use `getbbox()` instead of `getsize()`

### Image Size Calculation

**Current:** Fixed `img_height = line_height * 30` (line 148)
**Issue:** May create oversized images with extra whitespace
**Improvement:** Calculate dynamic height based on actual lines rendered

## Confidence Assessment

| Area | Level | Source | Notes |
|------|-------|--------|-------|
| Pillow 10.x capabilities | HIGH | Current installation (10.2.0), API documentation in training data | Verified local installation |
| Python 3.11.6 compatibility | HIGH | System Python version check | Both plugin and subprocess use same interpreter |
| In-process feasibility | HIGH | Architecture analysis, no library conflicts in Py 3.11 | Historical subprocess reason no longer applies |
| Subprocess elimination | MEDIUM | Based on training data + codebase analysis | Should verify no hidden conflicts during migration |
| API deprecations (getsize) | HIGH | Pillow 10.x deprecation warnings | Training data from 2024 Pillow releases |
| PNG optimization parameters | MEDIUM | Training data on Pillow save() options | Standard PIL functionality |
| Font rendering accuracy | HIGH | Current code analysis + PIL APIs | Existing code already uses these APIs |

## Sources

**Verified locally:**
- Python version: `/Library/Frameworks/Python.framework/Versions/Current/bin/python3 --version` → 3.11.6
- Pillow version: `pip show Pillow` → 10.2.0
- Current implementation: `text2png.py`, `image_generator.py` in codebase

**Training data (early 2025):**
- Pillow 10.x API documentation
- Python 3.11 standard library documentation
- PIL/Pillow migration guides

**Limitations:**
- Cannot verify latest Pillow 11.x features (outside training window)
- Cannot verify macOS-specific PIL behavior via external search
- Subprocess conflict assumption based on codebase comments + architecture analysis

## Recommendations for Roadmap

### Phase 1: Fix Current Subprocess Approach (Quick Win)

**If in-process migration is too risky initially:**
1. Fix color scheme bug in text2png.py (immediate value)
2. Add subprocess timeout enforcement
3. Improve error logging (unify with main plugin log)
4. Add change detection to prevent unnecessary generation

**Effort:** 1-2 days
**Risk:** Low (minimal changes to working architecture)

### Phase 2: Migrate to In-Process (Modernization)

**After Phase 1 validates image generation works:**
1. Refactor text2png.py into image_generator module function
2. Test in-process PIL import (verify no conflicts)
3. Replace subprocess.run() with direct function call
4. Migrate deprecated `getsize()` to `getbbox()`
5. Add font caching for performance

**Effort:** 2-3 days
**Risk:** Medium (architecture change, but reversible)

### Phase 3: Optimize & Enhance (Future)

**Once in-process generation stable:**
1. Dynamic image sizing (eliminate whitespace)
2. PNG optimization for Pushover (compress_level tuning)
3. Support all 10 trains (not just 5)
4. Add unit/integration tests

**Effort:** 2-3 days
**Risk:** Low (incremental improvements)

---

**Overall confidence:** MEDIUM-HIGH
- High confidence in Pillow capabilities and Python 3.11 compatibility
- Medium confidence in subprocess elimination (should verify no hidden dependencies during testing)
- All recommendations based on codebase analysis + verified local environment + training data
