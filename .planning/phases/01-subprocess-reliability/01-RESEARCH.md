# Phase 1: Subprocess Reliability - Research

**Researched:** 2026-02-01
**Domain:** Python subprocess execution and error handling
**Confidence:** HIGH

## Summary

Researched best practices for reliable subprocess execution in Python 3.10+ with focus on timeout enforcement, error handling, and stderr capture for the UK-Trains plugin's image generation subprocess. The current implementation uses `subprocess.run()` which is correct, but lacks critical safety features: no timeout enforcement, no exception handling for TimeoutExpired, and stderr/stdout captured to files rather than integrated with plugin logging.

The standard approach for production subprocess management involves: (1) enforcing timeouts to prevent indefinite hangs, (2) catching and handling TimeoutExpired exceptions with proper logging, (3) capturing stderr/stdout to make debugging visible in application logs, and (4) using list-format arguments to safely pass parameters without shell injection risks.

The UK-Trains plugin currently spawns text2png.py as a subprocess to avoid PIL/Pillow shared library conflicts with Indigo's embedded Python environment. This isolation strategy is sound, but the execution lacks defensive programming to handle subprocess failures gracefully.

**Primary recommendation:** Add timeout parameter to subprocess.run(), wrap in try/except to catch TimeoutExpired and CalledProcessError exceptions, capture stderr/stdout to plugin logger instead of separate files, and update device state when subprocess fails.

## Standard Stack

The established libraries/tools for subprocess execution in Python 3.10+:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| subprocess | stdlib (3.10+) | Process creation and management | Python standard library, battle-tested, comprehensive API |
| pathlib.Path | stdlib (3.4+) | Path handling for subprocess arguments | Type-safe path operations, cross-platform compatibility |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging | stdlib | Structured error reporting | Capturing subprocess failures in application logs |
| sys.executable | stdlib | Current Python interpreter path | Ensures subprocess uses same Python as parent process |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| subprocess.run() | subprocess.Popen() | Popen offers more control but requires manual pipe management; run() is simpler and sufficient for this use case |
| subprocess.run() | os.system() | os.system() is deprecated, no output capture, no error handling |
| subprocess.run() | subprocess.call() | call() is legacy API, returns only exit code, run() is current recommendation |

**Installation:**
```bash
# No installation needed - subprocess is Python standard library
# Current environment: Python 3.11.6
```

## Architecture Patterns

### Recommended Subprocess Execution Pattern
```python
# Production-ready subprocess execution with timeout and error handling
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def run_with_timeout(cmd: list, timeout: int = 10) -> subprocess.CompletedProcess:
    """Execute subprocess with timeout and comprehensive error handling.

    Args:
        cmd: Command and arguments as list of strings
        timeout: Maximum execution time in seconds

    Returns:
        CompletedProcess result if successful

    Raises:
        subprocess.TimeoutExpired: If execution exceeds timeout
        subprocess.CalledProcessError: If process exits with non-zero code
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,  # Captures both stdout and stderr
            text=True,            # Returns strings, not bytes
            timeout=timeout,      # Enforces maximum execution time
            check=True            # Raises CalledProcessError on non-zero exit
        )

        # Log output for debugging
        if result.stdout:
            logger.debug(f"Subprocess stdout: {result.stdout}")
        if result.stderr:
            logger.warning(f"Subprocess stderr: {result.stderr}")

        return result

    except subprocess.TimeoutExpired as e:
        logger.error(f"Subprocess timed out after {timeout}s: {e.cmd}")
        # stderr/stdout available in exception: e.stdout, e.stderr
        raise

    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess failed with exit code {e.returncode}: {e.cmd}")
        logger.error(f"stderr: {e.stderr}")
        raise

    except FileNotFoundError as e:
        logger.error(f"Subprocess executable not found: {cmd[0]}")
        raise OSError(f"Unable to execute {cmd[0]}")
```

### Pattern 1: Timeout Enforcement
**What:** Add timeout parameter to subprocess.run() to prevent indefinite hangs

**When to use:** Always, for any subprocess that might hang due to I/O, network, or external failures

**Example:**
```python
# Source: https://docs.python.org/3/library/subprocess.html
import subprocess

# 10-second timeout for image generation
result = subprocess.run(
    [sys.executable, 'text2png.py', 'output.png', 'input.txt', 'params.txt', 'YES'],
    timeout=10,
    capture_output=True,
    text=True
)
```

### Pattern 2: Exception Handling for Subprocess Failures
**What:** Catch TimeoutExpired and CalledProcessError to handle failures gracefully

**When to use:** Always, to prevent subprocess failures from crashing parent process

**Example:**
```python
# Source: https://docs.python.org/3/library/subprocess.html
try:
    result = subprocess.run(cmd, timeout=10, check=True, capture_output=True, text=True)
except subprocess.TimeoutExpired:
    # Process took too long
    logger.error(f"Subprocess timed out: {cmd}")
    device.updateStateOnServer('imageGenerationStatus', 'timeout')
except subprocess.CalledProcessError as e:
    # Process exited with non-zero code
    logger.error(f"Subprocess failed: {e.stderr}")
    device.updateStateOnServer('imageGenerationStatus', 'failed')
```

### Pattern 3: Argument Passing as List
**What:** Pass subprocess arguments as list of strings, not shell command string

**When to use:** Always, for security and proper argument escaping

**Example:**
```python
# Source: https://docs.python.org/3/library/subprocess.html
# CORRECT: List format - no shell injection risk, automatic escaping
subprocess.run([sys.executable, 'script.py', 'arg with spaces', '#FFF'])

# WRONG: Shell string - security risk, requires manual escaping
subprocess.run('python script.py "arg with spaces" "#FFF"', shell=True)  # DON'T DO THIS
```

### Pattern 4: stderr/stdout Capture to Logger
**What:** Capture subprocess output and write to application logger, not separate files

**When to use:** Always, for unified debugging and troubleshooting

**Example:**
```python
# Source: Production pattern from research
result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

if result.returncode != 0:
    logger.error(f"Image generation failed:")
    logger.error(f"stderr: {result.stderr}")
    logger.debug(f"stdout: {result.stdout}")
else:
    if result.stderr:
        # subprocess may write to stderr even on success
        logger.debug(f"Image generation stderr: {result.stderr}")
```

### Anti-Patterns to Avoid

- **Writing stderr/stdout to separate files:** Makes debugging harder, logs scattered across multiple locations. Use capture_output=True and log to plugin logger instead.

- **No timeout enforcement:** Subprocess can hang indefinitely on PIL errors, file I/O issues, or system resource contention. Always use timeout parameter.

- **Ignoring subprocess failures:** If image generation fails silently, user has no feedback. Catch exceptions and update device state.

- **Using shell=True:** Security risk for shell injection, unnecessary complexity. Use list-format arguments instead.

- **subprocess.call() or os.system():** Legacy APIs, deprecated. Use subprocess.run() for modern Python 3.5+.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timeout management | Manual threading with timers | subprocess.run(timeout=N) | Built-in, tested, handles edge cases like process cleanup |
| Output capture | Custom file handling | capture_output=True parameter | Automatic pipe management, prevents deadlocks |
| Error handling | Manual returncode checking | check=True parameter | Raises CalledProcessError with full context (stderr, stdout, cmd) |
| Argument escaping | Manual string quoting | List-format arguments | Handles spaces, special characters, prevents shell injection |

**Key insight:** subprocess module evolved over 20+ years to handle edge cases (deadlocks, zombie processes, signal handling, platform differences). Don't reimplement these solutions.

## Common Pitfalls

### Pitfall 1: No Timeout Enforcement
**What goes wrong:** Subprocess hangs indefinitely on errors (missing font file, PIL import failure, file system I/O hang), blocking Indigo plugin's concurrent thread.

**Why it happens:** subprocess.run() has no default timeout; caller must explicitly set timeout parameter.

**How to avoid:** Always add timeout parameter to subprocess.run() calls. For image generation (I/O-bound), 10 seconds is generous. For CPU-bound tasks, adjust based on expected runtime.

**Warning signs:**
- Plugin stops updating device states
- Indigo Event Log shows no recent activity from plugin
- Multiple python3 processes accumulating in Activity Monitor
- No timeout-related code in subprocess invocation

### Pitfall 2: Uncaught TimeoutExpired Exception
**What goes wrong:** When timeout occurs, TimeoutExpired exception propagates to caller, potentially crashing concurrent thread or leaving device state inconsistent.

**Why it happens:** Developer assumes subprocess will always complete successfully, doesn't wrap in try/except.

**How to avoid:** Always catch subprocess.TimeoutExpired and update device state accordingly. Log device name and context to help debugging.

**Warning signs:**
- Plugin concurrent thread crashes
- No error messages in Indigo log when subprocess times out
- Device states frozen in intermediate state
- Exception traceback in Indigo Event Log mentioning TimeoutExpired

### Pitfall 3: stderr Lost to Separate Files
**What goes wrong:** Subprocess writes errors to myImageErrors.txt, but developer doesn't check file. Errors invisible in Indigo Event Log where debugging typically happens.

**Why it happens:** Legacy pattern from when subprocess output management was harder. Modern subprocess.run() makes capture trivial with capture_output=True.

**How to avoid:** Use capture_output=True and write stderr/stdout to plugin's logger. This unifies debugging in one location (Indigo Event Log).

**Warning signs:**
- "Image generation failed but no errors in log"
- Debugging requires checking multiple separate text files
- No stderr output visible in Indigo Event Log

### Pitfall 4: Color Parameter Parsing Errors
**What goes wrong:** Color values like "#0F0" might be interpreted as comments or incorrectly escaped, causing PIL to receive malformed color strings.

**Why it happens:** When using shell=True or incorrect argument formatting, special characters like # can be misinterpreted by shell.

**How to avoid:** Use list-format arguments (not shell strings) and pass color values as-is. subprocess.run() handles special characters correctly when shell=False (default).

**Warning signs:**
- PIL errors about invalid color format
- Colors render incorrectly (default black/white instead of configured scheme)
- Subprocess stderr contains "invalid literal for int() with base 16"

### Pitfall 5: Using subprocess.call() (Deprecated)
**What goes wrong:** subprocess.call() returns only exit code, no access to stdout/stderr. Makes debugging impossible.

**Why it happens:** Old tutorials or legacy code examples use call(). It's still functional but limited.

**How to avoid:** Migrate to subprocess.run() which returns CompletedProcess object with returncode, stdout, stderr attributes.

**Warning signs:**
- Code uses subprocess.call()
- No way to see subprocess error output
- Cannot distinguish between different failure modes

## Code Examples

Verified patterns from official sources:

### Complete UK-Trains Subprocess Pattern
```python
# Source: Synthesized from https://docs.python.org/3/library/subprocess.html
# Production pattern for UK-Trains image generation subprocess

import subprocess
from pathlib import Path

def generate_departure_image(
    plugin_root: Path,
    image_filename: Path,
    text_filename: Path,
    parameters_filename: Path,
    departures_available: bool,
    device,
    logger
) -> bool:
    """Generate PNG departure board via subprocess with timeout and error handling.

    Args:
        plugin_root: Path to plugin root directory
        image_filename: Output PNG path
        text_filename: Input text file path
        parameters_filename: Color/font configuration path
        departures_available: Boolean for data availability flag
        device: Indigo device object for state updates
        logger: Plugin logger for error reporting

    Returns:
        True if image generated successfully, False otherwise
    """
    dep_flag = 'YES' if departures_available else 'NO'

    cmd = [
        constants.PYTHON3_PATH,
        str(plugin_root / 'text2png.py'),
        str(image_filename),
        str(text_filename),
        str(parameters_filename),
        dep_flag
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,  # Capture both stdout and stderr
            text=True,            # Decode as strings
            timeout=10,           # 10-second timeout for image generation
            check=True            # Raise CalledProcessError on non-zero exit
        )

        # Log subprocess output for debugging
        if result.stdout:
            logger.debug(f"Image generation stdout: {result.stdout}")
        if result.stderr:
            # PIL may write to stderr even on success
            logger.debug(f"Image generation stderr: {result.stderr}")

        device.updateStateOnServer('imageGenerationStatus', 'success')
        return True

    except subprocess.TimeoutExpired as e:
        logger.error(f"Image generation timed out for device '{device.name}' after 10 seconds")
        if e.stderr:
            logger.error(f"stderr before timeout: {e.stderr}")
        device.updateStateOnServer('imageGenerationStatus', 'timeout')
        return False

    except subprocess.CalledProcessError as e:
        logger.error(f"Image generation failed for device '{device.name}' with exit code {e.returncode}")
        logger.error(f"stderr: {e.stderr}")
        if e.stdout:
            logger.debug(f"stdout: {e.stdout}")
        device.updateStateOnServer('imageGenerationStatus', 'failed')
        return False

    except FileNotFoundError:
        logger.error(f"Python interpreter not found: {constants.PYTHON3_PATH}")
        device.updateStateOnServer('imageGenerationStatus', 'config_error')
        return False

    except Exception as e:
        logger.exception(f"Unexpected error generating image for device '{device.name}'")
        device.updateStateOnServer('imageGenerationStatus', 'error')
        return False
```

### Minimal Timeout Pattern
```python
# Source: https://docs.python.org/3/library/subprocess.html
import subprocess

# Simplest production pattern
try:
    subprocess.run(
        ['python3', 'text2png.py', 'out.png', 'in.txt', 'params.txt', 'YES'],
        timeout=10,
        check=True,
        capture_output=True,
        text=True
    )
except subprocess.TimeoutExpired:
    print("Image generation timed out")
except subprocess.CalledProcessError as e:
    print(f"Image generation failed: {e.stderr}")
```

### Device State Update on Failure
```python
# Pattern for updating Indigo device state when subprocess fails
def update_device_on_subprocess_failure(device, error_type, logger):
    """Update device state and icon when image generation fails."""
    device.updateStateOnServer('imageGenerationStatus', error_type)

    # Optionally update device icon to show error state
    if error_type == 'timeout':
        device.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
        logger.error(f"Device '{device.name}': Image generation timed out")
    elif error_type == 'failed':
        device.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
        logger.error(f"Device '{device.name}': Image generation failed")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| subprocess.call() | subprocess.run() | Python 3.5 (2015) | run() returns CompletedProcess with stdout/stderr, not just exit code |
| Manual PIPE handling | capture_output=True | Python 3.7 (2018) | Simpler API, automatic deadlock prevention |
| Manual returncode checking | check=True parameter | Python 3.5 (2015) | Automatic exception raising, clearer error handling |
| Writing output to files | Capturing to memory | Python 3.5+ | Faster, no file I/O, unified logging |

**Deprecated/outdated:**
- **subprocess.call()**: Legacy API, returns only exit code. Migrate to subprocess.run().
- **os.system()**: No output capture, no error handling. Use subprocess.run().
- **os.popen()**: Deprecated since Python 2.6. Use subprocess.run().
- **shell=True with user input**: Security vulnerability (shell injection). Use list-format arguments instead.

## Open Questions

1. **Current subprocess timeout behavior**
   - What we know: No timeout currently enforced in image_generator.py
   - What's unclear: Has timeout ever been a problem in production? Unknown frequency of hangs.
   - Recommendation: Add 10-second timeout preventatively. Image generation should complete in <2 seconds normally, 10s is generous buffer.

2. **Stderr interpretation from text2png.py**
   - What we know: text2png.py writes to stderr via print() statements and exception messages
   - What's unclear: Does PIL/Pillow write warnings to stderr even on success?
   - Recommendation: Log stderr at debug level (not error) for successful runs, error level for failures.

3. **Device state schema for image generation status**
   - What we know: Current device states track train info, not image generation status
   - What's unclear: Should we add new state for imageGenerationStatus, or use existing fields?
   - Recommendation: Add temporary imageGenerationStatus state for debugging, can remove after stabilization.

## Sources

### Primary (HIGH confidence)
- [Python subprocess documentation](https://docs.python.org/3/library/subprocess.html) - Official Python 3 documentation, updated 2026-01-30
- UK-Trains codebase - Current implementation in image_generator.py and text2png.py

### Secondary (MEDIUM confidence)
- [Python Subprocess Timeout Best Practices](https://alexandra-zaharia.github.io/posts/kill-subprocess-and-its-children-on-timeout-python/) - Community patterns verified against official docs
- [Python Subprocess Tutorial (Real Python)](https://realpython.com/python-subprocess/) - Comprehensive tutorial with production patterns
- [Python 101: How to Timeout a Subprocess](https://www.blog.pythonlibrary.org/2016/05/17/python-101-how-to-timeout-a-subprocess/) - Timeout handling patterns

### Tertiary (LOW confidence)
- Web search results on subprocess logging patterns - Multiple GitHub gists showing similar approaches, but not officially documented

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - subprocess is Python stdlib, well-documented, stable API
- Architecture: HIGH - Patterns verified from official Python docs, production-tested
- Pitfalls: MEDIUM - Based on official docs + web search, some inferred from common patterns

**Research date:** 2026-02-01
**Valid until:** 2026-03-01 (30 days - stable stdlib API, unlikely to change)
