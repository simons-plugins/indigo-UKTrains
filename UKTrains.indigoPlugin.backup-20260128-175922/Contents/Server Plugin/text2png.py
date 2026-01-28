###################################################################
# Separate process that will automatically take a text file of station
# and departure service information and create a PNG file for use as
# a refreshing URL in Indigo
#
# Version - 0.1
# Author - Mike Hesketh (Chameleon)
#
# Uses the excellent PILLOW python wrapper for PIL which must be installed

# Converts text information to a graphic image outside of indigo
import os, sys

# Import the graphic conversion files
try:
    import PIL
except ImportError as e:
    print(f"** PILLOW or PIL must be installed: {e}")
    sys.exit(21)

# Now get the key modules we're using on this occasion
from PIL import ImageFont
from PIL import Image
from PIL import ImageDraw

# Get the current python path for text files
pypath = os.path.realpath(sys.path[0])+'/'

# Get the passed parameters in the command line
trainArguments = sys.argv
print(trainArguments)
# Fail if no parameters found or less than 3
if len(trainArguments) < 4:
    print('** Failed to find arguments - image creation abandoned - contact Developer ** \n')

# Ok get the details
imageFileName = trainArguments[1]
trainTextFile = trainArguments[2]
parametersFileName = trainArguments[3]
departuresAvailable = trainArguments[4]

print(imageFileName)
print(trainTextFile)
print(parametersFileName)
print(departuresAvailable)


if 'YES' in departuresAvailable:
    trainsFound = True
else:
    trainsFound = False

# Extract the standard parameters for the image from file
# This file is used to communication between Indigo and this independant process
# File format is:
#   forcolour, bgcolour, isscolour, ticolour, cpcoloour, fontFullpath, fontFullPathTitle, fontSize,leftpadding,
#   rightpadding, width, trainsfound, imageFileName, sourceDataName

paraFile = open(parametersFileName, 'r')
parameterData = paraFile.readline()
parameterSplit = parameterData.split(',')
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
except (IOError, OSError) as e:
    print(f"Something wrong with the text file {trainTextFile}: {e}")
    print(sys.exit(22))

stationTitles = routeInfo.readline()
stationStatistics = routeInfo.readline()

timeTable = ''
for fileEntry in trainTextFile:
    timeTable = timeTable+'\n'+routeInfo.readline()

# Converts timeTable array into a departure board image for display
# Work out formatting characters
REPLACEMENT_CHARACTER = 'ZZFZ'
NEWLINE_REPLACEMENT_STRING = ' ' + REPLACEMENT_CHARACTER + ' '

# Get the fonts for the board
fontFullPath = pypath+'BoardFonts/MFonts/Lekton-Bold.ttf' # Regular
fontFullPathTitle = pypath+'BoardFonts/MFonts/sui generis rg.ttf' # Bold Title
fontCallingPoints = pypath+'BoardFonts/MFonts/Hack-RegularOblique.ttf' # Italic


# Get the font for the image.  Must be a mono-spaced font for accuracy
font = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontFullPath, fontsize + 4)
titleFont = ImageFont.load_default() if fontFullPathTitle == None else ImageFont.truetype(fontFullPathTitle,
                                                                                         fontsize + 12)
statusFont = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontFullPath, fontsize + 5)
departFont = ImageFont.load_default() if fontFullPathTitle == None else ImageFont.truetype(fontFullPath,
                                                                                         fontsize + 8)
delayFont = ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontFullPath, fontsize + 4)
callingFont= ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontCallingPoints, fontsize+2)
messagesFont= ImageFont.load_default() if fontFullPath == None else ImageFont.truetype(fontCallingPoints, fontsize)

# Calculate image size
timeTable = timeTable.replace('\n', NEWLINE_REPLACEMENT_STRING)
lines = []
line = ""

for word in timeTable.split():
    # Check to see if the word is longer than the possible size of image
    if word == REPLACEMENT_CHARACTER:  # give a blank line
        lines.append(line[1:].replace('-', ' '))  # slice the white space in the begining of the line
        line = ""
    # lines.append( "" ) #the blank line

    elif '++' in line:
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
line_height = int(line_height/1.5+0.5)

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
y += line_height+15
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
    if 'Destination' in line:

        # Column titles in cyan
        y += int(line_height*0.5)
        draw.text((leftpadding, y), line, cpcolour, font=departFont)
        y += line_height

    elif len(line) == 0:
        # Blank line
        y += (line_height/2+0.5)
        pass

    elif '**' in line:
        # No trains found message
        draw.text((leftpadding+10, y), line, isscolour, font=statusFont)
        y += line_height*1.2

    elif '++' in line:
        # Station Messages found
        draw.text((leftpadding+10, y), line.replace('+',''), isscolour, font=messagesFont)
        y += int(line_height*0.5)

    elif 'Status' in line:
        draw.text((leftpadding, y), line, ticolour, font=delayFont)
        # y += line_height

    elif '>' not in line:
        if noMoreTrains:
            # Don't process this one onwards
            break

        # Draw a destination with details
        if 'On time' in line:
            # Train is running on time
            draw.text((leftpadding, y), line, forcolour, font=departFont)

        elif 'Special' in line:
            draw.text((leftpadding, y), line, forcolour, font=callingFont)

        else:
            draw.text((leftpadding, y), line, isscolour, font=departFont)

        y += line_height+5

        currentService += 1
        if currentService > maxServices:
            # Only five services per board
            noMoreTrains = True
    else:
        # Calling points
        draw.text((leftpadding + 5, y), line.replace('>',' '), cpcolour, font=callingFont)
        y += line_height
img1 = img.save(imageFileName, 'png')