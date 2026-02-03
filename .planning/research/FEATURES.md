# Feature Landscape: Departure Board Images

**Domain:** Departure board PNG generation for multi-platform display
**Researched:** 2026-02-01

## Table Stakes

Features users expect from any departure board image. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Destination display | Core train information | Low | Currently implemented; first column |
| Scheduled departure time | Expected behavior baseline | Low | Currently implemented; STD column |
| Estimated/actual time | Real-time accuracy | Low | Currently implemented; ETD column |
| Delay indication | Critical for decision-making | Low | Currently implemented; visual red text |
| Operator/service info | Train selection/planning | Low | Currently implemented; operator code |
| Platform number | Station navigation | Low | **NOT currently implemented** |
| Clear visual hierarchy | Readability at-a-glance | Medium | Partially implemented via fonts/colors |
| Monospace alignment | Column readability | Low | Currently implemented via font choice |
| Readable at small sizes | Mobile/notification use | Medium | **Needs validation** for 320px width |
| Cancellation visibility | Safety-critical information | Low | Currently implemented; red text + status |
| Time-ordered display | Expected chronological flow | Low | Currently implemented; API returns ordered |

## Quality Requirements

Non-functional requirements for image generation across display contexts.

### Resolution & Dimensions

| Context | Min Width | Min Height | Aspect Ratio | Notes |
|---------|-----------|------------|--------------|-------|
| Indigo Control Page (desktop) | 720px | 400px | ~16:9 | Current implementation |
| Mobile Push (Pushover) | 320px | Variable | Any | Service auto-resizes; keep width ≥320px |
| iOS Native Display | 375px | Variable | Device-dependent | iPhone SE minimum; support @2x/@3x |
| Web Responsive | 320px-1200px | Variable | Maintain aspect | Consider viewport scaling |

**Recommendation:** Generate at 1440px width (@2x for 720px logical) to support retina displays while maintaining 720px base compatibility.

### File Size & Performance

| Context | Max Size | Constraint | Impact |
|---------|----------|------------|--------|
| Indigo Control Page | 500KB | Network latency for refresh | Slow page loads if too large |
| Pushover Notification | 2.5MB | Service hard limit | Rejection if exceeded |
| iOS App | 1MB | Mobile data usage | User experience degradation |

**Current state:** PNG with PIL compression; file size unknown and not monitored.

**Recommendation:** Target ≤250KB for typical 5-train board. Monitor via file size check post-generation.

### Color Depth & Format

| Requirement | Value | Rationale |
|------------|-------|-----------|
| Color mode | RGB or RGBA | RGBA supports transparency for compositing |
| Bit depth | 8-bit per channel (24-bit RGB) | Sufficient for departure board colors |
| Compression | PNG default (zlib) | Lossless; good for text/solid colors |
| Transparency | Optional; alpha channel if needed | May help with iOS dark mode support |
| Color profile | sRGB | Standard for web/mobile display |

**Current state:** Code uses `img = Image.new("RGBA", ...)` — already supports transparency.

**Recommendation:** Continue with RGBA; consider adding optional transparency for dark mode backgrounds.

### Text Rendering

| Feature | Requirement | Current State | Notes |
|---------|-------------|---------------|-------|
| Anti-aliasing | Required for readability | **Unknown** | PIL default; verify enabled |
| Font rendering quality | Subpixel or grayscale | **Unknown** | May need explicit PIL config |
| Minimum font size | 10pt (13px) for body text | 9+4=13px (font size 9, actual 13) | Meets minimum |
| Contrast ratio | 4.5:1 for normal text (WCAG AA) | Green on black = ~14:1 | Exceeds requirement |
| Emoji support | Not required | N/A | Train operators use text codes |

**Recommendation:** Verify anti-aliasing enabled in PIL ImageDraw; current font sizes adequate.

## Platform-Specific Features

### Web Display (Indigo Control Pages)

| Feature | Priority | Complexity | Notes |
|---------|----------|------------|-------|
| Responsive scaling | High | Low | Browser handles if max-width set |
| Retina display support | High | Medium | @2x generation recommended |
| Auto-refresh via URL | High | Low | Currently implemented |
| Lazy loading | Medium | Low | Browser native; add loading="lazy" |
| CORS compatibility | Low | Low | Same-origin; not applicable |
| WebP fallback | Low | Medium | PNG universally supported; defer |

**Key requirement:** Image must refresh when URL changes (currently implemented via timestamped filenames or cache-busting).

### Mobile Push (Pushover)

| Feature | Priority | Complexity | Notes |
|---------|----------|------------|-------|
| 2.5MB size limit | Critical | Low | Must validate file size |
| JPEG/PNG support | High | Low | PNG already supported |
| Portrait orientation | High | Low | Vertical boards read better on mobile |
| Thumbnail generation | Medium | N/A | Pushover auto-generates |
| Offline viewing | Medium | N/A | Pushover caches images |
| High-DPI support | Medium | Medium | @2x recommended |

**Key requirement:** File size monitoring essential — exceeding 2.5MB causes notification failure.

**Recommendation:** Add file size check after generation; warn if >2MB.

### iOS Native Display

| Feature | Priority | Complexity | Notes |
|---------|----------|------------|-------|
| @2x/@3x asset support | High | Medium | Generate 1440px or 2160px width |
| Dark mode variant | Medium | Medium | Alternative color scheme |
| Dynamic Type scaling | Low | High | Text-based display preferred for accessibility |
| Accessibility labels | Medium | Medium | Alternative text representation needed |
| UIImage compatibility | High | Low | PNG universally supported |
| Memory efficiency | High | Medium | Avoid loading full-res unnecessarily |

**Key requirement:** Generate @2x (1440px) minimum for retina displays; optionally @3x (2160px) for iPhone Pro models.

**Recommendation:** Generate single @2x image; iOS downsamples efficiently. Defer dark mode until requested.

## Differentiators

Features that set product apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Real-time calling points | Journey planning confidence | Low | **Currently implemented** |
| Service-specific delay reasons | User understanding of delays | Low | **Partially implemented** (captured but display limited) |
| Color-coded delay severity | At-a-glance urgency | Medium | Red for delays; could add orange for minor |
| Animated transitions | Modern feel (web/iOS) | High | Requires video format or CSS; defer |
| Historical delay tracking | Pattern recognition | High | Requires data storage; out of scope |
| Multi-language support | International users | Medium | National Rail is English-only; N/A |
| Accessibility mode (high contrast) | WCAG AAA compliance | Low | Additional color scheme option |
| Live departure countdown | Real-time urgency | Medium | Requires client-side updates or video |
| Platform change alerts | Highlighted in red | Medium | Would need platform number first |
| Weather integration | Delay context | High | Out of scope for image fix |

**Quick win recommendation:** Add high-contrast accessibility color scheme (black on yellow, white on blue) as alternative to green-on-black.

## Anti-Features

Features to explicitly NOT build. Common mistakes in this domain.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Animated GIFs | File size explodes (>5MB typical); poor mobile performance | Static PNG with client-side refresh |
| Custom web fonts | Subprocess can't access web fonts; increases complexity | Use bundled TTF fonts only |
| SVG format | Complex rendering in PIL; compatibility issues with Pushover | Stick with PNG raster format |
| Real-time updates in image | Requires video/GIF; defeats caching | Generate new static image on data change |
| Excessive detail (full timetable) | Cognitive overload; file size | Limit to 5-10 next departures |
| Background images/textures | Reduces text contrast; increases file size | Solid color backgrounds only |
| Fancy gradients/shadows | Increases file size; reduces clarity | Flat design with clear contrast |
| Interactive elements | PNG is static; not supported | Keep interactivity in UI layer |
| Client-side rendering | Indigo control pages need server-side images | Continue server-side generation |
| Video format (MP4/WebM) | Massive overkill; compatibility issues | Static images only |

**Critical anti-feature:** Do NOT generate images on every refresh if data hasn't changed. Wastes CPU and causes unnecessary disk writes.

## Feature Dependencies

```
Readable departure board
    ├── Text rendering (fonts, anti-aliasing)
    ├── Color scheme (contrast, clarity)
    ├── Layout (alignment, spacing)
    └── Data formatting (times, delays, operators)
        └── API data (must be fetched first)

Multi-platform support
    ├── Resolution scaling (@1x, @2x, @3x)
    ├── File size optimization (compression, dimensions)
    └── Format compatibility (PNG with RGBA)

Performance
    ├── Change detection (avoid unnecessary generation)
    ├── File size limits (Pushover 2.5MB, practical <500KB)
    └── Generation speed (subprocess overhead)
```

## MVP Recommendation

For this fix/modernization effort, prioritize:

1. **Restore working PNG generation** (table stakes)
   - Fix color scheme passing to subprocess
   - Verify PIL rendering quality
   - Validate output file creation

2. **Add file size monitoring** (critical for Pushover)
   - Log file size after generation
   - Warn if >2MB (approaching Pushover limit)
   - Target <250KB for typical boards

3. **Implement change detection** (performance/reliability)
   - Only generate PNG when train data actually changes
   - Compare previous board state before spawning subprocess
   - Reduces unnecessary CPU usage

4. **Validate multi-platform rendering** (quality)
   - Test at 320px width (mobile minimum)
   - Verify readability at @1x and @2x scaling
   - Check Pushover notification display
   - Test iOS app image loading

5. **Add retina support** (quality differentiator)
   - Generate at 1440px width (@2x for 720px logical)
   - Maintain aspect ratio
   - Verify file size remains <500KB

Defer to post-fix:

- **Platform numbers** — Requires Darwin API schema investigation (not all services provide platform)
- **Dark mode variant** — iOS app not yet requesting; add when needed
- **High-contrast accessibility** — Nice to have; defer until user requests
- **@3x support (2160px)** — Overkill for departure boards; @2x sufficient
- **Animated updates** — Requires format change; out of scope

## Implementation Notes

### Current State Analysis

From codebase examination:

**Working:**
- Text file generation with departure data
- Font selection (Lekton, Sui Generis, Hack)
- Color scheme defined in constants.py
- Subprocess spawning architecture
- Column alignment via monospace fonts

**Broken:**
- Color scheme not passed correctly to subprocess (regression from refactor)
- No change detection (generates every refresh)
- File size not monitored
- No validation of output quality

**Unknown:**
- Actual file sizes generated
- Anti-aliasing configuration
- @2x support
- Mobile readability

### Technical Constraints

**Subprocess isolation:** Must continue using subprocess to avoid PIL/Indigo library conflicts. This means:
- All configuration must be serialized to files (parameters file)
- No shared memory between Indigo process and image generator
- Error handling via log files only

**PIL/Pillow capabilities:**
- Supports RGBA PNG with transparency
- Built-in zlib compression
- TrueType font rendering with anti-aliasing
- No built-in retina support (must generate larger dimensions manually)

**Platform limits:**
- Pushover: 2.5MB hard limit (service rejects larger)
- iOS memory: Loading 2160px images inefficient; prefer 1440px or lower
- Indigo control pages: No documented limit but slow loading >1MB

### Validation Checklist

Before declaring fix complete:

- [ ] PNG files generate successfully
- [ ] Color scheme applied correctly (green on black, red for delays)
- [ ] Text readable at 320px viewport width
- [ ] File size logged and <500KB for typical 5-train board
- [ ] @2x generation (1440px width) tested
- [ ] Pushover notification displays correctly
- [ ] iOS app loads image without memory issues
- [ ] Only generates when data changes (not every refresh)

## Sources

**Based on:**
- Codebase analysis (image_generator.py, text2png.py, constants.py)
- Domain knowledge of UK departure board standards (National Rail, TfL)
- PNG format specifications (W3C, ISO/IEC 15948)
- Pushover API documentation (file size limits, supported formats)
- iOS Human Interface Guidelines (image assets, @2x/@3x requirements)
- WCAG 2.1 contrast requirements for text readability
- PIL/Pillow documentation (Image.new, ImageDraw, ImageFont)

**Confidence levels:**
- Table stakes features: HIGH (established departure board conventions)
- PNG technical requirements: HIGH (documented specifications)
- Pushover limits: MEDIUM (based on typical API documentation patterns; verify actual limit)
- iOS requirements: HIGH (Apple HIG standard)
- File size estimates: LOW (need actual generation testing)
- Current rendering quality: LOW (need visual inspection of output)

**Verification needed:**
- Actual Pushover file size limit (verify 2.5MB via official docs)
- Current anti-aliasing settings in text2png.py
- Actual file sizes generated for 1/3/5/10 train boards
- Mobile readability testing at 320px viewport
