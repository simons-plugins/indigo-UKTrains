# coding=utf-8

###############################################################################################
# Plugin looks at the National rail database for a selected route and identifies the current
# schedule, issues (e.g. delays and disruption) for a designated route.  This information can
# be stored as an Indigo device.
#
# It also sets an alarm if there are any issues with trains on that route
#
# Functions are:
#   Downloads the latest live departure and arrival times for the next 60 mins
#   Calculates and displays any delays and sets a TrainDelays flag in indigo for triggering
#   Stores current values as indigo variables for display on control pages
#
# This plugin will be expanded to include other forms of transport in the coming months
#
# Credits:  1. 	National Rail/Darwin for real-time API (please read their T&C)
#			2. 	http://www.1001fonts.com/ - free royalty fonts used in the departure board display
#			3. 	Robert Clake for his excellent nredarwin github mobule that made reading SOAP responses
#				a lot simpler
#			4.	Matt and Jay for helping me sort out the complexities of subprocess shells and shared
#				libraries
#
# 			And all the ALPHA testers who helped get it running!
#
#  Version 0.3.01
#  Release: BETA Only
###############################################################################################

# Get system modules
import os, sys, time, datetime,traceback
import subprocess
from subprocess import call


try:
	import indigo, requirements
except:
	print("This programme must be run from inside indigo pro 6")
	sys.exit(0)
import logging

try:
	import pytz
except ImportError:
	pass

# Get the current python path for text files
# Set up globals
global nationalDebug,  stationDict
stationDict = {}
#todo delete below record
#errorFile = '/Library/Application Support/Perceptive Automation/Indigo 6/Logs/NationRailErrors.log'

global pypath
global failPYTZ
failPYTZ = True
nationalDebug = False # Logging enabled for testing purposes only

# Get the current python path for text files
pypath = os.path.realpath(sys.path[0])

# Now update the system path if necessary
sys.path.append(pypath)
pypath = pypath + '/'
#pypath = pypath2.replace(' ', '\ ')


# Create error log process for solution

def errorHandler(myError):
	global nationalDebug,  pypath

	if nationalDebug:
		f = open(errorFile, 'a')
		f.write('-' * 80 + '\n')
		f.write('Exception Logged:' + str(time.strftime(time.asctime())) + ' in ' + myError + ' module' + '\n\n')
		exc_type, exc_value, exc_traceback = sys.exc_info()
		traceback.print_exception(exc_type, exc_value, exc_traceback,limit=2, file=f)


# Get darwin access modules and other standard dependencies in place
try:
	import nredarwin
	if nationalDebug:
		indigo.server.log('* Darwin present *', level=logging.INFO)
except:
	indigo.server.log("** Couldn't find nredarwin - contact developer or check forums for support **", level=logging.CRITICAL)
	sys.exit(3)

try:
	import suds
	if nationalDebug:
		indigo.server.log('* Suds present *', level=logging.INFO)
except:
	indigo.server.log("** Couldn't find suds module - check forums for install process for your system **", level=logging.CRITICAL)
	sys.exit(4)

try:
	import functools
	if nationalDebug:
		indigo.server.log('* Functools present *', level=logging.INFO)
except:
	indigo.server.log("** Couldn't find functools module - check forums for install process for your system **", level=logging.CRITICAL)
	sys.exit(5)

try:
	import os, logging
	if nationalDebug:
		indigo.server.log('* Logging and OS present *', level=logging.INFO)
except:
	indigo.server.log("** Couldn't find standard os or logging modules - contact the developer for support **", level=logging.CRITICAL)
	sys.exit(6)

try:
	from nredarwin.webservice import DarwinLdbSession
	if nationalDebug:
		indigo.server.log('* Darwin LDBS session ready *', level=logging.INFO)
except:
	indigo.server.log("** Error accessing nredarwin webservice - contact developer for support **", level=logging.CRITICAL)
	sys.exit(7)

# Import timezone checker
try:
	import pytz
	failPYTZ = False
except:
	indigo.server.log('WARNING - pytz not present times will be in GMT only' , level=logging.INFO)
	failPYTZ = True
	pass

def getUKTime():
	### Checks time generated to allow for BST
	### Note - all times are UK Time
	### Get the current time in London as a basis
	global failPYTZ

	if failPYTZ:
		# Module isn't installed so we will return GMT time
		gmtTime = time.gmtime()
		return time.strftime('%a %H:%M:%S', gmtTime)+' GMT'
	else:
		timeZone = pytz.timezone('Europe/London')
		lonTime = datetime.datetime.now(timeZone)
		return lonTime.strftime('%a %H:%M:%S')+' UK Time'

def delayCalc(estTime, arrivalTime):

	global nationalDebug, pypath

	# Calculates time different between two times of the form HH:MM or handles On Time, Cancelled or Delayed message
	delayMessage = ''
	trainProblem = False

	if '012'.find(arrivalTime[0]) == -1 or '012'.find(estTime[0]) == -1:
		if arrivalTime.find('On') != -1 or estTime.find('On') != -1:
			delayMessage = 'On time'
			trainProblem = False
		elif arrivalTime.upper().find('CAN') != -1 or estTime.upper().find('CAN') != -1 :
			delayMessage = 'Cancelled'
			trainProblem = True
		else:
			delayMessage = 'Delayed'
			trainProblem = True
	else:
		# It's a time so calculate the delay
		# Convert both to seconds
		ha, ma = [int(i) for i in arrivalTime.split(':')]
		timeValArrival = ha * 60 + ma
		he, me = [int(i) for i in estTime.split(':')]
		timeValEst = he * 60 + me

		# Check difference
		if timeValEst - timeValArrival < 0:
			# Delayed (mins)
			minsDelay = int(timeValEst - timeValArrival)  # Round up
			if minsDelay == 1:
				delayMessage = str(abs(minsDelay)) + ' min late'
				trainProblem = True
			else:
				delayMessage = str(abs(minsDelay)) + ' mins late'
				trainProblem = True

		elif timeValEst - timeValArrival > 0:
			# Early (mins)
			minsDelay = int(timeValEst - timeValArrival)  # Round up
			if minsDelay == 1:
				delayMessage = str(abs(minsDelay)) + ' min early'
				trainProblem = True
			else:
				delayMessage = str(abs(minsDelay)) + ' mins early'
				trainProblem = True
		else:
			delayMessage = 'On Time'
			trainProblem = False

	return trainProblem, delayMessage

def formatSpecials(longMessage):
	# Formats long messages into a readable format.  Maximum will be two lines in small font

	# Is the message blank?
	if len(longMessage.strip()) == 0:
		# Just return the message untouched
		return longMessage

	# Maximum line length
	maxLength = 130
	maxLines = 2

	# Remove the non breaking spaces
	nonBreakingSpace = u'&nbsp'
	longMessage = longMessage.replace(nonBreakingSpace,' ')
	longMessage = longMessage.replace('\n','')

	# Look at a more generic way to do this
	longMessage = longMessage.replace('<P>','')
	longMessage = longMessage.replace('</P>','')
	longMessage = longMessage.replace('<A>','')
	longMessage = longMessage.replace('</A>','')
	longMessage = longMessage.replace('href=','')
	longMessage = longMessage.replace('http','')
	longMessage = longMessage.replace('://','www.')
	longMessage = longMessage.replace('"','')
	longMessage = longMessage.replace('Travel News.','')
	longMessage = longMessage.replace('Latest','')
	longMessage = longMessage.replace('<A ','')
	longMessage = longMessage.replace('>','')

	# Now remove the []s
	longMessage = longMessage.replace('[','')
	longMessage = longMessage.replace(']','')

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
	if nationalDebug:
		indigo.server.log('Return message = '+returnMessage)
	return returnMessage

def routeUpdate(dev, apiAccess, networkrailURL, imagePath, parametersFileName):

	global nationalDebug, pypath

	if not dev.enabled and dev.configured:
		# Device is currently disabled or new so ignore and move on
		return False

	# Login to Darwin
	accessLogin = nationalRailLogin(networkrailURL, apiAccess)
	if not accessLogin[0]:
		# Login failed so ignore and return
		return False

	darwinSession = accessLogin[1]

	# Accessed database - now update details
	# First clear all previous data
	for trainNum in range(1,11):
		trainDestination = 'train'+str(trainNum)+'Dest'
		trainSch = 'train'+str(trainNum)+'Sch'
		trainEst = 'train'+str(trainNum)+'Est'
		trainDelay = 'train'+str(trainNum)+'Delay'
		trainIssue = 'train'+str(trainNum)+'Issue'
		trainReason = 'train'+str(trainNum)+'Reason'
		trainCalling = 'train'+str(trainNum)+'Calling'

		# Update the device to blank
		dev.updateStateOnServer(trainDestination, value = '')
		dev.updateStateOnServer(trainSch, value = '')
		dev.updateStateOnServer(trainEst, value = '')
		dev.updateStateOnServer(trainDelay, value = '')
		dev.updateStateOnServer(trainIssue, value = False)
		dev.updateStateOnServer(trainReason, value = '')
		dev.updateStateOnServer(trainCalling, value = '')

	# Ok now set the station issues flag to No
	dev.updateStateOnServer('stationIssues', value = False)

	# Ok - now let's get the real data and store it

	# The CRS information will be held against the ROUTE device
	stationStartCrs = dev.states['stationCRS'] # Codes are found on the National Rail data site and will be provided as a drop list for users
	stationEndCrs = dev.states['destinationCRS']
	try:
		stationBoardDetails = darwinSession.get_station_board(stationStartCrs)
	except:
		errorHandler('WARINING ** SOAP resolution failed - will retry later when server less busy **')
		return False # This will generally resolve itself within a min anyway

	# Extract information on station and store
	stationBoardName = stationBoardDetails.location_name
	timeGenerated = getUKTime()
	dev.updateStateOnServer('stationLong',  value = stationBoardName)
	dev.updateStateOnServer('timeGenerated', value = timeGenerated)

	# Ok let's get the details for all the services
	# Maximum storage is 10 entries (after filtering)

	# Calculate the destination filter for display
	if stationEndCrs == 'ALL':
		viaStation = ''
		baseVia = ''
	else:
		baseVia = dev.states['destinationLong']
		viaStation = '(via:' + baseVia + ')'

	# Get the departures board
	# Filtered
	if stationEndCrs !='ALL':
		try:
			stationBoardDetails = darwinSession.get_station_board(stationStartCrs,100,True,False,stationEndCrs)
		except:
			errorHandler('WARINING ** SOAP resolution failed - will retry later when server less busy **')
			return False
	else:
		# All trains departing
		# Get the departures board
		try:
			stationBoardDetails = darwinSession.get_station_board(stationStartCrs,100,True,False)
		except:
			errorHandler('WARINING ** SOAP resolution failed - will retry later when server less busy **')
			return False

	if nationalDebug:
		# Print debug information
		indigo.server.log('-' * 30, level=logging.DEBUG)
		indigo.server.log('Calculating the Departures Board for:' + stationBoardDetails.location_name + viaStation, level=logging.DEBUG)
		indigo.server.log('Generated on:' + str(stationBoardDetails.generated_at)[11:19] + '\n', level=logging.DEBUG)

	# Image parameters set up
	imageContent = []
	columnTitles = "Destination,Sch,Est,By"
	imageContent.append(columnTitles)
	textPath = imagePath
	imageFileName = imagePath+'/'+stationStartCrs+stationEndCrs+'timetable.png'

	if nationalDebug:
		indigo.server.log('Image File:'+imageFileName, level=logging.DEBUG)

	wordLength = 80
	maxLines = 30

	departuresFound = False
	currentTrain = 0

	if nationalDebug:
		indigo.server.log('Number of destinations = '+str(len(stationBoardDetails.train_services)), level=logging.DEBUG)

	for destination in stationBoardDetails.train_services:
		if nationalDebug:
			indigo.server.log('Train is = ', str(destination), level=logging.DEBUG)

		# Indigo device is limited to 10 departure services and this will also limit the board as well in this version
		currentTrain += 1
		if currentTrain > 10:
			break

		departuresFound = True

		# Field names...
		trainDestination = 'train'+str(currentTrain)+'Dest'
		trainOperator = 'train'+str(currentTrain)+'Op'
		trainSch = 'train'+str(currentTrain)+'Sch'
		trainEst = 'train'+str(currentTrain)+'Est'
		trainDelay = 'train'+str(currentTrain)+'Delay'
		trainProblem = 'train'+str(currentTrain)+'Issue'
		trainReason = 'train'+str(currentTrain)+'Reason'
		trainCalling = 'train'+str(currentTrain)+'Calling'

		# Get the service informaiton
		try:
			service = darwinSession.get_service_details(destination.service_id)
		except:
			errorHandler('WARINING ** SOAP resolution failed - will retry later when server less busy **')
			return False

		# Store the data for an image file if needed
		destinationDetails = destination.destination_text + ' ' + destination.std + ' ' + destination.etd + ' Operator: ' + str(
			destination.operator_name)

		# Add on the delay to the message in the image file
		destinationDetails += ' ' + delayCalc(destination.std, destination.etd)[1]

		# Now physically update the device
		dev.updateStateOnServer(trainDestination, value = destination.destination_text)
		dev.updateStateOnServer(trainOperator, value = destination.operator_name)
		dev.updateStateOnServer(trainSch, value = destination.std)
		dev.updateStateOnServer(trainEst, value = destination.etd)

		# Calculate any delay to service
		delayToService = delayCalc(destination.std, destination.etd)
		dev.updateStateOnServer(trainDelay, value = delayToService[1])
		dev.updateStateOnServer(trainProblem, value = delayToService[0])

		if 'On Time'.find(delayToService[1]):
			dev.updateStateOnServer(trainReason, value = '')
		else:
			if trainReason is not None:
				dev.updateStateOnServer(trainReason, value = str('No reason provided'))
			else:
				dev.updateStateOnServer(trainReason, value = '')

		# Now the calling points
		try:
			callingPoints = [cp.location_name for cp in service.subsequent_calling_points]
			arrivalTimes = [arrival.st for arrival in service.subsequent_calling_points]
			estimatedTimes = [arrival.et for arrival in service.subsequent_calling_points]
		except:
			errorHandler('WARINING ** SOAP failed on Calling Points access - try again later **')
			return False

		cpIndex = 0
		cpString = ''
		departuresFound = True

		for cpoint in callingPoints:
			try:
				if estimatedTimes[cpIndex].find('On') != -1:
					cpString += cpoint + '(' + arrivalTimes[cpIndex]+') '
				else:
					cpString += cpoint + '(' + estimatedTimes[cpIndex]+') '
				cpIndex += 1
			except AttributeError:
				errorHandler('WARNING - Estimated Time for calling point returned NULL - not critical')

			except:
				errorHandler('WARNING - Estimated Time for calling point - unknown error advise developer')

		cpString = cpString.replace('On time', '')

		# Update the device with calling point information if required
		if dev.pluginProps['includeCalling']:
			callingContent = cpString
			dev.updateStateOnServer(trainCalling, value = callingContent)

		# Create the image information and store in imageContent
		if len(delayCalc(destination.std, destination.etd)[1].strip()) == 0:
			destinationContent = '\n'+destination.destination_text + ',' + destination.std + ',' + destination.etd + ',' + \
								 str(destination.operator_code)+'\n'
			imageContent.append(destinationContent)
		else:
			destinationContent = '\n'+destination.destination_text + ',' + destination.std + ',' + destination.etd + ',' + \
								 str(destination.operator_name)
			imageContent.append(destinationContent)
			delayMessage = 'Status:'+delayCalc(destination.std, destination.etd)[1]+'\n'
			imageContent.append(delayMessage)

		# Calling points for image
		# Check if calling points wanted in the image
		if dev.pluginProps['includeCalling']:
			callingContent = cpString
			if len(callingContent) > 0:
				# Is the width longer than the image size
				if len(callingContent)<=wordLength:
					# No need to split the line up
					imageContent.append('>>> ' + callingContent)
				else:
					# Split up the line into parts
					# Find the first ')' after wordLength
					# First Line
					cutWordPoint = callingContent.find(')',wordLength-1)
					imageContent.append('>>> ' + callingContent[:cutWordPoint+1])
					remainingLine = callingContent[cutWordPoint+1:]

					# Other Lines
					while len(remainingLine)>wordLength:
						cutWordPoint = remainingLine.find(')', wordLength)
						imageContent.append('>>> '+remainingLine[:cutWordPoint+1])
						remainingLine = remainingLine[cutWordPoint+2:]

					# Now the last piece
					if len(remainingLine.strip()) != 0:
						imageContent.append('>>> '+remainingLine)

	# Ok - now just check if there is an issue on one of the trains at this station and flag if necessary
	for trainNum in range(1,11):
		trainProblem = 'train'+str(trainNum)+'Issue'
		if dev.states[trainProblem]:
			# There is an issue with at least one train so flag the station
			dev.updateStateOnServer('stationIssues', value = True)
			# No need to check any more field
			break

	# Create Image
	titleSeparator = '\n'+'-'*80+'\n'

	# Test messages flag (remove after BETA)
	testingMessages = False

	# The title for the departure board
	if len(stationBoardDetails.nrcc_messages)>0 or testingMessages:
		if testingMessages:
			specialMessages = 'This is a test message that would span a lot of lines in the display.  ' \
							  'We need to format it correctly and remove any special characters'+u'&nbspBecause '+\
							  'it is so long it will take a lot of lines on the display and this should be managed'+ \
							  ' through the maxLines element'

		else:
			specialMessages = str(stationBoardDetails.nrcc_messages)

		specialMessages = formatSpecials(specialMessages)

	else:
		specialMessages = ''

	departureBoardTitles = ("Departures - "+stationBoardDetails.location_name + ' '+ viaStation + ' '*60)[:60]+'\n'
	departureStatistics = 'Generated on:' + timeGenerated+'\n'
	departureMessages = specialMessages+'\n'

	# Update device with messages
	dev.updateStateOnServer('stationMessages', value = specialMessages.replace('+',''))

	if departuresFound:
		# Now format the departure content correctly
		stationBoard = ''
		newDes = []
		totLines = 0

		for newLines in range(len(imageContent)):

			if imageContent[newLines].find('Status') != -1:
				# Departure Details
				boardLine = imageContent[newLines]

			elif imageContent[newLines].find('>>>') == -1:
				# This is a destination line
				newDes = imageContent[newLines].split(',')
				destination = newDes[0] + '-' * 50
				schedule = newDes[1] + '-' * 10
				estimated = newDes[2] + '-' * 10
				operator = newDes[3]
				boardLine = destination[:35] + ' ' +schedule[:10] + estimated[:10] + operator

			else:
				# Calling points
				boardLine = imageContent[newLines]

			stationBoard = stationBoard + boardLine +'\n'

			# Check it still fits in the image
			totLines += 1
			if totLines>maxLines:
				break

	else:
		if len(viaStation) != 0:
			stationBoard = "** No departures found from "+stationBoardDetails.location_name+" direct to "+baseVia\
						   + " today **\n** Check Operators website for more information on current schedule and issues **"
		else:
			stationBoard = "** No departures found from "+stationBoardDetails.location_name\
						   + " today **\n** Check Operators website for more information on current schedule and issues **"

		dev.updateStateOnServer('stationMessages', value = specialMessages)

	# Ready to create image from information
	# Now we can create the image - yay
	# Create a text file for the image in the location stored
	trainText = textPath+'/'+stationStartCrs+stationEndCrs+'departureBoard.txt'
	trainTextFile =  open(trainText,'w')

	# Write the Departure board information first
	trainTextFile.write(departureBoardTitles)
	trainTextFile.write(departureStatistics)
	if len(departureMessages.strip()) != 0:
		trainTextFile.write(departureMessages)

	# Now the stationboard itself
	trainTextFile.write(stationBoard)
	trainTextFile.close()

	# Now run an instance of python with the corrent information to create a file for the Refreshing URL funcitonality
	if departuresFound:
		departuresAvailable = 'YES'
	else:
		departuresAvailable = 'NO'

	# Now we can call the subprocess to manage the conversion and move onto the next image
	# We run a fresh python image which means that the current environment variables are maintained for shared files
	# See forum for more details
	# Create places for the stderror and stdoutput
	indigo.debugger()
	outputInfo = open(pypath+'myImageOutput.txt',mode = 'w')
	errorInfo = open(pypath+'myImageErrors.txt',mode = 'w')
	if nationalDebug:
		indigo.server.log('Pypath = '+str(pypath)+'\nError: '+str(errorInfo)+'\nStandard: '+str(outputInfo))
	parametersFileNameMac = parametersFileName.replace(' ','\ ')
	imgResult = subprocess.run(['/Library/Frameworks/Python.framework/Versions/Current/bin/python3', pypath+'text2png.py', imageFileName, trainText, parametersFileName, departuresAvailable], stdout=outputInfo, stderr=errorInfo)

	print(imgResult)
	return True

def nationalRailLogin(wsdl = 'https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx',api_key='NO KEY'):
	# Module forces a login to the National Rail darwin service.  An API key is needed and the plugin will
	# fail if it's not provided

	global nationalDebug, pypath

	if wsdl.find('realtime.nationalrail') == -1:
		# Darwin address is invalid
		# print error message and return
		if nationalDebug:
			indigo.server.log('Darwin address is invalid - please read forum for update or contact developer')

		errorHandler('CRITICAL FAILURE ** Darwin is invalid - please check or advise developer - '+wsdl+' **')

		return False, None

	# We have a site and a key now try to use it:
	try:
		darwin_sesh = DarwinLdbSession(wsdl, api_key)
		# Login successful
		if nationalDebug:
			indigo.server.log('Login successful - now processing routes...')

		return True, darwin_sesh

	except:
		# Login failed. As the user to check details and try again
		if nationalDebug:
			indigo.server.log('Login failed - a) API key invalid, b) Dawin Offline or c) No Internet Access - Please check and reload plugin')

		errorHandler('WARNING ** Failed to log in to Darwin - check API key and internet connection')

		return False, None

################################################################################
class Plugin(indigo.PluginBase):
	########################################
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):

		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

		self.validatePrefsConfigUi(pluginPrefs)
		global nationalDebug, stationDict, pypath
		self.pluginid = pluginId
		# Set up version checker
		travelVersionFile = 'https://www.dropbox.com/s/62kahe2nh848b65/iTravelVersionInfo.html?dl=1'

		if nationalDebug:
			indigo.server.log('Initiating Plugin Class...', level=logging.DEBUG)

	def __del__(self):
		indigo.PluginBase.__del__(self)

	def validateDeviceConfigUi(self, devProps, typeId, devId):
		global nationalDebug, stationDict, pypath

		# Create station dictionary for lookup
		currentStationDict = self.createStationDict()

		# Create error dictionary
		errorDict = indigo.Dict()

		if 'trainRoute' in devProps:
			if len(devProps['trainRoute']) == 0:
				devProps['trainRoute']='Please enter valid name before continuing'
				errorDict = indigo.Dict()
				errorDict["trainRoute"] = "Enter a valid route name"
				errorDict["showAlertText"] = "You must enter a unique route name"
				return (False, devProps, errorDict)
		else:
			devProps['trainRoute'] = 'Unnamed Route:'+devId

		if 'stationName' in devProps:
			if len(devProps['stationName']) == 0 or devProps['stationName']=='All Destinations':
				devProps['stationCode']=''
				errorDict = indigo.Dict()
				errorDict["stationName"] = "Select a valid starting station"
				errorDict["showAlertText"] = "You must enter a unique start station name (not ALL or Blank)"
				return (False, devProps, errorDict)
			
			elif devProps['stationName'] in currentStationDict:

				# Name exists so get the code
				stationCRS = self.returnNetworkRailCode(devProps['stationName'], currentStationDict)
				devProps['stationCode'] = stationCRS

			else:
				devProps['stationName']='All Destinations'
				errorDict = indigo.Dict()
				errorDict["stationCode"] = "Select a valid starting station"
				errorDict["showAlertText"] = "You must select a unique start station name not All destinations"
				return (False, devProps, errorDict)

		else:
			devProps['stationCode'] = "WAT"
			devProps['stationName'] = 'London Waterloo'

		if 'destinationName' in devProps:
			if len(devProps['destinationName']) == 0 or devProps['destinationName']=='All Destinations':
				devProps['destinationName'] = 'All Destinations'
				devProps['destinationCode'] = 'ALL'
			
			elif devProps['destinationName'] in currentStationDict:
				# Code exists so update other information
				destStationCRS = self.returnNetworkRailCode(devProps['destinationName'], currentStationDict)
				devProps['destinationCode'] = destStationCRS

			else:
				devProps['destinationCode']='ZZZ'
				errorDict = indigo.Dict()
				errorDict["destinationName"] = "Select a valid destination station or leave blank"
				errorDict["showAlertText"] = "You must enter a unique destination station name or select ALL"
				return (False, devProps, errorDict)
		else:
			devProps['destinationCode'] = "ALL"
			devProps['destinationName'] = 'All destinations'

		# Finally update the states
		return True, devProps, errorDict

	def validatePrefsConfigUi(self, devProps):
		global nationalDebug, stationDict

		if nationalDebug:
			indigo.server.log('Validating Config file...')

		errorDict = indigo.Dict()
		if 'darwinAPI' in devProps:
			if len(devProps['darwinAPI']) == 0:
				devProps['darwinAPI']='Please enter valid name before continuing'
				errorDict = indigo.Dict()
				errorDict["darwinAPI"] = "Enter a valid API Key"
				errorDict["showAlertText"] ='You must enter a valid API key - see forum for details on obtaining a free key'
				return (False, devProps, errorDict)
		else:
			devProps['darwinAPI']='Please enter valid API before continuing'
			errorDict = indigo.Dict()
			errorDict["darwinAPI"] = "Invalid API Key"
			errorDict["showAlertText"] ='You must enter a valid API key - see forum for details on obtaining a free key'
			return (False, devProps, errorDict)

		if 'darwinSite' in devProps:
			if len(devProps['darwinSite']) == 0:
				devProps['darwinSite']='Please enter valid network site URL'
				errorDict = indigo.Dict()
				errorDict["darwinSite"] = "Invalid Darwin Network Rail URL"
				errorDict["showAlertText"] ='You must enter a valid Network Rail Darwin Site  - see forum for details on obtaining a free key'
				return (False, devProps, errorDict)
		else:
			devProps['darwinSite']='https://lite.realtime.nationalrail.co.uk/OpenLDBWS/wsdl.aspx'

		if 'createMaps' in devProps:
			if devProps['createMaps']:
				# Check image file name
				if len(devProps['imageFilename']) == 0:
					errorDict = indigo.Dict()
					errorDict["stationCode"] = "No file path found for images"
					errorDict["showAlertText"] = "You must enter a path for your image (e.g. /Users/myIndigo) - no trailing '/'"
					return (False, devProps, errorDict)


				try:
					if nationalDebug:
						indigo.server.log('Trying to create file '+devProps['imageFilename']+'/filecheck.txt')

					f=open(devProps['imageFilename']+'/filecheck.txt','w')
					f.close()
				except:
					# Can't open file in location report error to user
					errorDict = indigo.Dict()
					errorDict["imageFilename"] = "Invalid path for image files"
					errorDict["showAlertText"] = "You must enter a valid path for your image (e.g. /Users/myIndigo) - no trailing '/'"
					return (False, devProps, errorDict)

			else:
				# No maps
				devProps['imageFilename'] = 'No images being saved'
		else:
			devProps['createMaps'] = False

		if 'forcolour' in devProps:
			if devProps['forcolour'].find('#') == -1:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["forcolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #0F0 default = Green)"
				return (False, devProps, errorDict)

		if 'bgcolour' in devProps:
			if devProps['bgcolour'].find('#') == -1:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["bgcolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #000 default = Black)"
				return (False, devProps, errorDict)

		if 'isscolour' in devProps:
			if devProps['isscolour'].find('#') == -1:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["isscolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #F00 default = Red)"
				return (False, devProps, errorDict)

		if 'cpcolour' in devProps:
			if devProps['cpcolour'].find('#') == -1:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["cpcolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #000 default = White)"
				return (False, devProps, errorDict)

		if 'ticolour' in devProps:
			if devProps['ticolour'].find('#') == -1:
				# Missing # in colour format - tell user to correct and fail
				errorDict = indigo.Dict()
				errorDict["ticolour"] = "Missing # symbol in colour specification"
				errorDict["showAlertText"] = "You must enter a code similar to #FFF (i.e. #0FF default = Cyan)"
				return (False, devProps, errorDict)

		return (True, devProps)

	########################################
	# Internal utility methods. Some of these are useful to provide
	# a higher-level abstraction for accessing/changing route
	# properties or states.
	######################

	# Now define the key functions used to manage Route Device
	######################
	# Poll all of the states from the devices and pass new values to
	# Indigo Server.
	def _refreshStatesFromHardware(self, dev):
		# Send status updates to the indigo log
		if nationalDebug:
			indigo.server.log(u"RGB States check called")

	########################################
	def deviceStartComm(self, dev):
		dev.stateListOrDisplayStateIdChanged()  # Ensure latest devices.xml is being used
		if dev.pluginProps['routeActive']:
			dev.updateStateOnServer('deviceActive', True)
		else:
			dev.updateStateOnServer('deviceActive', False)

	def deviceStopComm(self, dev):
		return

	def deviceDeleted(self, dev):
		# Special routines for deleted devices
		pass

	########################################
	# Sensor Action callback
	######################
	def actionControlSensor(self, action, dev):
		###### TURN ON ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		if action.sensorAction == indigo.kSensorAction.TurnOn:
			if nationalDebug:
				indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name.encode('ascii', 'ignore'), "on"), level=logging.DEBUG)

		###### TURN OFF ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		elif action.sensorAction == indigo.kSensorAction.TurnOff:
			if nationalDebug:
				indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name.encode('ascii', 'ignore'), "off"), level=logging.DEBUG)

		###### TOGGLE ######
		# Ignore turn on/off/toggle requests from clients since this is a read-only sensor.
		elif action.sensorAction == indigo.kSensorAction.Toggle:
			if nationalDebug:
				indigo.server.log(u"ignored \"%s\" %s request (sensor is read-only)" % (dev.name.encode('ascii', 'ignore'), "toggle"), level=logging.DEBUG)

	########################################
	# General Action callback
	######################
	def actionControlGeneral(self, action, dev):
		###### BEEP ######
		if action.deviceAction == indigo.kDeviceGeneralAction.Beep:
			# Beep the hardware module (dev) here:
			# ** IMPLEMENT ME **
			indigo.server.log(u"sent \"%s\" %s" % (dev.name.encode('ascii', 'ignore'), "beep request"), level=logging.DEBUG)

		###### ENERGY UPDATE ######
		elif action.deviceAction == indigo.kDeviceGeneralAction.EnergyUpdate:
			# Request hardware module (dev) for its most recent meter data here:
			# ** IMPLEMENT ME **
			indigo.server.log(u"sent \"%s\" %s" % (dev.name.encode('ascii', 'ignore'), "energy update request"), level=logging.DEBUG)

		###### ENERGY RESET ######
		elif action.deviceAction == indigo.kDeviceGeneralAction.EnergyReset:
			# Request that the hardware module (dev) reset its accumulative energy usage data here:
			# ** IMPLEMENT ME **
			indigo.server.log(u"sent \"%s\" %s" % (dev.name.encode('ascii', 'ignore'), "energy reset request"), level=logging.DEBUG)

		###### STATUS REQUEST ######
		elif action.deviceAction == indigo.kDeviceGeneralAction.RequestStatus:
			# Query hardware module (dev) for its current status here. This differs from the
			# indigo.kThermostatAction.RequestStatusAll action - for instance, if your thermo
			# is battery powered you might only want to update it only when the user uses
			# this status request (and not from the RequestStatusAll). This action would
			# get all possible information from the thermostat and the other call
			# would only get thermostat-specific information:
			# ** GET BATTERY INFO **
			# and call the common function to update the thermo-specific data
			self._refreshStatesFromHardware(dev)
			if nationalDebug:
				indigo.server.log(u"sent \"%s\" %s" % (dev.name.encode('ascii', 'ignore'), "status request"), level=logging.DEBUG)

	def startup(self):
		global nationalDebug, stationDict, pypath

		try:
			requirements.requirements_check(self.pluginid)
		except ImportError as exception_error:
			self.logger.critical(f"PLUGIN STOPPED: {exception_error}")
			self.do_not_start_devices = True
			self.stopPlugin()

		if nationalDebug:
			indigo.server.log('Initiating Plugin Startup module...', level=logging.DEBUG)

		if self.pluginPrefs.get('checkboxDebug1',False):
			indigo.server.log(u"startup called")

		# Get configuration
		apiKey = self.pluginPrefs.get('darwinAPI', 'NO KEY')
		dawinURL = self.pluginPrefs.get('darwinSite', 'No URL')
		stationImage = self.pluginPrefs.get('createMaps', "true")
		refreshFreq = int(self.pluginPrefs.get('updateFreq','60'))
		nationalDebug = self.pluginPrefs.get('checkboxDebug1', False)

		if stationImage:
			imagePath= self.pluginPrefs.get('imageFilename', '/Users')
		else:
			imagePath = 'No Image'

		try:
			self.pluginPrefs['checkboxDebug']='false'
			self.pluginPrefs['updaterEmail']=''
			self.pluginPrefs['updaterEmailsEnabled']='false'

		except:
			if self.pluginPrefs.get('checkBoxDebug',False):
				self.errorLog(u"Update checker error.")

		for dev in indigo.devices.itervalues("self"):
			# Now check states
			dev.stateListOrDisplayStateIdChanged()

	def shutdown(self):
		indigo.server.log(u"shutdown called")

	########################################
	def runConcurrentThread(self):
		# Get the most current information
		# Validate preferences exist
		global nationalDebug, stationDict, pypath

		# Empty log

		self.logger.info('New Log:'+str(time.strftime(time.asctime()))+'\n')

		logTimeNextReset = time.time()+int(3600)

		while True:
			# Get configuration
			apiKey = self.pluginPrefs.get('darwinAPI', 'NO KEY')
			darwinURL = self.pluginPrefs.get('darwinSite', 'No URL')
			stationImage = self.pluginPrefs.get('createMaps', "true")
			refreshFreq = int(self.pluginPrefs.get('updateFreq','60'))
			nationalDebug = self.pluginPrefs.get('checkboxDebug1', False)

			fontFullPath = pypath+'BoardFonts/MFonts/Lekton-Bold.ttf' # Regular
			fontFullPathTitle = pypath+'BoardFonts/MFonts/sui generis rg.ttf' # Bold Title
			fontCallingPoints = pypath+'BoardFonts/MFonts/Hack-RegularOblique.ttf' # Italic

			# Get colours for display or defaults
			forcolour = self.pluginPrefs.get('forcolour', '#0F0')
			bgcolour = self.pluginPrefs.get('bgcolour', '#000')
			isscolour = self.pluginPrefs.get('isscolour', '#F00')
			cpcolour = self.pluginPrefs.get('cpcolour', '#FFF')
			ticolour = self.pluginPrefs.get('ticolour', '#0FF')

			if stationImage:
				imagePath= self.pluginPrefs.get('imageFilename', '/Users')

				# Now create a parameters file - this is user changeable in the BETA version
				parametersFileName = pypath+'trainparameters.txt'
				parametersFile = open(parametersFileName,'w')
				parametersFile.write(forcolour+','+bgcolour+','+isscolour+','+ticolour+','+cpcolour+',9,3,3,720')
				parametersFile.close()

			else:
				imagePath = 'No Image'

			try:
				self.pluginPrefs['checkboxDebug']='false'
				self.pluginPrefs['updaterEmail']=''
				self.pluginPrefs['updaterEmailsEnabled']='false'
				self.updater.checkVersionPoll()

			except:
				if self.pluginPrefs.get('checkBoxDebug',False):
					self.errorLog(u"Update checker error.")

			# Reset the log?
			if logTimeNextReset<time.time():
				f = open(errorFile,'w')
				f.write('#'*80+'\n')
				f.write('Log reset:'+str(time.strftime(time.asctime()))+'\n')
				f.write('#'*80+'\n')
				f.close()
				logReset = False
				logTimeNextReset = time.time()+int(3600)

			for dev in indigo.devices.iter('self.trainTimetable'):
				# Refresh each of the timeTable route devices in turn

				# Set the state flag
				# Update the standard fields if they've been changed
				# Checking
				# Test mode only
				if nationalDebug:
					indigo.server.log('Device:'+dev.name+' being checked now...', level=logging.DEBUG)

				if nationalDebug:
					indigo.server.log(dev.name+' is '+ str(dev.states['deviceActive']), level=logging.DEBUG)

				if dev.states['deviceActive']:
					dev.updateStateOnServer('stationLong', value = dev.pluginProps['stationName'])
					dev.updateStateOnServer('stationCRS',value = dev.pluginProps['stationCode'])
					dev.updateStateOnServer('destinationLong', value  = dev.pluginProps['destinationName'])
					dev.updateStateOnServer('destinationCRS',value = dev.pluginProps['destinationCode'])

					# Update the device with the latest information
					deviceRefresh = routeUpdate(dev, apiKey, darwinURL, imagePath, parametersFileName)

					if not deviceRefresh:
						# Update failed - probably due to SOAP server timeout
						# Ignore and move onto the next device
						# Change the active icon on this round
						dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
						dev.updateStateOnServer('deviceStatus', value = 'Awaiting update')
						if nationalDebug:
							indigo.server.log('** Error updating device '+dev.name+' SOAP server failure **')
					else:
						# Success
						if dev.states["stationIssues"]:
							dev.updateStateImageOnServer(indigo.kStateImageSel.SensorTripped)
							dev.updateStateOnServer('deviceStatus', value = 'Delays or issues')
						else:
							dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOn)
							dev.updateStateOnServer('deviceStatus', value = 'Running on time')

						if nationalDebug:
							indigo.server.log('** Sucessfully updated:'+dev.name+' **')

				else:
					dev.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
					dev.updateStateOnServer('deviceStatus', value = 'Not active')

			self.sleep(refreshFreq)

		# Broken out of TRUE loop so shutdown
		self.shutdown()

	########################################
	# Menu. xls
	######################

	# Possible functionality
	# 	Active/Inactive Toggle
	# 	Print departure board to file or log


	########################################
	# Custom Plugin Action callbacks (defined in Actions.xml)
	######################
	# Possible functionality
	# 	Activate/Deactivate
	# 	Refresh Stationboard immediately

	# Selection actions for device configuration

	def selectStation(self, filter="", valuesDict=None, typeId="", targetId=0):
		global nationalDebug, stationDict, pypath

		# Refresh the station codes from file
		stationDict = {}

		# Open the station codes file
		stationCodesFile = pypath+'/stationCodes.txt'

		try:
			stations = open(stationCodesFile,"r")
		except:
			# Couldn't find stations file - advise user and exit
			indigo.server.log('*** Could not open station code file '+stationCodesFile+' ***')
			errorHandler('CRITICAL FAILURE ** Station Code file missing - '+stationCodesFile)
			sys.exit(1)

		# Extract the data to dictionary
		# Data format is CRS,Station Name (csv)
		for line in stations:
			stationDetails = line
			stationCRS = stationDetails[:3]
			stationName = stationDetails[4:].replace('\r\n','')

			# Add to dictionary
			stationDict={}
			stationDict[stationName]=stationName

		# Close the data file
		stations.close()

		if len(stationDict) == 0:
			# Dictionary is empty - advise user and exit
			indigo.server.log('*** Station File is empty - please reinstall '+stationCodesFile+' ***')
			errorHandler('CRITICAL FAILURE ** Station code file empty - '+stationCodesFile)
			sys.exit(1)
		indigo.debugger()
		stationCodeArray = stationDict.items()
		#stationCodeArray.sort(key=lambda x: x.get('1'))
		#jmoistures.sort(key=lambda x: x.get('id'), reverse=True)

		return stationCodeArray

	def actionRefreshDevice(self, pluginAction, typeId, dev):
		# This immediately refreshes the device station board information

		return pluginAction

	def refreshDevice(self, valuesDict, typeId):
		# This refreshes the device station information as requested by the plugin

		return valuesDict

	def createStationDict(self):

		global nationalDebug, pypath

		# Refresh the station codes from file
		localStationDict = {}

		# Open the station codes file
		stationCodesFile = pypath+'/stationCodes.txt'

		try:
			stations = open(stationCodesFile,"r")
		except:
			# Couldn't find stations file - advise user and exit
			indigo.server.log('*** Could not open station code file '+stationCodesFile+' ***')
			errorHandler('CRITICAL FAILURE ** Station Code file missing - '+stationCodesFile)
			sys.exit(1)

		# Extract the data to dictionary
		# Data format is CRS,Station Name (csv)
		for line in stations:
			stationDetails = line
			stationCRS = stationDetails[:3]
			stationName = stationDetails[4:].replace('\r\n','')

			# Add to dictionary
			localStationDict[stationName]=stationCRS

		# Close the data file
		stations.close()

		if len(localStationDict) == 0:
			# Dictionary is empty - advise user and exit
			indigo.server.log('*** Station File is empty - please reinstall '+stationCodesFile+' ***')
			errorHandler('CRITICAL FAILURE ** Station code file empty - '+stationCodesFile)
			sys.exit(1)

		return localStationDict

	def returnNetworkRailCode(self,fullStationName, localStationDict):
		# Returns a three digit code for a station name in local station dictionary
		global nationalDebug, pypath

		if len(fullStationName) == 0:
			# No station name sent through so return a blank code
			return 'ZZZ'

		if fullStationName in localStationDict:
			# Found the station name
			# return the 3 digital code
			return localStationDict[fullStationName]
		else:
			# Station Name not in Dictionary
			# Return error
			return 'ZZZ'

	def toggleDebugging(self):
		if self.debug:
			self.logger.info("Turning off debug logging")
			self.pluginPrefs["showDebugInfo"] = False
		else:
			self.logger.info("Turning on debug logging")
			self.pluginPrefs["showDebugInfo"] = True
		self.debug = not self.debug


def text2png(imageFileName, trainTextFile, parametersFileName, departuresAvailable):
	# Import the graphic conversion files
	try:
		import PIL
	except:
		print('** PILLOW or PIL must be installed - please see forum for details')
		sys.exit(21)

	# Now get the key modules we're using on this occasion
	from PIL import ImageFont
	from PIL import Image
	from PIL import ImageDraw

	# Get the current python path for text files
	pypath = os.path.realpath(sys.path[0]) + '/'
	indigo.debugger()
	# Get the passed parameters in the command line

	if nationalDebug:
		indigo.server.log(parametersFileName, level=logging.DEBUG)

	if departuresAvailable.find('YES') != -1:
		trainsFound = True
	else:
		trainsFound = False

	# Extract the standard parameters for the image from file
	# This file is used to communication between Indigo and this independant process
	# File format is:
	#   forcolour, bgcolour, isscolour, ticolour, cpcoloour, fontFullpath, fontFullPathTitle, fontSize,leftpadding,
	#   rightpadding, width, trainsfound, imageFileName, sourceDataName

	with open(parametersFileName, 'r') as f:
		parameterSplit = f.readline().split(',')
	forcolour = parameterSplit[0]
	bgcolour = parameterSplit[1]
	isscolour = parameterSplit[2]
	ticolour = parameterSplit[3]
	cpcolour = parameterSplit[4]
	fontsize = int(parameterSplit[5])
	leftpadding = int(parameterSplit[6])
	rightpadding = int(parameterSplit[7])
	width = int(parameterSplit[8])

	# Ok now we need to extract the station for the departure board
	# Extract station and route timetable information

	try:
		routeInfo = open(trainTextFile, 'r')
	except:
		print('Something wrong with the text file!' + trainTextFile)
		print(sys.exit(22))

	stationTitles = routeInfo.readline()
	stationStatistics = routeInfo.readline()

	timeTable = ''
	for fileEntry in trainTextFile:
		timeTable = timeTable + '\n' + routeInfo.readline()

	# Converts timeTable array into a departure board image for display
	# Work out formatting characters
	REPLACEMENT_CHARACTER = u'ZZFZ'
	NEWLINE_REPLACEMENT_STRING = ' ' + REPLACEMENT_CHARACTER + ' '

	# Get the fonts for the board
	fontFullPath = pypath + 'BoardFonts/MFonts/Lekton-Bold.ttf'  # Regular
	fontFullPathTitle = pypath + 'BoardFonts/MFonts/sui generis rg.ttf'  # Bold Title
	fontCallingPoints = pypath + 'BoardFonts/MFonts/Hack-RegularOblique.ttf'  # Italic

	# Get the font for the image.  Must be a mono-spaced font for accuracy
	font = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontFullPath, fontsize + 4)
	titleFont = ImageFont.load_default() if fontFullPathTitle == None else ImageFont.truetype(fontFullPathTitle, fontsize + 12)
	statusFont = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontFullPath, fontsize + 5)
	departFont = ImageFont.load_default() if fontFullPathTitle == None else ImageFont.truetype(fontFullPath, fontsize + 8)
	delayFont = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontFullPath, fontsize + 4)
	callingFont = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontCallingPoints, fontsize + 2)
	messagesFont = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontCallingPoints, fontsize)

	# Calculate image size
	timeTable = timeTable.replace('\n', NEWLINE_REPLACEMENT_STRING)
	lines = []
	line = u""

	for word in timeTable.split():
		# Check to see if the word is longer than the possible size of image
		if word == REPLACEMENT_CHARACTER:  # give a blank line
			lines.append(line[1:].replace('-', ' '))  # slice the white space in the begining of the line
			line = u""
		# lines.append( u"" ) #the blank line

		elif line.find('++') != -1:
			# This is a status line and can be longer
			# Width is controlled in the main plugin
			line += ' ' + word

		elif font.getsize(line + ' ' + word)[0] <= (width - rightpadding - leftpadding):
			line += ' ' + word

		else:  # start a new line because the word is longer than a line
			# Line splitting now managed in main code
			continue

	if len(line) != 0:
		lines.append(line[1:])  # add the last line

	# Calculate image proportions
	line_height = font.getsize(timeTable)[1]
	img_height = line_height * (30)
	line_height = int(line_height / 1.5 + 0.5)

	if not trainsFound:
		img_height = line_height * (30)

	# Draw the blank image
	img = Image.new("RGBA", (width, img_height), bgcolour)
	draw = ImageDraw.Draw(img)

	# Extract the station details
	# Remove the char returns
	titleLines = stationTitles.replace('\n', NEWLINE_REPLACEMENT_STRING)
	statsLines = stationStatistics.replace('\n', NEWLINE_REPLACEMENT_STRING)

	# Draw the titles in Cyan in title font
	y = 0
	stationName = stationTitles
	draw.text((leftpadding, y), stationName, ticolour, font=titleFont)
	y += line_height + 15
	stationStats = stationStatistics
	draw.text((leftpadding, y), stationStats, cpcolour, font=statusFont)
	y += line_height
	currentService = 0
	maxLines = 35
	maxServices = 5
	noMoreTrains = False

	# Now add the content
	for line in lines:

		# Is this the titles line for the columns?
		if line.find('Destination') != -1:

			# Column titles in cyan
			y += int(line_height * 0.5)
			draw.text((leftpadding, y), line, cpcolour, font=departFont)
			y += line_height

		elif len(line) == 0:
			# Blank line
			y += (line_height / 2 + 0.5)
			pass

		elif line.find('**') != -1:
			# No trains found message
			draw.text((leftpadding + 10, y), line, isscolour, font=statusFont)
			y += line_height * 1.2

		elif line.find('++') != -1:
			# Station Messages found
			draw.text((leftpadding+10, y), line.replace('+',''), isscolour, font=messagesFont)
			y += int(line_height * 0.5)

		elif line.find('Status') != -1:
			draw.text((leftpadding, y), line, ticolour, font=delayFont)
		# y += line_height

		elif line.find('>') == -1:
			if noMoreTrains:
				# Don't process this one onwards
				break

			# Draw a destination with details
			if line.find('On time') != - 1:
				# Train is running on time
				draw.text((leftpadding, y), line, forcolour, font=departFont)

			elif line.find('Special') != -1:
				draw.text((leftpadding, y), line, forcolour, font=callingFont)

			else:
				draw.text((leftpadding, y), line, isscolour, font=departFont)

			y += line_height + 5

			currentService += 1
			if currentService > maxServices:
				# Only five services per board
				noMoreTrains = True
		else:
			# Calling points
			draw.text((leftpadding + 5, y), line.replace('>', ' '), cpcolour, font=callingFont)
			y += line_height
	img1 = img.save(imageFileName, 'png')