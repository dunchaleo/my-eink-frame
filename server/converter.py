### credits
# conversion code modified from waveshare website
# build_exif_dict and get_date() modified from saschiwy/heic_converter

#if we cant do server conversions, it means we're on a MCU that cant use pillow/advanced image library. since an MCU doesnt have an OS, we couldnt be calling a subprocess. so imo the converter is free to be a subprocess. it is also free to use thread pool executor. neither is available on micropython.

#everyting in this file needs to be silent since it's subprocessed. debug logging has to be to a file.

import sys
import os
from pathlib import Path
from PIL import Image, ImagePalette, ImageOps, ExifTags
from pillow_heif import register_heif_opener
from datetime import datetime
import piexif
import struct
#import contextlib #suppress stdout

def log(str):
    with open('.log','a+') as log:
        log.write(f'converter.py\t{str}')


# the image conversion isnt my main focus so this is probably bad or inefficient, but it's subprocessed so can just swap for anything
def convert(input_image:Image.Image,o,m,b) -> Image.Image:
    # force rgb/a
    if input_image.mode == "CMYK":
        input_image = input_image.convert("RGB")
    if input_image.mode not in ("RGB", "RGBA", "L", "P"):
        input_image = input_image.convert("RGBA")
    # actually rotate exif rotation
    input_image = ImageOps.exif_transpose(input_image)

    if(b == 'light'):
        display_background = (255,255,255)
    else:
        display_background = (0,0,0)
    width, height = input_image.size
    # always 800x480, we dont want to give the display driver the job of orientation. the converter should be outputting sideways images when o = 'portrait'
    target_width = 800
    target_height = 480

    target_image = input_image.resize((target_width,target_height))
    return target_image

#not really using this at all right now
#might have been better for converter.py subprocess to stdout this as a dict in raw bytes. right now, converter subproc is not agnostic to the structure of files.csv. could have handled that in master proc instead. but it's fine
def build_exif_dict(image_info, date:datetime): #image.info attribute

    # Try to load existing exif data via piexif
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
    try:
        if "exif" in image_info:
            exif_dict = piexif.load(image_info["exif"])
    except:
        # If loading fails, use our default structure
        pass

    # Update exif data with orientation and datetime
    exif_dict["0th"][piexif.ImageIFD.DateTime] = date.strftime("%Y:%m:%d %H:%M:%S")
    exif_dict["0th"][piexif.ImageIFD.Orientation] = 1

    # Add dummy author data to ensure EXIF is not empty
    exif_dict["0th"][piexif.ImageIFD.Artist] = "unknown"

    # Ensure the Exif IFD exists and add a dummy entry if needed
    if not exif_dict.get("Exif"):
        exif_dict["Exif"] = {}

    #exif_bytes = piexif.dump(exif_dict)
    #return exif_bytes
    return exif_dict

#for use in build_exif_dict and writing bytes to stdout
def get_date(image_exif, verbose=False) -> datetime:
    if image_exif:
        # Make a map with tag names and grab the datetime
        exif = {ExifTags.TAGS[k]: v for k, v in image_exif.items() if k in ExifTags.TAGS and type(v) is not bytes}
        if 'DateTime' in exif:
            date = datetime.strptime(exif['DateTime'], '%Y:%m:%d %H:%M:%S')
        else:
            date = datetime.now()

    else:
        # No EXIF data exists, use current datetime
        date = datetime.now()
        if verbose:
            log(f'No EXIF data found for image\n')

    return date

def main(f, o, m, b, file_format_str, ret=False):
    register_heif_opener()
    path = f'./working/{f}' #hardcode upload path
    outpath = f'./storage/{f}.png' #hardcode storage path

    with Image.open(path) as image:
        log(f'converting: {f} {o} {m} {b}\n')
        my_date = get_date(image.getexif(), True)
        converted = convert(image, o, m, b)
        converted.save(outpath, format='PNG')

    #write bytes: here, make sure that Meta.insert() can read output bytes. data must be structured like a row in files.csv
    #(struct.pack() needs bytes objs rather than py strs)
    out_bytes = struct.pack(file_format_str, f.encode('utf-8'),int(my_date.timestamp))
    if(ret):
        return out_bytes

if __name__ == '__main__':
    main(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5])
