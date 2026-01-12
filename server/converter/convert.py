# originally from waveshare website

# this doesn't need to be python. but i dont know how tied down i am to
# pimoroni's python library for their inky displays! i've been able to find python and even
# rust libraries for waveshare e-ink, but the inky still looks higher quality...
# (actually, waveshare's supplied driver lib is also python)
# either way, it definitely needs to be high level because of how modern image files are..
# so for an esp32-only version that downloads from a physically separate server, this conversion should
# happen on that server.
# maybe dithering could still be done on embedded device given highly regular/homogenous input image data.

import sys
import os.path
from PIL import Image, ImagePalette, ImageOps, ExifTags
import argparse
from pillow_heif import register_heif_opener
from datetime import datetime
import piexif

register_heif_opener()

def main(f, o, m, b): #see args
    if(b == 'light'):
        display_background = (255,255,255)
    else:
        display_background = (0,0,0)

    # Check whether the input file exists
    if not os.path.isfile(f):
        print(f'Error: file {f} does not exist')
        sys.exit(1)

    # read input image
    input_image = Image.open(f)
    # get data about the image: dimensions for use in converter,
    # and save the exif to tack back on after conversion.
    width, height = input_image.size
    exif_bytes = get_exif_bytes(input_image)

    # specify target size
    if o == 'landscape':
        target_width, target_height = 800, 480
    elif o == 'portrait':
        target_width, target_height = 480, 800

    #scale of source relative to target
    scale = (width / target_width, height / target_height)
    factor = min(scale[0],scale[1])

    # 4 cases:
    # source img x > target x,
    #  target x > source img x;
    # source img y > target y,
    #  target y > source img y.
    # a wide image whose dims are > 800,480 is a very common case for example.
    # we can take care of some edge cases by first ensuring source dims always >= target dims:
    if factor<1:
        #directly change input_image, reset info. this shouldnt happen for most cases.
        input_image = ImageOps.scale(input_image, 1/factor) #scale up
        width, height = input_image.size
        scale = (width / target_width, height / target_height)
        factor = min(scale[0],scale[1])

    if m == 'fill':
        #crop from center
        #NOTE this option is likely to be insufficent for any modern camera: it will be too zoomed in.
        #  could do a trial-and-error repeated dims-check-and-adjust until right-ish upfront, then invoke pillow
        left = (width - target_width) // 2
        top = (height - target_height) // 2
        right = (width + target_width) // 2
        bottom = (height + target_height) // 2
        target_image = input_image.crop((left,top,right,bottom))
    elif m == 'fit':
        content_scale = min(1/scale[0],1/scale[1])
        temp_image = input_image.resize((int(width*content_scale),int(height*content_scale)), Image.Resampling.LANCZOS) #ImageOps.scale cant use fancy resampling
        #padding to concat: padding = (target_height - temp_image.size[0], target_width - temp_image.size[1])
        target_image = ImageOps.pad(temp_image, (target_width,target_height), color=display_background) #TODO test padding methods other than pad
    elif m == 'stretch':
        target_image = input_image.resize((target_width,target_height))

    #target_image.save("output.bmp", exif=exif_bytes) #uh oh, bmps dont have exif
    target_image.save("output.jpg", "jpeg", exif=exif_bytes, quality=100)
    print('Successfully converted?' )

# function credit: saschiwy/heic_converter
# (unique deps: piexif, datetime, ExifTags)
def get_exif_bytes(image):
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
            print(f'No EXIF data found for {source_file}, creating dummy EXIF data')

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

parser = argparse.ArgumentParser(description='--orientation: landscape/portrait  --mode: fill/fit/stretch  --background: light/dark')
# add and read orientation/mode args
parser.add_argument('image_file', type=str, default='input.jpg', help='Input image file')
parser.add_argument('--orientation', choices=['landscape', 'portrait'], help='Image direction (landscape or portrait)')
parser.add_argument('--mode', choices=['fill', 'fit', 'stretch'], default='fit', help='Image framing mode (fill (crop), fit, or stretch (resize))')
parser.add_argument('--background', choices=['light','dark'], default='light', help='Background color (light or dark) (only matters if \'--mode fit\')')
#args = parser.parse_args()    # uncomment!!

#main(args.image_file, args.orientation, args.mode, args.background)


#notes misc
#emacs: (pipenv-activate) found the venv correctly, comint repl just works
#  (it might have been (pyvenv-activate "dir" that did it??)
#in python repl, `import sys\n print(sys.executable)`
#`import filename` to source this file from repl
#filename.main('input.jpg', 'landscape', 'fit', 'dark')
