"""
Modern mobile-optimized departure board renderer for UK-Trains plugin

This module generates portrait-orientation PNG images optimized for mobile
messaging apps (WhatsApp, iMessage) using a contemporary card-based design.

Design Specifications:
    - Dimensions: 414×variable portrait (iPhone compatible)
    - Color scheme: Modern dark theme with WCAG AA contrast
    - Typography: Hack font family (monospace)
    - Layout: Card-based with rounded corners and proper spacing

Exit codes:
    0 = Success
    1 = File I/O error
    2 = PIL/Pillow error
    3 = Configuration error

Author: Claude Code
Version: 1.0
Created: 2026-02-04
"""

import sys
import os
from typing import List, Dict, Tuple
from PIL import Image, ImageDraw, ImageFont


# Modern design constants (matches constants.py specification)
IMAGE_WIDTH = 414
CARD_HEIGHT = 150  # Reference only - actual card height is calculated dynamically
CARD_SPACING = 12
MARGIN = 20
CARD_PADDING = 16
BORDER_RADIUS = 8
HEADER_HEIGHT = 80
FOOTER_HEIGHT = 60

# Color scheme (WCAG AA compliant)
COLORS = {
    'background': '#1A1D29',
    'card_surface': '#252938',
    'primary_text': '#FFFFFF',
    'secondary_text': '#A0A4B8',
    'station_name': '#64B5F6',
    'on_time': '#00C853',
    'delayed': '#FF6B00',
    'cancelled': '#F44336',
    'early': '#2196F3',
    'platform': '#FFC107',
    'operator': '#9E9E9E',
    'separator': '#3A3F52'
}

# Font sizes
FONT_SIZES = {
    'station': 26,
    'destination': 18,
    'platform': 20,
    'time': 16,
    'status': 14,
    'operator': 12,
    'timestamp': 12,
    'calling_points': 11
}

# Safety limits
MAX_IMAGE_HEIGHT = 10000  # 10k pixels = ~8MB uncompressed
MAX_SERVICES = 5


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB tuple.

    Args:
        hex_color: Hex color string (e.g., '#1A1D29' or '1A1D29')

    Returns:
        RGB tuple (r, g, b)

    Raises:
        ValueError: If hex_color is not a valid 6-character hex color
        TypeError: If hex_color is not a string
    """
    if not isinstance(hex_color, str):
        raise TypeError(f"hex_color must be string, got {type(hex_color).__name__}: {hex_color}")

    # Remove leading # if present
    hex_color = hex_color.lstrip('#')

    # Validate length
    if len(hex_color) != 6:
        raise ValueError(f"hex_color must be 6 characters (got {len(hex_color)}): '{hex_color}'")

    # Convert with better error message
    try:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except ValueError as e:
        raise ValueError(f"Invalid hex color '{hex_color}': {e}") from e


def load_fonts(pypath: str) -> Dict[str, ImageFont.FreeTypeFont]:
    """Load Hack font family at appropriate sizes.

    Args:
        pypath: Base path to plugin directory

    Returns:
        Dictionary mapping font names to ImageFont objects
    """
    fonts = {}
    font_base = os.path.join(pypath, 'BoardFonts/MFonts/')

    try:
        fonts['station'] = ImageFont.truetype(
            os.path.join(font_base, 'Hack-Bold.ttf'),
            FONT_SIZES['station']
        )
        fonts['destination'] = ImageFont.truetype(
            os.path.join(font_base, 'Hack-Bold.ttf'),
            FONT_SIZES['destination']
        )
        fonts['platform'] = ImageFont.truetype(
            os.path.join(font_base, 'Hack-Bold.ttf'),
            FONT_SIZES['platform']
        )
        fonts['time'] = ImageFont.truetype(
            os.path.join(font_base, 'Hack-Regular.ttf'),
            FONT_SIZES['time']
        )
        fonts['status'] = ImageFont.truetype(
            os.path.join(font_base, 'Hack-Bold.ttf'),
            FONT_SIZES['status']
        )
        fonts['operator'] = ImageFont.truetype(
            os.path.join(font_base, 'Hack-Regular.ttf'),
            FONT_SIZES['operator']
        )
        fonts['timestamp'] = ImageFont.truetype(
            os.path.join(font_base, 'Hack-Regular.ttf'),
            FONT_SIZES['timestamp']
        )
        fonts['calling_points'] = ImageFont.truetype(
            os.path.join(font_base, 'Hack-RegularOblique.ttf'),
            FONT_SIZES['calling_points']
        )
    except OSError as e:
        print(f"Error loading fonts: {e}", file=sys.stderr)
        raise

    return fonts


def draw_rounded_rectangle(
    draw: ImageDraw.ImageDraw,
    bbox: Tuple[int, int, int, int],
    radius: int,
    fill: Tuple[int, int, int]
) -> None:
    """Draw a rounded rectangle.

    Args:
        draw: PIL ImageDraw object
        bbox: Bounding box (x1, y1, x2, y2)
        radius: Corner radius in pixels
        fill: RGB color tuple
    """
    x1, y1, x2, y2 = bbox

    # Draw main rectangles
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)

    # Draw corners
    draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
    draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
    draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
    draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)


def draw_status_indicator(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    status_text: str,
    font: ImageFont.FreeTypeFont
) -> None:
    """Draw colored circle + status text.

    Args:
        draw: PIL ImageDraw object
        x: X position
        y: Y position (top of text baseline)
        status_text: Status string (e.g., "On time", "5 mins late")
        font: Font for status text
    """
    # Determine status color
    status_lower = status_text.lower()
    if 'on time' in status_lower:
        color = hex_to_rgb(COLORS['on_time'])
    elif 'cancel' in status_lower:
        color = hex_to_rgb(COLORS['cancelled'])
    elif 'late' in status_lower or 'delay' in status_lower:
        color = hex_to_rgb(COLORS['delayed'])
    elif 'early' in status_lower:
        color = hex_to_rgb(COLORS['early'])
    else:
        color = hex_to_rgb(COLORS['secondary_text'])

    # Draw circle (12px diameter)
    circle_size = 12
    circle_y = y + (FONT_SIZES['status'] - circle_size) // 2
    draw.ellipse(
        [x, circle_y, x + circle_size, circle_y + circle_size],
        fill=color
    )

    # Draw status text
    text_x = x + circle_size + 8
    draw.text((text_x, y), status_text, fill=color, font=font)


def render_header(
    draw: ImageDraw.ImageDraw,
    y_offset: int,
    station_title: str,
    departures_line: str,
    timestamp: str,
    fonts: Dict[str, ImageFont.FreeTypeFont]
) -> int:
    """Render station name and timestamp header section.

    Args:
        draw: PIL ImageDraw object
        y_offset: Starting Y position
        station_title: Station route string (e.g., "WAL to WAT")
        departures_line: Full departures line with station names
        timestamp: Generation timestamp string
        fonts: Dictionary of loaded fonts

    Returns:
        Y position after header
    """
    y = y_offset

    # Parse full station names from departures line
    # Format: "Departures - Walton-on-Thames (via:London Waterloo)"
    # or: "Departures - Walton-on-Thames (via:London Waterloo" (incomplete closing paren)
    # or: "Departures - London Waterloo"
    if 'Departures - ' in departures_line:
        station_names = departures_line.split('Departures - ')[1].strip()

        # Remove "(via:" prefix and trailing ")" to produce clean "FROM to TO" format
        if '(via:' in station_names:
            parts = station_names.split('(via:')
            from_station = parts[0].strip()
            to_station = parts[1].rstrip(')').strip() if len(parts) > 1 else ""
            if to_station:
                title = f"{from_station} to {to_station}"
            else:
                title = from_station
        else:
            # No via, just station name
            title = station_names
    else:
        # Fallback to CRS codes
        parts = station_title.split(' to ')
        if len(parts) == 2:
            title = f"{parts[0]} to {parts[1]}"
        else:
            title = station_title

    # Wrap title if too long (max 2 lines)
    max_width = IMAGE_WIDTH - 2 * MARGIN
    title_lines = []

    # Try to fit on one line first
    bbox = draw.textbbox((0, 0), title, font=fonts['station'])
    if bbox[2] - bbox[0] <= max_width:
        title_lines = [title]
    else:
        # Wrap at "to" if present
        if ' to ' in title:
            parts = title.split(' to ')
            title_lines = [parts[0], f"to {parts[1]}"]
        else:
            # Word wrap
            words = title.split()
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                bbox = draw.textbbox((0, 0), test_line, font=fonts['station'])
                if bbox[2] - bbox[0] <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        title_lines.append(current_line)
                    current_line = word
            if current_line:
                title_lines.append(current_line)

    # Draw station name line(s) in large bold
    for line in title_lines[:2]:  # Max 2 lines
        draw.text(
            (MARGIN, y),
            line,
            fill=hex_to_rgb(COLORS['station_name']),
            font=fonts['station']
        )
        y += FONT_SIZES['station'] + 4

    y += 4  # Extra spacing after station name

    # Draw "Departures" subtitle
    draw.text(
        (MARGIN, y),
        "Departures",
        fill=hex_to_rgb(COLORS['primary_text']),
        font=fonts['status']
    )
    y += FONT_SIZES['status'] + 6

    # Draw timestamp
    draw.text(
        (MARGIN, y),
        timestamp,
        fill=hex_to_rgb(COLORS['secondary_text']),
        font=fonts['timestamp']
    )
    y += FONT_SIZES['timestamp'] + 24  # Extra spacing before cards

    return y


def parse_service_data(lines: List[str]) -> List[Dict]:
    """Parse text lines into service dictionaries.

    Text format uses dashes as field separators:
    "London Waterloo------- 17:09-----On time---South Western Railway"

    Args:
        lines: Raw text lines from departure board

    Returns:
        List of service dictionaries with parsed data

    Side effects:
        Prints warnings to stderr for malformed lines
    """
    import re

    services = []
    current_service = None
    skipped_lines = 0
    malformed_services = []

    for line_num, line in enumerate(lines, start=1):
        line_stripped = line.strip()
        if not line_stripped or 'Destination' in line_stripped:
            continue

        # Service line (contains multiple dashes as separators)
        # Format: "Destination---Platform---Time-----Status---Operator" (5 parts)
        # Legacy: "Destination-------Time-----Status---Operator" (4 parts)
        if '---' in line_stripped and 'Status:' not in line_stripped and '>>>' not in line_stripped:
            # Split on 3+ consecutive dashes
            parts = re.split(r'-{3,}', line_stripped)
            # Remove empty parts and strip whitespace
            parts = [p.strip() for p in parts if p.strip()]

            if len(parts) >= 5:
                # New format with platform
                current_service = {
                    'destination': parts[0],
                    'platform': parts[1],
                    'scheduled': parts[2],
                    'estimated': parts[3],
                    'operator': parts[4],
                    'status': parts[3],  # Estimated time or status
                    'calling_points': ''
                }
                services.append(current_service)
            elif len(parts) >= 4:
                # Legacy format without platform (backwards compatibility)
                current_service = {
                    'destination': parts[0],
                    'platform': '',
                    'scheduled': parts[1],
                    'estimated': parts[2],
                    'operator': parts[3],
                    'status': parts[2],  # Estimated time or status
                    'calling_points': ''
                }
                services.append(current_service)
            elif len(parts) == 3:
                # Likely a cancelled/delayed train where status merged with operator
                # e.g. "Cancelled-South Western Railway" (only 1-2 dashes between them)
                # Try to split the last field on known status words
                last_field = parts[2]
                status_match = re.match(
                    r'^(Cancelled|Delayed|On time|Bus)\s*-\s*(.*)',
                    last_field, re.IGNORECASE
                )
                if status_match:
                    current_service = {
                        'destination': parts[0],
                        'platform': '',
                        'scheduled': parts[1],
                        'estimated': status_match.group(1),
                        'operator': status_match.group(2) or 'Unknown',
                        'status': status_match.group(1),
                        'calling_points': ''
                    }
                    services.append(current_service)
                else:
                    # Genuinely malformed
                    malformed_services.append((line_num, line_stripped, len(parts)))
                    skipped_lines += 1
                    print(f"WARNING: Skipping malformed service line {line_num}: {line_stripped[:80]}", file=sys.stderr)
                    print(f"  Expected 4-5 fields, found {len(parts)}", file=sys.stderr)
                    current_service = None
            else:
                # MALFORMED LINE - log warning
                malformed_services.append((line_num, line_stripped, len(parts)))
                skipped_lines += 1
                print(f"WARNING: Skipping malformed service line {line_num}: {line_stripped[:80]}", file=sys.stderr)
                print(f"  Expected 4-5 fields, found {len(parts)}", file=sys.stderr)
                current_service = None  # Don't attach calling points to malformed service

        # Status line (explicit status after the main line)
        elif 'Status:' in line_stripped and current_service:
            status_text = line_stripped.replace('Status:', '').strip()
            current_service['status'] = status_text

        # Calling points line (contains '>>>')
        elif '>>>' in line_stripped and current_service:
            calling_points = line_stripped.replace('>', '').strip()
            # Append to existing calling points (might be multi-line)
            if current_service['calling_points']:
                current_service['calling_points'] += ' ' + calling_points
            else:
                current_service['calling_points'] = calling_points
        elif '>>>' in line_stripped and not current_service:
            # Orphaned calling points
            skipped_lines += 1
            print(f"WARNING: Orphaned calling points line {line_num} (no associated service)", file=sys.stderr)

    # Summary report
    if skipped_lines > 0:
        print(f"PARSING SUMMARY: Skipped {skipped_lines} malformed lines, parsed {len(services)} services", file=sys.stderr)

    return services


def render_service_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    service: Dict,
    fonts: Dict[str, ImageFont.FreeTypeFont]
) -> int:
    """Render a single service card with rounded corners.

    Args:
        draw: PIL ImageDraw object
        x: Left edge X position
        y: Top edge Y position
        service: Service data dictionary
        fonts: Dictionary of loaded fonts

    Returns:
        Height of the rendered card
    """
    # Pre-calculate calling point lines to determine card height
    calling_lines = []
    if service.get('calling_points'):
        calling_points = service['calling_points']
        content_width = (IMAGE_WIDTH - 2 * MARGIN - 2 * CARD_PADDING)
        max_width = content_width - 15  # Account for arrow

        # Split into stations (format: "Station1(time) Station2(time)")
        stations = []
        current_station = ""
        paren_depth = 0

        for char in calling_points:
            current_station += char
            if char == '(':
                paren_depth += 1
            elif char == ')':
                paren_depth -= 1
                if paren_depth == 0:
                    stations.append(current_station.strip())
                    current_station = ""

        if current_station.strip():
            stations.append(current_station.strip())

        # Build lines that fit within width
        current_line = ""
        for station in stations:
            test_line = f"{current_line} {station}".strip()
            bbox = draw.textbbox((0, 0), f"› {test_line}", font=fonts['calling_points'])
            if bbox[2] - bbox[0] <= max_width:
                current_line = test_line
            else:
                if current_line:
                    calling_lines.append(current_line)
                current_line = station

            if len(calling_lines) >= 2:  # Max 2 lines
                break

        if current_line and len(calling_lines) < 2:
            calling_lines.append(current_line)

    # Calculate dynamic card height based on content
    card_height = CARD_PADDING  # Top padding
    card_height += FONT_SIZES['platform'] + 6  # Platform row
    card_height += FONT_SIZES['destination'] + 6  # Destination row
    card_height += FONT_SIZES['status'] + 6  # Status row
    card_height += FONT_SIZES['operator'] + 4  # Operator row
    card_height += len(calling_lines) * (FONT_SIZES['calling_points'] + 2)  # Calling points (0-2 lines)
    card_height += CARD_PADDING  # Bottom padding

    card_x2 = x + (IMAGE_WIDTH - 2 * MARGIN)
    card_y2 = y + card_height

    # Draw card background with calculated height
    draw_rounded_rectangle(
        draw,
        (x, y, card_x2, card_y2),
        BORDER_RADIUS,
        hex_to_rgb(COLORS['card_surface'])
    )

    # Card interior positioning
    content_x = x + CARD_PADDING
    content_y = y + CARD_PADDING
    content_width = (IMAGE_WIDTH - 2 * MARGIN - 2 * CARD_PADDING)

    # Row 1: Platform (left) | Scheduled Time (right)
    row_y = content_y

    # Platform badge (if available) - left side
    if service.get('platform'):
        platform_text = f"Platform {service['platform']}"
    else:
        platform_text = "Platform TBC"

    draw.text(
        (content_x, row_y),
        platform_text,
        fill=hex_to_rgb(COLORS['platform']),
        font=fonts['platform']
    )

    # Scheduled time - right aligned
    time_text = service['scheduled']
    time_bbox = draw.textbbox((0, 0), time_text, font=fonts['time'])
    time_width = time_bbox[2] - time_bbox[0]
    time_x = card_x2 - CARD_PADDING - time_width

    draw.text(
        (time_x, row_y),
        time_text,
        fill=hex_to_rgb(COLORS['primary_text']),
        font=fonts['time']
    )

    row_y += FONT_SIZES['platform'] + 6

    # Row 2: Destination (bold, prominent)
    destination = service['destination']
    if len(destination) > 30:
        destination = destination[:27] + "..."

    draw.text(
        (content_x, row_y),
        destination,
        fill=hex_to_rgb(COLORS['primary_text']),
        font=fonts['destination']
    )

    row_y += FONT_SIZES['destination'] + 6

    # Row 3: Status (colored dot + text)
    draw_status_indicator(
        draw,
        content_x,
        row_y,
        service['status'],
        fonts['status']
    )

    row_y += FONT_SIZES['status'] + 6

    # Row 4: Operator name
    operator = service['operator']
    draw.text(
        (content_x, row_y),
        operator,
        fill=hex_to_rgb(COLORS['operator']),
        font=fonts['operator']
    )

    row_y += FONT_SIZES['operator'] + 4

    # Row 5: Calling points (italic, wrapped) - use pre-calculated lines
    if calling_lines:
        # Calculate arrow indent for continuation lines
        arrow_bbox = draw.textbbox((0, 0), "› ", font=fonts['calling_points'])
        arrow_indent = arrow_bbox[2] - arrow_bbox[0]

        # Draw calling point lines
        for idx, line in enumerate(calling_lines):
            if idx == 0:
                # First line with arrow
                draw.text(
                    (content_x, row_y),
                    f"› {line}",
                    fill=hex_to_rgb(COLORS['secondary_text']),
                    font=fonts['calling_points']
                )
            else:
                # Continuation lines - indent to align with first line text
                draw.text(
                    (content_x + arrow_indent, row_y),
                    line,
                    fill=hex_to_rgb(COLORS['secondary_text']),
                    font=fonts['calling_points']
                )
            row_y += FONT_SIZES['calling_points'] + 2

    return card_height


def render_services(
    draw: ImageDraw.ImageDraw,
    y_offset: int,
    services: List[Dict],
    fonts: Dict[str, ImageFont.FreeTypeFont]
) -> int:
    """Render all service cards.

    Args:
        draw: PIL ImageDraw object
        y_offset: Starting Y position
        services: List of service dictionaries
        fonts: Dictionary of loaded fonts

    Returns:
        Y position after all cards
    """
    y = y_offset

    for service in services[:5]:  # Maximum 5 services
        card_height = render_service_card(draw, MARGIN, y, service, fonts)
        y += card_height + CARD_SPACING

    return y


def render_footer(
    draw: ImageDraw.ImageDraw,
    y_offset: int,
    messages: str,
    fonts: Dict[str, ImageFont.FreeTypeFont]
) -> int:
    """Render station messages footer.

    Args:
        draw: PIL ImageDraw object
        y_offset: Starting Y position
        messages: Station messages text
        fonts: Dictionary of loaded fonts

    Returns:
        Y position after footer
    """
    if not messages:
        return y_offset

    y = y_offset + 12  # Extra spacing before footer

    # Draw warning icon + message
    warning_text = f"⚠️  {messages}"

    # Wrap to max 2 lines
    max_width = IMAGE_WIDTH - 2 * MARGIN
    lines = []
    words = warning_text.split()
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=fonts['timestamp'])
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

        if len(lines) >= 2:  # Max 2 lines
            break

    if current_line and len(lines) < 2:
        lines.append(current_line)

    # Draw lines
    for line in lines:
        draw.text(
            (MARGIN, y),
            line,
            fill=hex_to_rgb(COLORS['delayed']),
            font=fonts['timestamp']
        )
        y += FONT_SIZES['timestamp'] + 4

    return y + 16  # Padding at bottom


def render_no_trains_message(
    draw: ImageDraw.ImageDraw,
    y_offset: int,
    station_name: str,
    fonts: Dict[str, ImageFont.FreeTypeFont]
) -> int:
    """Render centered "no trains" message card.

    Args:
        draw: PIL ImageDraw object
        y_offset: Starting Y position
        station_name: Station name for message
        fonts: Dictionary of loaded fonts

    Returns:
        Y position after message
    """
    y = y_offset

    # Draw a single card with centered message
    card_x = MARGIN
    card_y = y
    card_x2 = IMAGE_WIDTH - MARGIN
    card_y2 = y + 150

    draw_rounded_rectangle(
        draw,
        (card_x, card_y, card_x2, card_y2),
        BORDER_RADIUS,
        hex_to_rgb(COLORS['card_surface'])
    )

    # Center text in card
    message_y = card_y + 40

    message_lines = [
        "No departures found",
        f"from {station_name}",
        "",
        "Check operator website for",
        "current schedule and issues"
    ]

    for line in message_lines:
        if line:
            bbox = draw.textbbox((0, 0), line, font=fonts['status'])
            text_width = bbox[2] - bbox[0]
            text_x = (IMAGE_WIDTH - text_width) // 2

            draw.text(
                (text_x, message_y),
                line,
                fill=hex_to_rgb(COLORS['secondary_text']),
                font=fonts['status']
            )

        message_y += FONT_SIZES['status'] + 4

    return card_y2 + MARGIN


def render_modern_board(
    station_title: str,
    timestamp: str,
    services: List[Dict],
    messages: str,
    output_path: str,
    departures_line: str = ""
) -> bool:
    """Main rendering function for modern departure board style.

    Args:
        station_title: Station route (e.g., "WAL to WAT")
        timestamp: Generation timestamp
        services: List of service dictionaries
        messages: Station messages (may be empty)
        output_path: Path to save PNG file
        departures_line: Full departures line with station names

    Returns:
        True if successful, False otherwise
    """
    try:
        # Get plugin path
        pypath = os.path.realpath(sys.path[0]) + '/'

        # Load fonts with specific error handling
        try:
            fonts = load_fonts(pypath)
        except (OSError, FileNotFoundError) as e:
            print(f"FONT ERROR: {e}", file=sys.stderr)
            print("Solution: Reinstall plugin or verify BoardFonts directory exists", file=sys.stderr)
            return False

        # Calculate and validate dimensions
        height = 120
        if services:
            max_card_height = 160
            height += len(services[:5]) * (max_card_height + CARD_SPACING)
        else:
            height += 200
        if messages:
            height += FOOTER_HEIGHT
        height += MARGIN * 2

        # Validate dimensions before creating image
        if height > MAX_IMAGE_HEIGHT:
            print(f"ERROR: Image height {height}px exceeds max {MAX_IMAGE_HEIGHT}px", file=sys.stderr)
            return False

        # Create image with PIL error handling
        try:
            img = Image.new('RGB', (IMAGE_WIDTH, height), hex_to_rgb(COLORS['background']))
            draw = ImageDraw.Draw(img)
        except (ValueError, MemoryError) as e:
            print(f"PIL ERROR: Cannot create image: {e}", file=sys.stderr)
            print(f"Dimensions: {IMAGE_WIDTH}x{height}", file=sys.stderr)
            return False

        # Render content with data error handling
        try:
            y = MARGIN
            y = render_header(draw, y, station_title, departures_line, timestamp, fonts)

            if services:
                y = render_services(draw, y, services, fonts)
            else:
                station_name = station_title.split(' to ')[0] if ' to ' in station_title else station_title
                y = render_no_trains_message(draw, y, station_name, fonts)

            if messages:
                y = render_footer(draw, y, messages, fonts)
        except (KeyError, AttributeError, IndexError) as e:
            print(f"DATA ERROR: Malformed service data: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return False

        # Crop and save with I/O error handling
        img = img.crop((0, 0, IMAGE_WIDTH, y + MARGIN))

        try:
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            img.save(output_path, 'png', optimize=True)
        except OSError as e:
            print(f"FILE ERROR: Cannot write image: {e}", file=sys.stderr)
            print(f"Output path: {output_path}", file=sys.stderr)
            return False

        return True

    except Exception as e:
        # Truly unexpected errors only
        print(f"UNEXPECTED ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return False
