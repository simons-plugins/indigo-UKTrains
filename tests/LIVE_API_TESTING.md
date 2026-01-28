# Live Darwin API Testing Guide

This guide shows you how to test the UK-Trains plugin with **real Darwin API calls** instead of mocked responses.

## Why Test with Live API?

- ✅ Verify mocks match real API behavior
- ✅ Test with actual live train data
- ✅ Discover edge cases in real responses
- ✅ Validate integration before production
- ✅ Debug issues that only appear with real data

## Prerequisites

### 1. Get a Darwin API Key

Visit: https://www.nationalrail.co.uk/developers/

1. Create an account
2. Register for OpenLDBWS (Live Departure Boards Web Service)
3. Get your API key (will look like: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

### 2. Set Environment Variable

```bash
# Option 1: Export for current session
export DARWIN_API_KEY="your_actual_key_here"

# Option 2: Add to your shell profile (~/.bashrc, ~/.zshrc)
echo 'export DARWIN_API_KEY="your_key_here"' >> ~/.zshrc
source ~/.zshrc

# Option 3: Create a .env file (don't commit this!)
echo "DARWIN_API_KEY=your_key_here" > tests/.env
```

## Running Live API Tests

### Run All Live API Tests

```bash
cd /Users/simon/vsCodeProjects/Indigo/UK-Trains/tests

# Basic run
pytest -m live_api

# With verbose output
pytest -m live_api -v

# With print statements (see API responses)
pytest -m live_api -v -s
```

### Run Specific Tests

```bash
# Single test file
pytest -m live_api integration/test_live_darwin_api.py

# Single test class
pytest -m live_api integration/test_live_darwin_api.py::TestLiveDarwinAPI

# Single test function
pytest -m live_api integration/test_live_darwin_api.py::TestLiveDarwinAPI::test_get_station_board_london_paddington -v -s
```

### Run with Different Stations

You can modify the tests to use your local stations:

```python
# Edit test_live_darwin_api.py
@pytest.mark.parametrize("crs_code,expected_name", [
    ("YOUR_LOCAL_STATION", "Expected Name"),
])
def test_your_station(self, live_darwin_session, crs_code, expected_name):
    board = live_darwin_session.get_station_board(crs_code)
    assert expected_name in board.location_name
```

## Common Station CRS Codes

| Station | CRS Code |
|---------|----------|
| London Paddington | PAD |
| London Victoria | VIC |
| London Waterloo | WAT |
| London King's Cross | KGX |
| London Liverpool Street | LST |
| Bristol Temple Meads | BRI |
| Birmingham New Street | BHM |
| Manchester Piccadilly | MAN |
| Edinburgh Waverley | EDB |
| Glasgow Central | GLC |

Full list: https://www.nationalrail.co.uk/stations_destinations/

## Example Test Session

```bash
# Set your API key
export DARWIN_API_KEY="your_key_here"

# Run live tests with output
cd /Users/simon/vsCodeProjects/Indigo/UK-Trains/tests
pytest -m live_api -v -s

# Expected output:
# ================== test session starts ===================
# platform darwin -- Python 3.11.6, pytest-7.4.3
#
# integration/test_live_darwin_api.py::TestLiveDarwinAPI::test_can_connect_to_darwin PASSED
#
# Found 15 services at London Paddington
# Sample service: Bristol Temple Meads at 14:30 (est: On time)
# integration/test_live_darwin_api.py::TestLiveDarwinAPI::test_get_station_board_london_paddington PASSED
#
# ...
# ================== 10 passed in 2.34s ====================
```

## What the Tests Check

### Connection Tests
- `test_can_connect_to_darwin` - Verifies API key works
- `test_major_london_stations` - Tests multiple stations

### Data Format Tests
- `test_get_station_board_london_paddington` - Checks station board structure
- `test_get_filtered_station_board` - Tests destination filtering
- `test_get_service_details` - Verifies calling points data

### Edge Case Tests
- `test_invalid_crs_code` - Handles bad station codes
- `test_station_with_no_services` - Works when no trains

### Mock Validation Tests
- `test_on_time_service_format` - Confirms mocks match real data
- `test_delayed_service_format` - Validates delay calculations

## Troubleshooting

### "DARWIN_API_KEY environment variable not set"

```bash
# Check if it's set
echo $DARWIN_API_KEY

# If empty, set it
export DARWIN_API_KEY="your_key_here"
```

### "Failed to create Darwin session"

- Check your API key is correct
- Verify you have internet connection
- Check Darwin service status: https://www.nationalrail.co.uk/

### "No services found"

- Tests may run late at night when few trains operate
- Try during UK business hours (9am-5pm GMT)
- Use busy stations like Paddington, Victoria

### Tests are skipped

By default, live API tests are skipped to avoid using API quota. You must explicitly run them:

```bash
# Wrong (skips live tests)
pytest

# Right (runs live tests)
pytest -m live_api
```

## Best Practices

1. **Don't commit your API key** - Never add it to git
2. **Limit test frequency** - API has usage limits
3. **Test during business hours** - More train services available
4. **Use specific stations** - Avoid random station selection
5. **Cache responses** - For repeated testing, save sample responses

## Integration with Your Workflow

### Before Deploying to Production

```bash
# Run full test suite (mocked)
pytest

# Verify with live API
pytest -m live_api

# If both pass, deploy!
```

### When Debugging Real Issues

```bash
# User reports issue with Bristol trains from Paddington
pytest -m live_api integration/test_live_darwin_api.py::TestLiveDarwinAPI::test_get_filtered_station_board -v -s

# Check actual API response format
# Modify test to match user's exact query
```

### Continuous Integration

You can add live API tests to CI/CD, but only if you:
- Store API key in CI secrets
- Run on schedule (not every commit)
- Handle failures gracefully (API might be down)

```yaml
# .github/workflows/live_api_test.yml (example)
name: Weekly Live API Check

on:
  schedule:
    - cron: '0 10 * * 1'  # Every Monday at 10am

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install -r tests/requirements-test.txt
      - run: pytest -m live_api
        env:
          DARWIN_API_KEY: ${{ secrets.DARWIN_API_KEY }}
```

## Next Steps

1. Get your Darwin API key
2. Set the environment variable
3. Run: `pytest -m live_api -v -s`
4. Watch real train data flow through your tests!
5. Modify tests to match your specific use cases

Happy testing! 🚂
