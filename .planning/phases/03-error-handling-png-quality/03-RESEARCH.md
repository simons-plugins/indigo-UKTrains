# Phase 3: Error Handling & PNG Quality - Research

**Researched:** 2026-02-02
**Domain:** Python exit codes, PIL/Pillow error handling, font fallback, PNG format compatibility
**Confidence:** HIGH

## Summary

Researched error handling patterns for subprocess-based image generation with specific exit codes, PIL/Pillow font fallback mechanisms, and PNG format compatibility across multiple display contexts (Indigo control pages, Pushover notifications, iOS UIImage). The current text2png.py implementation uses exit codes 21 and 22 inconsistently, lacks comprehensive error handling for PIL operations, and doesn't implement font fallback when TrueType fonts are missing.

The standard approach for production subprocess error reporting involves: (1) specific exit codes by error category (0=success, 1=file I/O, 2=PIL error, 3=other), enabling parent process to log meaningful error types, (2) try-except blocks around all PIL operations (ImageFont.truetype raises OSError when fonts not found), with graceful fallback to ImageFont.load_default(), and (3) PNG saved with optimize=True for cross-platform compatibility without additional parameters needed.

PNG format is universally supported across target platforms: Indigo serves static files with standard MIME types, Pushover API accepts image/png up to 5MB with automatic resizing, and iOS UIImage has native PNG support. Pillow's default PNG output (RGBA mode, DEFLATE compression) is compatible with all three contexts without format-specific tuning.

**Primary recommendation:** Implement standardized exit codes in text2png.py (0/1/2/3), wrap all PIL operations in try-except with specific error types (OSError for fonts, ValueError for PIL limits, Exception for unknown), fallback to ImageFont.load_default() when truetype fonts missing, and save PNG with optimize=True parameter.

## Standard Stack

The established libraries/tools for error handling and PNG generation:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sys | stdlib | Exit code handling via sys.exit() | Python standard library, universal subprocess communication |
| PIL/Pillow | 10.0+ | Image generation with PNG support | Industry standard for Python image processing, comprehensive format support |
| pathlib.Path | stdlib (3.4+) | Path handling for file operations | Type-safe, cross-platform, integrates with exception handling |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging | stdlib | Structured error reporting | Capturing error context before sys.exit() |
| os | stdlib | Legacy exit codes (os.EX_* constants) | Advanced exit code semantics on Unix systems |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Numeric exit codes | os.EX_* constants (sysexits.h) | EX_* more semantic but Windows-incompatible; stick to 0-3 for portability |
| ImageFont.load_default() | Bundled TTF as fallback | Default font simpler, no file distribution, sufficient for fallback |
| PIL/Pillow | Other image libraries (imageio, OpenCV) | Pillow is standard for Python, extensive format support, best PNG compatibility |

**Installation:**
```bash
# Pillow already installed for UK-Trains plugin
# sys, pathlib, logging are Python standard library
```

## Architecture Patterns

### Recommended Exit Code Scheme

Exit codes communicate error type from subprocess to parent process:

| Exit Code | Meaning | When to Use |
|-----------|---------|-------------|
| 0 | Success | Image generated and saved successfully |
| 1 | File I/O Error | Cannot read input files (text, parameters) or write PNG |
| 2 | PIL/Pillow Error | Font loading failed, image creation failed, PIL exceptions |
| 3 | Other Error | Argument parsing, unexpected exceptions, configuration errors |

This scheme follows Unix conventions (0=success, non-zero=failure) while providing specific error categories for debugging.

### Pattern 1: Exit Code Error Handling

**What:** Use specific exit codes to communicate error type from text2png.py to parent process

**When to use:** Always, for any subprocess that can fail in multiple ways

**Example:**
```python
# Source: Synthesized from https://docs.python.org/3/library/sys.html
import sys

# Success
try:
    img.save(imageFileName, 'png', optimize=True)
    sys.exit(0)  # Success
except OSError as e:
    print(f"File I/O error saving PNG: {e}", file=sys.stderr)
    sys.exit(1)  # File I/O error
except Exception as e:
    print(f"Unexpected error saving PNG: {e}", file=sys.stderr)
    sys.exit(3)  # Other error
```

### Pattern 2: Font Fallback with Try-Except

**What:** Attempt to load TrueType font, fallback to default font if file missing or unreadable

**When to use:** Always, for any font loading operation that might fail

**Example:**
```python
# Source: https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
from PIL import ImageFont

def load_font_with_fallback(font_path: str, size: int):
    """Load TrueType font with fallback to default font.

    Args:
        font_path: Path to .ttf font file
        size: Font size in points

    Returns:
        ImageFont object (FreeTypeFont or default)
    """
    try:
        return ImageFont.truetype(font_path, size)
    except OSError as e:
        # Font file not found or unreadable
        print(f"Warning: Could not load font '{font_path}': {e}", file=sys.stderr)
        print(f"Using default font instead", file=sys.stderr)
        return ImageFont.load_default()
    except Exception as e:
        # Unexpected error
        print(f"Unexpected error loading font '{font_path}': {e}", file=sys.stderr)
        return ImageFont.load_default()

# Usage
font = load_font_with_fallback(fontFullPath, fontsize + 4)
titleFont = load_font_with_fallback(fontFullPathTitle, fontsize + 12)
```

### Pattern 3: Comprehensive PIL Error Handling

**What:** Wrap all PIL operations in try-except blocks with specific exception types

**When to use:** Always, for production image generation code

**Example:**
```python
# Source: Synthesized from https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
import sys
from PIL import ImageFont, Image, ImageDraw

def generate_departure_board_png(
    image_path: str,
    text_path: str,
    params_path: str
) -> None:
    """Generate departure board PNG with comprehensive error handling.

    Exits with specific codes:
        0 = Success
        1 = File I/O error
        2 = PIL error
        3 = Other error
    """
    try:
        # Read input files
        try:
            with open(text_path, 'r') as f:
                board_text = f.read()
            with open(params_path, 'r') as f:
                params = f.read().strip().split(',')
        except (OSError, IOError) as e:
            print(f"Error reading input files: {e}", file=sys.stderr)
            sys.exit(1)  # File I/O error

        # Parse parameters
        try:
            fg_color = params[0]
            bg_color = params[1]
            fontsize = int(params[5])
            width = int(params[8])
        except (IndexError, ValueError) as e:
            print(f"Error parsing parameters: {e}", file=sys.stderr)
            sys.exit(3)  # Other error (malformed parameters)

        # Load fonts with fallback
        try:
            font = ImageFont.truetype('Lekton-Bold.ttf', fontsize)
        except OSError:
            print("Warning: Could not load font, using default", file=sys.stderr)
            font = ImageFont.load_default()

        # Create image
        try:
            img = Image.new("RGBA", (width, 400), bg_color)
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), board_text, fg_color, font=font)
        except ValueError as e:
            # PIL limits exceeded (e.g., MAX_STRING_LENGTH)
            print(f"PIL error creating image: {e}", file=sys.stderr)
            sys.exit(2)  # PIL error
        except Exception as e:
            print(f"Unexpected error creating image: {e}", file=sys.stderr)
            sys.exit(2)  # PIL error

        # Save PNG
        try:
            img.save(image_path, 'png', optimize=True)
        except OSError as e:
            print(f"Error writing PNG file: {e}", file=sys.stderr)
            sys.exit(1)  # File I/O error
        except Exception as e:
            print(f"Unexpected error saving PNG: {e}", file=sys.stderr)
            sys.exit(3)  # Other error

        # Success
        sys.exit(0)

    except Exception as e:
        # Catch-all for unexpected errors
        print(f"Unexpected error in image generation: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(3)  # Other error
```

### Pattern 4: Parent Process Exit Code Handling

**What:** Check subprocess exit code and log specific error type to plugin log

**When to use:** Always, when processing subprocess results

**Example:**
```python
# Source: Synthesized from Phase 1 research
import subprocess

def handle_image_generation_result(result: subprocess.CompletedProcess, device, logger):
    """Process image generation subprocess result with exit code handling.

    Args:
        result: CompletedProcess from subprocess.run()
        device: Indigo device object
        logger: Plugin logger
    """
    if result.returncode == 0:
        logger.debug(f"Image generated successfully for '{device.name}'")
        device.updateStateOnServer('imageGenerationStatus', 'success')
        return True

    elif result.returncode == 1:
        logger.error(f"File I/O error generating image for '{device.name}'")
        logger.error(f"stderr: {result.stderr}")
        device.updateStateOnServer('imageGenerationStatus', 'file_error')
        device.updateStateOnServer('displayStateImageSel', 'SensorTripped')
        return False

    elif result.returncode == 2:
        logger.error(f"PIL error generating image for '{device.name}'")
        logger.error(f"stderr: {result.stderr}")
        device.updateStateOnServer('imageGenerationStatus', 'pil_error')
        device.updateStateOnServer('displayStateImageSel', 'SensorTripped')
        return False

    elif result.returncode == 3:
        logger.error(f"Other error generating image for '{device.name}'")
        logger.error(f"stderr: {result.stderr}")
        device.updateStateOnServer('imageGenerationStatus', 'other_error')
        device.updateStateOnServer('displayStateImageSel', 'SensorOff')
        return False

    else:
        logger.error(f"Unknown exit code {result.returncode} for '{device.name}'")
        logger.error(f"stderr: {result.stderr}")
        device.updateStateOnServer('imageGenerationStatus', 'unknown_error')
        return False
```

### Pattern 5: PNG Optimization for Cross-Platform Compatibility

**What:** Save PNG with optimize=True for maximum compatibility and reasonable file size

**When to use:** Always, for PNG files served across multiple platforms

**Example:**
```python
# Source: https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html
from PIL import Image

# Create RGBA image (supports transparency, compatible everywhere)
img = Image.new("RGBA", (720, 400), background_color)
draw = ImageDraw.Draw(img)
# ... draw content ...

# Save with optimization
# optimize=True: Pillow performs extra pass to select optimal encoder settings
# No compress_level needed: optimize overrides it to 9 (max compression)
# No quality needed: PNG is lossless
img.save(image_path, 'png', optimize=True)

# Result: PNG with DEFLATE compression, compatible with:
# - Indigo control pages (static file serving)
# - Pushover API (image/png MIME type, <5MB)
# - iOS UIImage (native PNG support)
```

### Anti-Patterns to Avoid

- **Using same exit code for all errors:** Makes debugging impossible. Parent process can't distinguish file I/O from PIL errors. Use specific codes (0/1/2/3).

- **Not handling OSError from ImageFont.truetype:** Font files can be missing, corrupted, or unreadable. Always wrap in try-except with fallback to load_default().

- **Calling sys.exit() inside try block without re-raising:** Catches sys.exit()'s SystemExit exception, preventing proper exit. Put sys.exit() after try-except or in finally block.

- **Using print(sys.exit(22)):** This prints None and exits with code 0 (success), not 22. Incorrect pattern in current text2png.py line 79.

- **Not logging stderr before exit:** Parent process needs context to debug failures. Always print error message to stderr before sys.exit().

- **Setting PNG quality parameter:** PNG is lossless, quality parameter doesn't apply (that's JPEG). Use optimize=True instead.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exit code constants | Custom error codes >127 | 0/1/2/3 in range 0-127 | Unix convention, shell compatibility, no magic numbers needed |
| Font fallback | Custom bitmap font | ImageFont.load_default() | Built into Pillow, guaranteed to work, no file distribution |
| PNG compression | Manual DEFLATE tuning | optimize=True parameter | Pillow automatically selects best settings for file size |
| Error type detection | String parsing from stderr | Specific exception types (OSError, ValueError) | Python exception hierarchy designed for this, more reliable |

**Key insight:** Python's exception hierarchy and Pillow's error handling are designed for exactly this use case. OSError for file operations, ValueError for PIL limits, and sys.exit() with numeric codes provide standard, battle-tested error communication between subprocess and parent.

## Common Pitfalls

### Pitfall 1: Incorrect sys.exit() Usage

**What goes wrong:** Code like `print(sys.exit(22))` (line 79 in current text2png.py) prints None and exits with code 0, not 22. Parent process sees success when file I/O failed.

**Why it happens:** sys.exit() raises SystemExit exception, doesn't return a value. Wrapping in print() catches the exception and prints the return value (None).

**How to avoid:** Call sys.exit() directly, not inside print(). Use separate print() to stderr before sys.exit().

**Correct pattern:**
```python
except (IOError, OSError) as e:
    print(f"Error reading file: {e}", file=sys.stderr)
    sys.exit(1)  # Not print(sys.exit(1))
```

**Warning signs:**
- Subprocess always returns exit code 0
- Error messages printed but parent sees success
- `print(sys.exit(...))` in code

### Pitfall 2: No Font Fallback

**What goes wrong:** ImageFont.truetype() raises OSError when font file missing, crashing subprocess with unhandled exception. No PNG generated, but exit code is non-zero with Python traceback, not meaningful error message.

**Why it happens:** Font files assumed to exist at hardcoded paths (lines 94-96 in text2png.py), but distribution may be incomplete or paths may be wrong.

**How to avoid:** Wrap all ImageFont.truetype() calls in try-except, fallback to ImageFont.load_default() on OSError.

**Warning signs:**
- OSError traceback mentioning font paths
- Image generation fails after plugin installation
- Works on developer machine, fails on user machine
- Fonts exist but path separator wrong (Windows vs Unix)

### Pitfall 3: Not Including Color Parameters in Error Reporting

**What goes wrong:** Color parsing errors (invalid hex format, wrong parameter count) cause cryptic PIL errors or crashes without context about which device/route triggered the error.

**Why it happens:** Parameters read from file without validation, passed directly to PIL.

**How to avoid:** Validate color format before creating image. Log device name and parameters in error messages.

**Warning signs:**
- PIL error "invalid literal for int() with base 16"
- Image generation works for some devices, fails for others
- Error messages lack context about which route failed

### Pitfall 4: Exit Code Range Violations

**What goes wrong:** Using exit codes outside 0-255 range (Python modulo 256s them) or above 127 (conflicts with shell signals). Current code uses 21, 22 which are non-standard and don't communicate error category.

**Why it happens:** Arbitrary numbers chosen without considering exit code conventions or parent process interpretation.

**How to avoid:** Stick to 0-3 range: 0=success, 1=file I/O, 2=PIL error, 3=other. Simple, standard, shell-compatible.

**Warning signs:**
- Exit codes >127
- Exit codes don't correspond to error categories
- Documentation doesn't explain exit code meanings
- Parent process can't distinguish error types

### Pitfall 5: PNG Format Parameters Confusion

**What goes wrong:** Attempting to set quality parameter (JPEG-specific) or compress_level without optimize, producing larger files or ignored parameters.

**Why it happens:** Confusion between JPEG (quality 0-100) and PNG (compress_level 0-9, optimize flag) parameters.

**How to avoid:** For PNG: use `optimize=True`, omit quality. Optimize automatically sets compress_level=9. For JPEG: use quality, omit optimize.

**Warning signs:**
- PNG files larger than expected
- quality parameter in PNG save call
- compress_level set without optimize=True
- PIL warnings about ignored parameters

## Code Examples

Verified patterns from official sources:

### Complete text2png.py Error Handling Pattern

```python
# Source: Synthesized from https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
# Production pattern for UK-Trains text2png.py with exit codes and font fallback

import os, sys
from pathlib import Path

# Import PIL with error handling
try:
    from PIL import ImageFont, Image, ImageDraw
except ImportError as e:
    print(f"PILLOW or PIL must be installed: {e}", file=sys.stderr)
    sys.exit(2)  # PIL error (library not available)

def load_font_safe(font_path: str, size: int, font_name: str = "font"):
    """Load TrueType font with fallback to default.

    Args:
        font_path: Path to .ttf file
        size: Font size in points
        font_name: Description for error messages

    Returns:
        ImageFont object (truetype or default)
    """
    try:
        return ImageFont.truetype(font_path, size)
    except OSError as e:
        print(f"Warning: Could not load {font_name} '{font_path}': {e}", file=sys.stderr)
        print(f"Using default font for {font_name}", file=sys.stderr)
        return ImageFont.load_default()

def main():
    """Generate departure board PNG with comprehensive error handling."""

    # Validate arguments
    if len(sys.argv) < 5:
        print("Error: Insufficient arguments", file=sys.stderr)
        print(f"Usage: {sys.argv[0]} <image_file> <text_file> <params_file> <YES|NO>",
              file=sys.stderr)
        sys.exit(3)  # Other error (usage)

    image_filename = sys.argv[1]
    train_text_file = sys.argv[2]
    parameters_filename = sys.argv[3]
    departures_available = sys.argv[4]

    trains_found = 'YES' in departures_available

    # Read parameters file
    try:
        with open(parameters_filename, 'r') as f:
            params = f.read().strip().split(',')

        forcolour = params[0]
        bgcolour = params[1]
        isscolour = params[2]
        ticolour = params[3]
        cpcolour = params[4]
        fontsize = int(params[5])
        leftpadding = int(params[6])
        rightpadding = int(params[7])
        width = int(params[8])

    except (OSError, IOError) as e:
        print(f"Error reading parameters file '{parameters_filename}': {e}", file=sys.stderr)
        sys.exit(1)  # File I/O error
    except (IndexError, ValueError) as e:
        print(f"Error parsing parameters: {e}", file=sys.stderr)
        print(f"Parameters: {params}", file=sys.stderr)
        sys.exit(3)  # Other error (malformed parameters)

    # Read board text file
    try:
        with open(train_text_file, 'r') as f:
            station_titles = f.readline()
            station_statistics = f.readline()
            timetable = f.read()

    except (OSError, IOError) as e:
        print(f"Error reading text file '{train_text_file}': {e}", file=sys.stderr)
        sys.exit(1)  # File I/O error

    # Get plugin directory for fonts
    pypath = Path(sys.path[0])

    # Load fonts with fallback
    font_path = pypath / 'BoardFonts/MFonts/Lekton-Bold.ttf'
    title_path = pypath / 'BoardFonts/MFonts/sui generis rg.ttf'
    calling_path = pypath / 'BoardFonts/MFonts/Hack-RegularOblique.ttf'

    font = load_font_safe(str(font_path), fontsize + 4, "regular font")
    title_font = load_font_safe(str(title_path), fontsize + 12, "title font")
    calling_font = load_font_safe(str(calling_path), fontsize + 2, "calling points font")

    # Create image
    try:
        img_height = 400  # Calculate based on content
        img = Image.new("RGBA", (width, img_height), bgcolour)
        draw = ImageDraw.Draw(img)

        # Draw station titles
        y = 0
        draw.text((leftpadding, y), station_titles.strip(), ticolour, font=title_font)
        y += 30
        draw.text((leftpadding, y), station_statistics.strip(), cpcolour, font=font)

        # Draw timetable content
        # ... existing drawing logic ...

    except ValueError as e:
        # PIL limits exceeded (e.g., string too long, invalid color)
        print(f"PIL error creating image: {e}", file=sys.stderr)
        sys.exit(2)  # PIL error
    except Exception as e:
        print(f"Unexpected error creating image: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)  # PIL error

    # Save PNG
    try:
        img.save(image_filename, 'png', optimize=True)
    except OSError as e:
        print(f"Error writing PNG file '{image_filename}': {e}", file=sys.stderr)
        sys.exit(1)  # File I/O error
    except Exception as e:
        print(f"Unexpected error saving PNG: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(3)  # Other error

    # Success
    sys.exit(0)

if __name__ == '__main__':
    main()
```

### Parent Process Exit Code Handling

```python
# Source: Integration with Phase 1 subprocess pattern
import subprocess

def generate_with_exit_code_handling(cmd, device, logger):
    """Execute image generation subprocess and handle exit codes.

    Args:
        cmd: Command list for subprocess.run()
        device: Indigo device object
        logger: Plugin logger

    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False  # Don't raise on non-zero exit, handle manually
        )

        # Log subprocess output
        if result.stdout:
            logger.debug(f"Image generation output: {result.stdout}")

        # Handle exit codes
        if result.returncode == 0:
            logger.debug(f"Image generated successfully for '{device.name}'")
            device.updateStateOnServer('imageGenerationStatus', 'success')
            device.updateStateOnServer('imageGenerationError', '')
            return True

        elif result.returncode == 1:
            # File I/O error
            error_msg = "File I/O error (cannot read input or write PNG)"
            logger.error(f"{error_msg} for device '{device.name}'")
            logger.error(f"Details: {result.stderr}")
            device.updateStateOnServer('imageGenerationStatus', 'failed')
            device.updateStateOnServer('imageGenerationError', error_msg)
            return False

        elif result.returncode == 2:
            # PIL error
            error_msg = "PIL/Pillow error (font loading or image creation failed)"
            logger.error(f"{error_msg} for device '{device.name}'")
            logger.error(f"Details: {result.stderr}")
            device.updateStateOnServer('imageGenerationStatus', 'failed')
            device.updateStateOnServer('imageGenerationError', error_msg)
            return False

        elif result.returncode == 3:
            # Other error
            error_msg = "Configuration or unexpected error"
            logger.error(f"{error_msg} for device '{device.name}'")
            logger.error(f"Details: {result.stderr}")
            device.updateStateOnServer('imageGenerationStatus', 'failed')
            device.updateStateOnServer('imageGenerationError', error_msg)
            return False

        else:
            # Unknown exit code
            error_msg = f"Unknown error (exit code {result.returncode})"
            logger.error(f"{error_msg} for device '{device.name}'")
            logger.error(f"Details: {result.stderr}")
            device.updateStateOnServer('imageGenerationStatus', 'failed')
            device.updateStateOnServer('imageGenerationError', error_msg)
            return False

    except subprocess.TimeoutExpired as e:
        logger.error(f"Image generation timed out for device '{device.name}'")
        device.updateStateOnServer('imageGenerationStatus', 'timeout')
        device.updateStateOnServer('imageGenerationError', 'Timeout after 10 seconds')
        return False

    except Exception as e:
        logger.exception(f"Unexpected error in image generation for '{device.name}'")
        device.updateStateOnServer('imageGenerationStatus', 'error')
        device.updateStateOnServer('imageGenerationError', str(e))
        return False
```

### Font Fallback Pattern

```python
# Source: https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
from PIL import ImageFont
import sys

def get_fonts_with_fallback(pypath, fontsize):
    """Load all fonts with individual fallback.

    Returns dict of font objects, using default font for any that fail to load.
    """
    fonts = {}

    font_configs = [
        ('regular', f'{pypath}BoardFonts/MFonts/Lekton-Bold.ttf', fontsize + 4),
        ('title', f'{pypath}BoardFonts/MFonts/sui generis rg.ttf', fontsize + 12),
        ('status', f'{pypath}BoardFonts/MFonts/Lekton-Bold.ttf', fontsize + 5),
        ('depart', f'{pypath}BoardFonts/MFonts/Lekton-Bold.ttf', fontsize + 8),
        ('delay', f'{pypath}BoardFonts/MFonts/Lekton-Bold.ttf', fontsize + 4),
        ('calling', f'{pypath}BoardFonts/MFonts/Hack-RegularOblique.ttf', fontsize + 2),
        ('messages', f'{pypath}BoardFonts/MFonts/Hack-RegularOblique.ttf', fontsize),
    ]

    for name, path, size in font_configs:
        try:
            fonts[name] = ImageFont.truetype(path, size)
        except OSError as e:
            print(f"Warning: Could not load {name} font from '{path}': {e}",
                  file=sys.stderr)
            print(f"Using default font for {name}", file=sys.stderr)
            fonts[name] = ImageFont.load_default()

    return fonts

# Usage
fonts = get_fonts_with_fallback(pypath, fontsize)
draw.text((x, y), text, color, font=fonts['title'])
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single exit code for all errors | Specific codes by category (0/1/2/3) | Unix convention (1970s) | Parent process can log error type, aids debugging |
| IOError exception | OSError exception | Python 3.3 (2012) | OSError is parent class, catch OSError for all file errors |
| Manual font checking | Try-except with fallback | Modern practice | Graceful degradation, user sees board even without custom fonts |
| PNG without optimization | PNG with optimize=True | Pillow best practice | Smaller files, faster loading, same visual quality |

**Deprecated/outdated:**
- **IOError**: Merged into OSError in Python 3.3. Use OSError for file operations.
- **Exit codes >127**: Conflicts with shell signal codes. Stick to 0-127 range.
- **print(sys.exit(N))**: Incorrect pattern, exits with 0 not N. Call sys.exit() directly.
- **Assuming fonts exist**: No validation, crashes on missing files. Use try-except with fallback.

## Open Questions

1. **Device state schema for error messages**
   - What we know: Current device states track train info, imageGenerationStatus exists from Phase 1
   - What's unclear: Should we add imageGenerationError state for user-visible error message?
   - Recommendation: Add imageGenerationError state to store last error message. Useful for Indigo triggers and control page display.

2. **Font fallback user notification**
   - What we know: Font fallback works silently, user may not realize custom fonts aren't loading
   - What's unclear: Should plugin log font fallback at INFO or DEBUG level?
   - Recommendation: Log at WARNING level on first occurrence per plugin startup. Alerts user without spamming log every 60 seconds.

3. **PNG file size limits**
   - What we know: Pushover has 5MB limit, departure boards are typically <100KB
   - What's unclear: Should we validate PNG size before considering generation successful?
   - Recommendation: No validation needed. Departure boards are text-based, extremely unlikely to exceed 1MB even with optimize=False.

4. **Exit code standardization across plugins**
   - What we know: UK-Trains uses custom codes (21, 22), other Indigo plugins may use different schemes
   - What's unclear: Is there an Indigo plugin exit code convention?
   - Recommendation: Use 0/1/2/3 scheme for UK-Trains. Simple, standard, doesn't depend on Indigo-specific conventions.

## Sources

### Primary (HIGH confidence)
- [Python sys module documentation](https://docs.python.org/3/library/sys.html) - Official Python 3 documentation for sys.exit()
- [Pillow ImageFont documentation](https://pillow.readthedocs.io/en/stable/reference/ImageFont.html) - Official Pillow 12.1.0 documentation (2026-01-02)
- [Pillow Image file formats](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html) - PNG save options and parameters
- [Pushover API documentation](https://pushover.net/api) - Image attachment requirements
- [Python Built-in Exceptions](https://docs.python.org/3/library/exceptions.html) - OSError, IOError, FileNotFoundError hierarchy

### Secondary (MEDIUM confidence)
- [Exit Code Best Practices](https://chrisdown.name/2013/11/03/exit-code-best-practises.html) - Unix exit code conventions
- [Controlling Python Exit Codes and Shell Scripts](https://henryleach.com/2025/02/controlling-python-exit-codes-and-shell-scripts/) - Recent (2025) article on exit codes
- [iOS Loading Images Guide](https://developer.apple.com/library/archive/documentation/2DDrawing/Conceptual/DrawingPrintingiOS/LoadingImages/LoadingImages.html) - UIImage format support
- [PNG Specification](http://www.libpng.org/pub/png/spec/1.2/png-1.2-pdg.html) - Color depth and format details

### Tertiary (LOW confidence)
- Web search results on PIL exception handling - Common patterns but not officially documented
- Community discussions about Pillow font issues - Real-world problems but not authoritative

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - sys, Pillow are standard library and industry standard respectively
- Architecture: HIGH - Exit codes follow Unix conventions, exception handling verified from official docs
- Pitfalls: HIGH - Based on actual bugs in current text2png.py code and official docs
- PNG compatibility: MEDIUM - Pushover/iOS support verified, but Indigo serving behavior inferred

**Research date:** 2026-02-02
**Valid until:** 2026-03-02 (30 days - stable APIs, exit code conventions unchanged for decades)
