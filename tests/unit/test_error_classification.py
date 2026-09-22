"""
Unit tests for error_classification.classify_exception() (GitHub issue #28
review).

PluginLogger.log_failure()'s throttle decision is keyed on `category`:
unchanged == still the same failure (file log only), changed == tell the
user again. Before this, routeUpdate keyed Darwin failures on
`type(e).__name__` alone -- and nredarwin/webservice.py raises
WebServiceError for nearly everything (network outage, HTTP errors,
malformed JSON), so a genuine change in failure (e.g. a network outage
turning into a 401 Unauthorized) was silently suppressed as "the same
failure".
"""

import pytest

from error_classification import classify_exception
from nredarwin.webservice import WebServiceError


@pytest.mark.unit
class TestHttpStatusClassification:
    def test_http_status_code_is_the_category(self):
        e = WebServiceError('Darwin REST 401 Unauthorized: {"error":"invalid key"}')
        assert classify_exception(e) == "http_401"

    def test_different_http_status_codes_are_different_categories(self):
        e_401 = WebServiceError("Darwin REST 401 Unauthorized: nope")
        e_503 = WebServiceError("Darwin REST 503 Service Unavailable: retry later")
        assert classify_exception(e_401) != classify_exception(e_503)

    def test_same_status_code_with_varying_detail_is_one_category(self):
        e1 = WebServiceError("Darwin REST 401 Unauthorized: request id abc123")
        e2 = WebServiceError("Darwin REST 401 Unauthorized: request id def456")
        assert classify_exception(e1) == classify_exception(e2)

    def test_network_error_and_http_error_are_different_categories(self):
        """The exact reproduction from the review: a network outage and a
        401 both raise WebServiceError, but must not throttle each other."""
        network = WebServiceError(
            "Darwin REST network error: [Errno 8] nodename nor servname "
            "provided, or not known"
        )
        http = WebServiceError("Darwin REST 401 Unauthorized: nope")
        assert classify_exception(network) != classify_exception(http)


@pytest.mark.unit
class TestGenericExceptionClassification:
    def test_message_with_varying_numbers_is_one_category(self):
        e1 = WebServiceError("Darwin REST network error: timed out after 30s (attempt 1)")
        e2 = WebServiceError("Darwin REST network error: timed out after 45s (attempt 7)")
        assert classify_exception(e1) == classify_exception(e2)

    def test_different_exception_types_are_different_categories(self):
        assert classify_exception(ValueError("bad json")) != classify_exception(TypeError("bad json"))

    def test_message_is_normalised_across_digits(self):
        e1 = OSError("disk full: wrote 1024 of 4096 bytes")
        e2 = OSError("disk full: wrote 2048 of 8192 bytes")
        assert classify_exception(e1) == classify_exception(e2)

    def test_different_message_is_a_different_category(self):
        e1 = OSError("disk full")
        e2 = OSError("permission denied")
        assert classify_exception(e1) != classify_exception(e2)

    def test_hex_like_ids_are_normalised(self):
        e1 = RuntimeError("request abcdef1234567890 failed")
        e2 = RuntimeError("request 1234567890abcdef failed")
        assert classify_exception(e1) == classify_exception(e2)
