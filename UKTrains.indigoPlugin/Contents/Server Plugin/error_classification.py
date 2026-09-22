# coding=utf-8
"""
Failure classification for Event Log throttling (#28 review).

PluginLogger.log_failure() throttles repeated Event Log lines by comparing
a `category` string across calls for the same key: unchanged category ==
"still the same failure" (file log only), changed == "something new, tell
the user again". classify_exception() derives that category from an
exception so the file log keeps every raw message (which varies cycle to
cycle -- different byte counts, request ids, timestamps) while the Event
Log still collapses those into "the same kind of failure" -- and still
tells the difference between e.g. a network outage and a 401, even though
nredarwin/webservice.py raises the same WebServiceError type for nearly
everything.
"""
import re

# nredarwin/webservice.py folds the HTTP status into the message text
# (`f'Darwin REST {e.code} {e.reason}: {detail}'`) rather than exposing it
# as a structured attribute, so pull it back out here.
_HTTP_STATUS_RE = re.compile(r'\bDarwin REST (\d{3})\b')

# Long hex-looking runs (request ids, etc.) before the plain digit pass,
# so e.g. "abcdef1234567890" collapses the same as "1234567890abcdef".
_HEX_ID_RE = re.compile(r'[0-9a-fA-F]{8,}')
_DIGITS_RE = re.compile(r'\d+')


def classify_exception(e: BaseException) -> str:
	"""Return a stable category string for an exception, for use as the
	`category` argument to PluginLogger.log_failure()/log_failure_quiet().

	Prefers the HTTP status code when the message carries one (a network
	outage and a 401 must not share a throttle bucket just because both
	raise WebServiceError). Otherwise falls back to the exception type
	plus its message with digits and hex-like ids normalised out, so the
	same underlying failure recurring with different specifics (byte
	counts, timestamps, request ids) still collapses to one category.
	"""
	message = str(e)

	status_match = _HTTP_STATUS_RE.search(message)
	if status_match:
		return f"http_{status_match.group(1)}"

	normalised = _HEX_ID_RE.sub('X', message)
	normalised = _DIGITS_RE.sub('N', normalised)
	return f"{type(e).__name__}:{normalised}"
