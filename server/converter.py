### credits
# conversion code modified from waveshare website
# get_exif_bytes() modified from saschiwy/heic_converter


###
#if we cant do server conversions, it means we're on a MCU that cant use pillow/advanced image library. since an MCU doesnt have an OS, we couldnt be calling a subprocess. so imo the converter is free to be a subprocess. it is also free to use thread pool executor. neither is available on micropython.

#everyting in this file needs to be silent since it's subprocessed. debug logging has to be to a file.

import sys
import os.path
from PIL import Image, ImagePalette, ImageOps, ExifTags
from pillow_heif import register_heif_opener
from datetime import datetime
import piexif
#import contextlib #suppress stdout

def log(str):
    with open('.log','a+') as log:
        log.write(f'converter.py\t{str}')

# (unique deps: piexif, datetime, ExifTags)
# tries to copy exif via piexif first, but failing that (e.g. if png or tiff?) it still specifically extracts the datetime and builds its own exif dict.
def get_exif_bytes(path, verbose:bool = False):
    image = Image.open(path)
    image_exif = image.getexif()

    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

    if image_exif:
        # Make a map with tag names and grab the datetime
        exif = {ExifTags.TAGS[k]: v for k, v in image_exif.items() if k in ExifTags.TAGS and type(v) is not bytes}
        if 'DateTime' in exif:
            date = datetime.strptime(exif['DateTime'], '%Y:%m:%d %H:%M:%S')
        else:
            date = datetime.now()

        # Try to load existing exif data via piexif
        try:
            if "exif" in image.info:
                exif_dict = piexif.load(image.info["exif"])
        except:
            # If loading fails, use our default structure
            pass
    else:
        # No EXIF data exists, use current datetime
        date = datetime.now()
        if verbose:
            log(f'No EXIF data found for {image.filename}, creating dummy EXIF data')
    # Update exif data with orientation and datetime
    exif_dict["0th"][piexif.ImageIFD.DateTime] = date.strftime("%Y:%m:%d %H:%M:%S")
    exif_dict["0th"][piexif.ImageIFD.Orientation] = 1

    # Add dummy author data to ensure EXIF is not empty
    exif_dict["0th"][piexif.ImageIFD.Artist] = "unknown"

    # Ensure the Exif IFD exists and add a dummy entry if needed
    if not exif_dict.get("Exif"):
        exif_dict["Exif"] = {}

    exif_bytes = piexif.dump(exif_dict)
    return exif_bytes

def exif_to_csv(path):
   return string(get_exif_bytes)


#simulate an exif output ideally
import sys
import struct
import time
log(f'the input args are {sys.argv} (file, orientation, mode, background)')
log('heres some blocking in the body\n')
#stdout 255 byte chunk for filename, and unsigned int for timestamp. + more ?
#doing this in C would mean stdout a char* and just know how to delimit it on the other side. so it's similar here:
out_bytes = struct.pack('@255sI', b'filename.jpg',1770863679)
sum(range(30000000*len(sys.argv[1])))
log('this is the end of the blocking\n')
sys.stdout.buffer.write(out_bytes)
