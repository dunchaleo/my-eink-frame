#if we cant do server conversions, it means we're on a MCU that cant use pillow/advanced image library. since an MCU doesnt have an OS, we couldnt be calling a subprocess. so imo the converter is free to be a subprocess. it is also free to use thread pool executor. neither is available on micropython.


# conversion code modified from waveshare website
# get_exif_bytes() modified from saschiwy/heic_converter

import sys
import os.path
from PIL import Image, ImagePalette, ImageOps, ExifTags
from pillow_heif import register_heif_opener
from datetime import datetime
import piexif

#everyting in this file needs to be silent since it's subprocessed. debug logging has to be to a file.

def log(str):
    with open('.log','w') as log:
        log.write(str)

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

import time
log('heres some blocking in the body')
time.sleep(5)
log('this is the end')


#simulate an exif output ideally
import sys
import struct
#stdout 12-byte chunk for SFN, 255 for long, and unsigned int for timestamp
#(is SFN even a good idea?)
#out = struct.pack('12s255sI', b'SFN.JPG', b'longfilename.jpg',1770863679)
#doing this in C would mean stdout a char* and just know how to delimit it on the other side. so it's basically the same here:
out = struct.pack('12s255sI', b'SFN.JPG', b'longfilename.jpg',1770863679)
#meaning we arent unpacking the struct itself, but the stdout "stream"
sys.stdout.buffer.write(out)
