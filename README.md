# UK Trains Plugin for Indigo

Real-time UK train departure information integrated with the Indigo home automation system.

## Overview

The UK Trains plugin connects your Indigo home automation system to the UK National Rail Darwin Live Departure Boards API, providing real-time train departure information for any UK railway station. Display departure boards, track delays, and integrate train schedules into your home automation workflows.

**Originally based on Chameleon's iTravel plugin, fully rewritten and modernized for macOS Monterey+, Python 3, and Indigo 2023+.**

## Features

- **Real-time departure information** from any UK railway station
- **Automatic updates** at configurable intervals (30-600 seconds)
- **Visual departure boards** with customizable colors and fonts
- **Delay tracking** with problem flags for delayed, early, or cancelled trains
- **Route filtering** - show only trains to specific destinations
- **Calling points** - display intermediate stops for each service
- **Special messages** from National Rail (service disruptions, engineering works)
- **Multiple devices** - track different stations or routes simultaneously
- **Device states** - use train data in triggers, actions, and control pages

## Requirements

- **Indigo 2023.2 or later** (macOS)
- **Python 3.10+** (included with Indigo 2023+)
- **Darwin API Key** (free registration at [National Rail Developers Portal](https://www.nationalrail.co.uk/developers/))

## Installation

1. **Download the plugin** from the GitHub releases page
2. **Double-click** the `.indigoPlugin` file to install
3. **Indigo will prompt** to enable the plugin
4. **Enter your Darwin API key** in the plugin configuration

### Getting a Darwin API Key

1. Visit [https://www.nationalrail.co.uk/developers/](https://www.nationalrail.co.uk/developers/)
2. Click "Register" and create an account
3. Log in and navigate to "My Account" → "API Keys"
4. Request a new API key for "Darwin LDB (Live Departure Boards)"
5. Copy the key and paste it into the plugin configuration

## Configuration

### Plugin Settings

Open **Plugins → UK Trains → Configure** to set global options:

- **Darwin API Key** - Your API key from National Rail
- **Darwin WSDL URL** - Leave as default unless using a different endpoint
- **Update Frequency** - How often to refresh data (30-600 seconds, default: 60)
- **Create Departure Images** - Generate PNG images of departure boards
- **Image Output Directory** - Where to save departure board images
- **Colors** - Customize foreground, background, delay, and calling point colors

### Creating a Station Device

1. **Plugins → UK Trains → Create New Device**
2. Select **"UK Train Departure Board"**
3. Configure the device:
   - **Station CRS Code** - 3-letter code for departure station (e.g., PAD for Paddington)
   - **Destination CRS Code** - Filter to only trains going to this station (or "ALL" for all departures)
   - **Include Calling Points** - Show intermediate stops for each train
   - **Create Station Board Images** - Generate visual departure board for this device

### Finding Station Codes

Station codes (CRS codes) are 3-letter codes used by National Rail:

- **Paddington**: PAD
- **King's Cross**: KGX
- **Waterloo**: WAT
- **Victoria**: VIC
- **Liverpool Street**: LST

Full list available at: [https://www.nationalrail.co.uk/stations_destinations/48541.aspx](https://www.nationalrail.co.uk/stations_destinations/48541.aspx)

## Usage

### Device States

Each device tracks up to 10 trains with the following states:

**Per Train (train1-train10)**:
- `trainXDestination` - Final destination
- `trainXOperator` - Train operating company
- `trainXSch` - Scheduled departure time
- `trainXEst` - Estimated departure time
- `trainXDelay` - Delay message ("On Time", "5 mins late", "Cancelled", etc.)
- `trainXProblem` - Boolean flag (True if delayed, early, or cancelled)
- `trainXReason` - Delay reason if provided
- `trainXCalling` - Intermediate calling points (if enabled)

**Station Information**:
- `stationLong` - Full station name
- `stationIssues` - Boolean flag (True if any train has problems)
- `timeGenerated` - Last update timestamp
- `message1` - NRCC special messages (disruptions, engineering works)

### Example Triggers

**Alert on delays at my station**:
```
Trigger: Device State Changed
Device: London Paddington to Bristol
State: stationIssues becomes True
Action: Send notification "Train delays at Paddington"
```

**Announce next train 10 minutes before departure**:
```
Trigger: Schedule
Time: Daily at 08:20 (if you leave at 08:30)
Condition: Device State "train1Problem" is False
Action: Speak "Your 08:30 train to Bristol is on time"
```

**Flash lights if train is cancelled**:
```
Trigger: Device State Changed
Device: My Commute
State: train1Delay contains "Cancelled"
Action: Flash office lights red
```

### Example Control Pages

Add departure board to your control page:

1. Create a **Status Display** element
2. Link to device state: `train1Destination`
3. Add multiple status displays for different trains
4. Use `trainXProblem` state to change color (red for problems)

### Departure Board Images

If enabled, the plugin generates PNG images showing departure boards:

**Location**: `~/Documents/IndigoImages/` (or configured path)
**Format**: `{StationCRS}_{DestinationCRS}.png`
**Example**: `PAD_BRI.png` (Paddington to Bristol)

Display on iPads, dashboards, or control pages using Indigo's control page image feature.

## Troubleshooting

### Plugin won't start

- Check **Indigo → Event Log** for error messages
- Verify Darwin API key is valid (test at [Darwin API Documentation](https://lite.realtime.nationalrail.co.uk/OpenLDBWS/))
- Ensure Indigo 2023.2+ is installed

### No train data showing

- Verify station CRS codes are correct (3 letters, uppercase)
- Check if station has services at current time (some stations have limited hours)
- Look for error messages in Indigo Event Log
- Test API key at National Rail developer portal

### Delays showing incorrectly

- Check that device update frequency isn't too high (minimum 30 seconds recommended)
- API may have temporary issues - check [National Rail Twitter](https://twitter.com/nationalrailenq)
- Verify timezone on Mac is set correctly (BST/GMT matters for schedule calculations)

### Image generation failing

- Check image output directory exists and is writable
- Ensure font files are present in plugin bundle
- Check plugin log: `~/Library/Application Support/Perceptive Automation/Indigo [version]/Logs/`

### Common API Errors

- **"Invalid API Key"** - Check key is copied correctly, no extra spaces
- **"Station not found"** - Verify CRS code is valid
- **"Too many requests"** - Reduce update frequency or check if multiple devices are polling same endpoint

## Advanced Usage

### Multiple Routes from Same Station

Create multiple devices for the same departure station with different destination filters:

- **Device 1**: Paddington → Bristol (only Bristol trains)
- **Device 2**: Paddington → Oxford (only Oxford trains)
- **Device 3**: Paddington → ALL (all departures)

### Integration with Schedules

Use time-based triggers to:
- Enable departure board display only during commute hours
- Change update frequency (faster during peak times)
- Announce specific trains at specific times

### Using with Control Pages

1. Create custom control page with departure information
2. Use device states in substitution variables
3. Add images to show full departure board
4. Use conditional formatting based on `trainXProblem` states

## Development

For developers and contributors:

- **Repository**: [GitHub - simons-plugins/indigo-UKTrains](https://github.com/simons-plugins/indigo-UKTrains)
- **Bug Reports**: [GitHub Issues](https://github.com/simons-plugins/indigo-UKTrains/issues)
- **Documentation**: See `CLAUDE.md` for development setup
- **Tests**: Comprehensive test suite with 58 unit tests and 14 live API tests

### Running Tests

```bash
cd UK-Trains/tests
pytest unit/ -v                    # Unit tests
pytest integration/ -v             # Integration tests (mocked)
pytest -m live_api integration/    # Live API tests (requires API key)
```

## Credits

- **Original iTravel Plugin**: Chameleon (Indigo Forums)
- **Rewrite & Modernization**: Simon (2025)
- **Darwin LDB API**: National Rail Enquiries
- **Built with**: [nredarwin](https://github.com/robert-b-clarke/nredarwin) SOAP client

## License

This plugin is provided as-is for use with Indigo home automation. Darwin API usage subject to National Rail terms of service.

## Support

- **Indigo Forums**: [Plugin Support Thread](https://forums.indigodomo.com/)
- **GitHub Issues**: [Report bugs and request features](https://github.com/simons-plugins/indigo-UKTrains/issues)
- **Darwin API Support**: [National Rail Developer Portal](https://www.nationalrail.co.uk/developers/)

---

**Version**: 3.0+ (2025)
**Minimum Indigo Version**: 2023.2
**macOS**: Monterey or later
**Python**: 3.10+
