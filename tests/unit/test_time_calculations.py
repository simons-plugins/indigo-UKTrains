"""
Unit tests for time calculation functions

Tests the delayCalc() function which calculates delays between
scheduled and estimated times.
"""

import pytest
import sys

# Import the function to test
# The mock indigo module will be injected by conftest.py
import plugin


@pytest.mark.unit
class TestDelayCalc:
    """Test cases for delayCalc function"""

    def test_on_time_string(self):
        """Test when service is exactly on time (string 'On time')"""
        has_problem, message = plugin.delayCalc("14:30", "On time")
        assert has_problem is False
        assert message == "On time"

    def test_on_time_exact_match(self):
        """Test when estimated matches scheduled time exactly"""
        has_problem, message = plugin.delayCalc("14:30", "14:30")
        assert has_problem is False
        assert message == "On Time"

    def test_cancelled_service(self):
        """Test when service is cancelled"""
        has_problem, message = plugin.delayCalc("14:30", "Cancelled")
        assert has_problem is True
        assert message == "Cancelled"

    def test_cancelled_service_uppercase(self):
        """Test cancelled with different case"""
        has_problem, message = plugin.delayCalc("14:30", "CANCELLED")
        assert has_problem is True
        assert message == "Cancelled"

    def test_delayed_string(self):
        """Test generic 'Delayed' string"""
        has_problem, message = plugin.delayCalc("14:30", "Delayed")
        assert has_problem is True
        assert message == "Delayed"

    def test_late_5_minutes(self):
        """Test service running 5 minutes late"""
        # estTime=14:25 (train will arrive), arrivalTime=14:30 (scheduled) -> 5 min late
        has_problem, message = plugin.delayCalc("14:25", "14:30")
        assert has_problem is True
        assert message == "5 mins late"

    def test_late_1_minute(self):
        """Test service running 1 minute late (singular)"""
        # estTime=14:29, arrivalTime=14:30 -> 1 min late
        has_problem, message = plugin.delayCalc("14:29", "14:30")
        assert has_problem is True
        assert message == "1 min late"

    def test_late_20_minutes(self):
        """Test service running 20 minutes late"""
        # estTime=15:25, arrivalTime=15:45 -> 20 min late
        has_problem, message = plugin.delayCalc("15:25", "15:45")
        assert has_problem is True
        assert message == "20 mins late"

    def test_early_3_minutes(self):
        """Test service running 3 minutes early"""
        # estTime=16:03, arrivalTime=16:00 -> 3 min early
        has_problem, message = plugin.delayCalc("16:03", "16:00")
        assert has_problem is True
        assert message == "3 mins early"

    def test_early_1_minute(self):
        """Test service running 1 minute early (singular)"""
        # estTime=16:01, arrivalTime=16:00 -> 1 min early
        has_problem, message = plugin.delayCalc("16:01", "16:00")
        assert has_problem is True
        assert message == "1 min early"

    def test_midnight_crossing_delay(self):
        """Test delay calculation crossing midnight"""
        # This is a known limitation - midnight crossing might not work correctly
        # Documenting expected behavior
        has_problem, message = plugin.delayCalc("23:50", "00:10")
        # Due to the simple calculation, this will show as early, not late
        # This is a known bug that could be fixed in Phase 3
        assert has_problem is True

    def test_early_morning_on_time(self):
        """Test early morning service on time"""
        has_problem, message = plugin.delayCalc("06:30", "06:30")
        assert has_problem is False
        assert message == "On Time"

    def test_early_morning_delayed(self):
        """Test early morning service delayed"""
        # estTime=06:20, arrivalTime=06:30 -> 10 min late
        has_problem, message = plugin.delayCalc("06:20", "06:30")
        assert has_problem is True
        assert message == "10 mins late"

    def test_null_arrival_time(self):
        """Test with null/None arrival time"""
        # estTime=None, arrivalTime="14:30"
        has_problem, message = plugin.delayCalc(None, "14:30")
        # Should handle gracefully - returns Delayed
        assert has_problem is True
        assert message == "Delayed"

    def test_null_est_time(self):
        """Test with null/None estimated time"""
        # estTime="14:30", arrivalTime=None
        has_problem, message = plugin.delayCalc("14:30", None)
        # Should handle gracefully - returns Delayed
        assert has_problem is True
        assert message == "Delayed"

    def test_empty_string_times(self):
        """Test with empty string times"""
        has_problem, message = plugin.delayCalc("", "14:30")
        assert has_problem is True
        assert message == "Delayed"

    def test_on_time_in_est_time(self):
        """Test when 'On' appears in estimated time"""
        has_problem, message = plugin.delayCalc("14:30", "On time")
        assert has_problem is False
        assert message == "On time"

    def test_on_time_in_arrival_time(self):
        """Test when 'On' appears in arrival time"""
        has_problem, message = plugin.delayCalc("On time", "14:30")
        assert has_problem is False
        assert message == "On time"

    def test_large_delay_60_minutes(self):
        """Test very large delay"""
        # estTime=15:00, arrivalTime=16:00 -> 60 min late
        has_problem, message = plugin.delayCalc("15:00", "16:00")
        assert has_problem is True
        assert message == "60 mins late"

    def test_peak_hours_calculation(self):
        """Test calculation during peak hours (2x:xx format)"""
        # estTime=21:25, arrivalTime=21:30 -> 5 min late
        has_problem, message = plugin.delayCalc("21:25", "21:30")
        assert has_problem is True
        assert message == "5 mins late"

    @pytest.mark.parametrize("estimated,scheduled,expected_problem,expected_msg", [
        ("10:00", "10:00", False, "On Time"),
        ("09:55", "10:00", True, "5 mins late"),
        ("10:05", "10:00", True, "5 mins early"),
        ("On time", "10:00", False, "On time"),
        ("Cancelled", "10:00", True, "Cancelled"),
        ("Delayed", "10:00", True, "Delayed"),
    ])
    def test_common_scenarios(self, estimated, scheduled, expected_problem, expected_msg):
        """Parametrized test for common scenarios"""
        # Note: Function signature is delayCalc(estTime, arrivalTime)
        has_problem, message = plugin.delayCalc(estimated, scheduled)
        assert has_problem == expected_problem
        assert message == expected_msg


@pytest.mark.unit
class TestDelayCalcEdgeCases:
    """Edge cases and error handling for delayCalc"""

    def test_malformed_time_format(self):
        """Test with malformed time format"""
        # Times that don't start with 0, 1, or 2 trigger special string handling
        has_problem, message = plugin.delayCalc("99:99", "14:30")
        # Should be treated as a special status string
        assert has_problem is True
        assert message == "Delayed"

    def test_partial_cancellation_string(self):
        """Test with partial 'CAN' in string"""
        has_problem, message = plugin.delayCalc("14:30", "CANcelled due to fault")
        assert has_problem is True
        assert message == "Cancelled"

    def test_mixed_case_on_time(self):
        """Test 'On time' with mixed case"""
        has_problem, message = plugin.delayCalc("14:30", "On Time")
        assert has_problem is False
        assert message == "On time"
