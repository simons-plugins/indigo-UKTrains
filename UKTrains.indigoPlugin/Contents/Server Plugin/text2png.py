###################################################################
# Separate process that will automatically take a text file of station
# and departure service information and create a PNG file for use as
# a refreshing URL in Indigo
#
# Version - 0.2
# Author - Mike Hesketh (Chameleon)
# Updated - 2026-02-02 - Standardized exit codes and error handling
#
# Uses the excellent PILLOW python wrapper for PIL which must be installed

# Converts text information to a graphic image outside of indigo
import os, sys

# Import the graphic conversion files
try:
    import PIL
except ImportError as e:
    print(f"PILLOW or PIL must be installed: {e}", file=sys.stderr)
    sys.exit(2)  # PIL error

# Now get the key modules we're using on this occasion
from PIL import ImageFont
from PIL import Image
from PIL import ImageDraw


def load_font_safe(font_path: str, size: int, font_name: str = "font"):
    """Load TrueType font with fallback to default.

    Args:
        font_path: Path to .ttf file
        size: Font size in points
        font_name: Description for error messages

    Returns:
        ImageFont object (truetype or default)
    """
    try:
        return ImageFont.truetype(font_path, size)
    except OSError as e:
        print(f"Warning: Could not load {font_name} '{font_path}': {e}", file=sys.stderr)
        print(f"Using default font for {font_name}", file=sys.stderr)
        return ImageFont.load_default()


try:
    # Get the current python path for text files
    pypath = os.path.realpath(sys.path[0])+'/'

    # Get the passed parameters in the command line
    trainArguments = sys.argv

    # Fail if no parameters found or less than 4
    if len(trainArguments) < 5:
        print("Error: Insufficient arguments", file=sys.stderr)
        print(f"Usage: {sys.argv[0]} <image_file> <text_file> <params_file> <YES|NO>", file=sys.stderr)
        sys.exit(3)  # Other error (usage)

    # Ok get the details
    imageFileName = trainArguments[1]
    trainTextFile = trainArguments[2]
    parametersFileName = trainArguments[3]
    departuresAvailable = trainArguments[4]

    if 'YES' in departuresAvailable:
        trainsFound = True
    else:
        trainsFound = False

    # Extract the standard parameters for the image from file
    # This file is used to communication between Indigo and this independant process
    # File format is:
    #   forcolour, bgcolour, isscolour, ticolour, cpcoloour, fontFullpath, fontFullPathTitle, fontSize,leftpadding,
    #   rightpadding, width, trainsfound, imageFileName, sourceDataName

    try:
        with open(parametersFileName, 'r') as paraFile:
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
    except (OSError, IOError) as e:
        print(f"Error reading parameters file '{parametersFileName}': {e}", file=sys.stderr)
        sys.exit(1)  # File I/O error
    except (IndexError, ValueError) as e:
        print(f"Error parsing parameters: {e}", file=sys.stderr)
        sys.exit(3)  # Other error (malformed parameters)

    # Ok now we need to extract the station for the departure board
    # Extract station and route timetable information

    try:
        with open(trainTextFile, 'r') as routeInfo:
            stationTitles = routeInfo.readline()
            stationStatistics = routeInfo.readline()
            timeTable = ''
            for line in routeInfo:
                timeTable = timeTable + '\n' + line.rstrip('\n')
    except (OSError, IOError) as e:
        print(f"Error reading text file '{trainTextFile}': {e}", file=sys.stderr)
        sys.exit(1)  # File I/O error

    # Converts timeTable array into a departure board image for display
    # Work out formatting characters
    REPLACEMENT_CHARACTER = 'ZZFZ'
    NEWLINE_REPLACEMENT_STRING = ' ' + REPLACEMENT_CHARACTER + ' '

    # Get the fonts for the board
    fontFullPath = pypath+'BoardFonts/MFonts/Lekton-Bold.ttf' # Regular
    fontFullPathTitle = pypath+'BoardFonts/MFonts/sui generis rg.ttf' # Bold Title
    fontCallingPoints = pypath+'BoardFonts/MFonts/Hack-RegularOblique.ttf' # Italic

    # Get the font for the image.  Must be a mono-spaced font for accuracy
    font = load_font_safe(fontFullPath, fontsize + 4, "regular")
    titleFont = load_font_safe(fontFullPathTitle, fontsize + 12, "title")
    statusFont = load_font_safe(fontFullPath, fontsize + 5, "status")
    departFont = load_font_safe(fontFullPath, fontsize + 8, "depart")
    delayFont = load_font_safe(fontFullPath, fontsize + 4, "delay")
    callingFont = load_font_safe(fontCallingPoints, fontsize + 2, "calling")
    messagesFont = load_font_safe(fontCallingPoints, fontsize, "messages")

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

        elif font.getlength(line + ' ' + word) <= (width - rightpadding - leftpadding):
            line += ' ' + word

        else:  # start a new line because the word is longer than a line
            # Line splitting now managed in main code
            continue

    if len(line) != 0:
        lines.append(line[1:])  # add the last line

    # Calculate image proportions
    # getsize() removed in Pillow 10.x - use getbbox() instead
    bbox = font.getbbox(timeTable)
    line_height = bbox[3] - bbox[1]  # bottom - top
    img_height = line_height * (30)
    line_height = int(line_height/1.5+0.5)

    if not trainsFound:
        img_height = line_height * (30)

    # Draw the blank image
    try:
        img = Image.new("RGBA", (width, img_height), bgcolour)
        draw = ImageDraw.Draw(img)
    except ValueError as e:
        print(f"PIL error creating image: {e}", file=sys.stderr)
        sys.exit(2)  # PIL error
    except Exception as e:
        print(f"Unexpected error creating image: {e}", file=sys.stderr)
        sys.exit(2)  # PIL error

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

    # Save PNG with optimization
    try:
        img.save(imageFileName, 'png', optimize=True)
        sys.exit(0)  # Success
    except OSError as e:
        print(f"Error writing PNG file '{imageFileName}': {e}", file=sys.stderr)
        sys.exit(1)  # File I/O error
    except Exception as e:
        print(f"Unexpected error saving PNG: {e}", file=sys.stderr)
        sys.exit(3)  # Other error

except Exception as e:
    print(f"Unexpected error in image generation: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(3)  # Other error
