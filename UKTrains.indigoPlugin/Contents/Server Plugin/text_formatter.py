# coding=utf-8
"""
Text formatting utilities for UK-Trains plugin

Pure functions for processing Darwin API text data.
"""
import time
import datetime
import re
from typing import Tuple

try:
	import pytz
	_MODULE_FAILPYTZ = False
except ImportError:
	pytz = None
	_MODULE_FAILPYTZ = True


def getUKTime() -> str:
	"""Get current UK time formatted as string.

	Returns:
		Formatted time string with timezone indicator (e.g., "Mon 14:30:45 UK Time")
	"""
	### Checks time generated to allow for BST
	### Note - all times are UK Time
	### Get the current time in London as a basis

	if _MODULE_FAILPYTZ:
		# Module isn't installed so we will return GMT time
		gmtTime = time.gmtime()
		return time.strftime('%a %H:%M:%S', gmtTime)+' GMT'
	else:
		timeZone = pytz.timezone('Europe/London')
		lonTime = datetime.datetime.now(timeZone)
		return lonTime.strftime('%a %H:%M:%S')+' UK Time'

def delayCalc(scheduled_time: str, estimated_time: str) -> Tuple[bool, str]:
	"""Calculate delay between scheduled and estimated times.

	Args:
		scheduled_time: Scheduled time string (HH:MM format or status)
		estimated_time: Estimated time string (HH:MM format or status like "On time")

	Returns:
		Tuple of (has_problem: bool, message: str)

	Note:
		If estimated_time > scheduled_time: train is late
		If estimated_time < scheduled_time: train is early
	"""
	# Calculates time different between two times of the form HH:MM or handles On Time, Cancelled or Delayed message
	delayMessage = ''
	trainProblem = False

	# Check if times are valid HH:MM format or special status strings
	if not scheduled_time or not estimated_time or scheduled_time[0] not in '012' or estimated_time[0] not in '012':
		# Handle null/None values safely
		if scheduled_time and 'On' in scheduled_time or estimated_time and 'On' in estimated_time:
			delayMessage = 'On time'
			trainProblem = False
		elif scheduled_time and 'CAN' in scheduled_time.upper() or estimated_time and 'CAN' in estimated_time.upper():
			delayMessage = 'Cancelled'
			trainProblem = True
		else:
			delayMessage = 'Delayed'
			trainProblem = True
	else:
		# It's a time so calculate the delay
		# Convert both to minutes
		hs, ms = [int(i) for i in scheduled_time.split(':')]
		timeValScheduled = hs * 60 + ms
		he, me = [int(i) for i in estimated_time.split(':')]
		timeValEstimated = he * 60 + me

		# Check difference: positive means late, negative means early
		delay_minutes = timeValEstimated - timeValScheduled

		if delay_minutes < 0:
			# Train is early (estimated < scheduled)
			if abs(delay_minutes) == 1:
				delayMessage = '1 min early'
			else:
				delayMessage = f'{abs(delay_minutes)} mins early'
			trainProblem = True

		elif delay_minutes > 0:
			# Train is late (estimated > scheduled)
			if delay_minutes == 1:
				delayMessage = '1 min late'
			else:
				delayMessage = f'{delay_minutes} mins late'
			trainProblem = True
		else:
			# On time (estimated == scheduled)
			delayMessage = 'On Time'
			trainProblem = False

	return trainProblem, delayMessage

def formatSpecials(longMessage: str) -> str:
	"""Format long special messages into readable format.

	Removes HTML tags, limits line length, and wraps to maximum 2 lines.

	Args:
		longMessage: Raw message string (may contain HTML)

	Returns:
		Formatted message string with line breaks
	"""
	# Formats long messages into a readable format.  Maximum will be two lines in small font

	# Is the message blank?
	if len(longMessage.strip()) == 0:
		# Just return the message untouched
		return longMessage

	# Maximum line length
	maxLength = 130
	maxLines = 2

	# Remove HTML tags and special entities using regex
	html_pattern = re.compile(r'<[^>]+>')
	entity_pattern = re.compile(r'&[a-z]+;?')

	# Remove HTML tags
	longMessage = html_pattern.sub('', longMessage)
	# Remove HTML entities (e.g., &nbsp;, &amp;)
	longMessage = entity_pattern.sub(' ', longMessage)
	# Remove newlines
	longMessage = longMessage.replace('\n', '')

	# Clean up specific text patterns
	longMessage = longMessage.replace('href=', '')
	longMessage = longMessage.replace('http', '')
	longMessage = longMessage.replace('://', 'www.')
	longMessage = longMessage.replace('"', '')
	longMessage = longMessage.replace('Travel News.', '')
	longMessage = longMessage.replace('Latest', '')
	longMessage = longMessage.replace('[', '')
	longMessage = longMessage.replace(']', '')

	# Ok now break up the message if required
	returnMessage = ''
	remaining = True
	remainingMessage = longMessage
	totalLines = 0

	while remaining:
		totalLines += 1

		if len(remainingMessage.strip())>maxLength:
			# Need to split the messsage more
			# Find the next space following the maxLength
			nextPartStart = remainingMessage.find(' ',maxLength)
			returnMessage += '+++'+remainingMessage[:nextPartStart] + '\n'

			if nextPartStart != -1:
				# More to process
				remainingMessage = remainingMessage[nextPartStart+1:]
			else:
				remainingMessage = ''
				remaining = False

			if totalLines == maxLines:
				# That's all we have room for
				remaining = False
				break

		else:
			returnMessage += '+++'+remainingMessage+'\n'

			# Forget the rest of the message
			remaining = False

	# Return the multi-line string
	# Note: Debug logging removed - use plugin instance logger instead
	return returnMessage
