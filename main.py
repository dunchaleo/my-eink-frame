#!/usr/bin/env python3

import inky

import sys
import os
from pathlib import Path
import shutil
import time

from PIL import Image, ImagePalette, ImageOps, ExifTags
from pillow_heif import register_heif_opener
from datetime import datetime, timezone, timedelta
import piexif

import sqlite3

import asyncio
import subprocess

#notes on auto mounting and detecting device plug-ins:
#claude made example w/ pyudev + asyncio, i found a similar usage of that here:
#  https://github.com/foresto/joystickwake/blob/leave-github/joystickwake
#claude: "add_reader is asyncio's exposure of the reactor pattern"
#helpful: https://www.packtpub.com/en-us/product/nodejs-design-patterns-second-edition-9781785885587/chapter/1-welcome-to-the-nodejs-platform-1/section/the-reactor-pattern-ch01lvl1sec04

dev_add_evt = asyncio.Event()

context = pyudev.Context()
monitor = pyudev.Monitor.from_netlink(context)
monitor.filter_by(subsystem='block', device_type='partition')

DEV = '/dev/sda1'

class Settings:
    def __init__(self,path:str):
        self.path = path
        (
            self.orientation, self.mode, self.background,
            self.spf, self.direction, self.ssortcol, self.sorderby,
            self.filtermode, self.tz # no filtercol, only support preset filter modes w/ 'ts'
        ) = self.fread()

    def fread(self):
        #landscape/portrait
        #fill/fit/stretch
        #light/dark

        #int seconds per frame
        #forwards/backwards/random
        #str ssortcol (ts)

        #month/season/all
        #int utc offset hours (e.g. est/dst = -4/-5)

        if(self.path == ''):
            settings = ['portrait','fill','light','60','forwards','ts','month','-5']
        else:
            with open(self.path, 'r') as f:
                settings = f.read().splitlines()
        ret:list[str|int] = list(settings) #list() is like strdup, helps type checker
        ret[3] = int(settings[3])
        ret[7] = int(settings[7])
        my_replace = lambda s: (
            s.replace('forwards', 'ASC') if s.endswith('forwards') else
            s.replace('backwards', 'DESC') if s.endswith('backwards') else
            'RANDOM()'
        )
        sorderby = 'ORDER BY '+my_replace(f'{settings[5]} {settings[4]}')
        ret.insert(6,sorderby)
        return ret


async def main(mntpath, storagepath):
    loop = asyncio.get_running_loop()
    #remember, this basically means poll_udev can run between every line in main()
    loop.add_reader(monitor.fileno(), poll_udev)

    while True:
        #get settings #(move this, do whenever init() to be called)
        settings = Settings(os.path.join(mntpath,'settings.txt'))

        if dev_add_evt.is_set():
            dev_add_evt.clear()
            #mount device now
            my_mount() #aka subprocess.run udisksctl mount DEV
            #set up storage dir with converted files and db
            await init(mntpath, storagepath, settings) #NOTE, init() is still sync, so it needs to be run in a thread with run_in_executor
            #  (although it could just stay sync and block, big deal? biggest problem add_reader's callback either finds multiple adds or only sees the most recent add? it just wont trigger until init() finishes)

            #udisksd should have auto mounted drive. unmount it after init()
            subprocess.run(('udisksctl', 'unmount', '-b', DEV))
        await run(storagepath,settings)
def poll_udev():
    #runs whenever fd/socket representing udev events is readable (basically always?) and the asyncio event loop is available
    device = monitor.poll(timeout=0)
    if device and device.action == 'add':
        #for this project, theres only one possible device, the open rpi usb port
        device_event.set()


async def run(storagepath, settings:Settings):
    #async but note each line blocks except wait_for and the timeout

    #TODO on the fly inky 4 buttons: filter on (some in cycle), filter off (all in cycle), sort on (display next in order), sort off (display random next)
    display = inky.auto()
    conn = sqlite3.connect(os.path.join(storagepath, 'pics.db'))
    cursor = conn.cursor()
    conn.create_function('FILTER',3, sqlite_filter)
    squery = f'SELECT fname FROM pics WHERE FILTER(ts, \'{settings.filtermode}\', {settings.tz}) {settings.sorderby}'
    i=-1
    while True:
        #really bad design doing this query every time :^)
        files:list[tuple[str,]] = cursor.execute(squery).fetchall()
        if(i >= len(files)):
            i=0
        else:
            i+=1

        file:str = f'{files[i][0]}.PNG'
        fp = os.path.join(storagepath,file)
        with Image.open(fp) as image:
            display.set_image(image)
            display.show()

        try:
            #we "want" this to raise timeout err for normal operation.
            #(event flag toggles (drive plugged in), Event.wait() returns, we quit run()).
            await asyncio.wait_for(dev_add_evt.wait(), settings.spf)
            return ''
        except asyncio.TimeoutError:
            #SPF seconds passed
            continue
def sqlite_filter(col,filtermode,tz):
    #hardcode my #1 desired feature:
    #return t if timestamp month is current month right now
    #could make this more performant by returning ranges of timestamps given desired month, corresponding to e.g. december of every year for the last 50 years (100 vals) and then sql could check if col is within ranges[0]..ranges[1] or within ranges[2]..ranges[3] or ...

    # we dont store python datetimes in db.
    # TODO list of ranges. dont use datetime in here, cheating.
    dt = datetime.fromtimestamp(col, timezone(timedelta(hours=tz)))
    # datetime.fromtimestamp(datetime.now().timestamp(), timezone(timedelta(hours=-4))).strftime("%d %m %y %I:%M%p")
    if(filtermode == 'month'):
        if(dt.month == datetime.now().month):
            return 1
        else:
            return 0
    else:
        #season mode not implemented
        return 1

def init(mntpath, destpath, settings:Settings):
    #(for now, keep this regular sync function, does not get interrupted through copying or converting)
    #indescriminately copy all image files to host disk (destpath) and convert them immediately after all copied.
    #also create sqlite db file.
    #limitation: if user has same filename in different dirs on their drive, the latest read one will overwrite. we arent doing multiple "albums" yet.
    register_heif_opener()

    #first clear destpath
    shutil.rmtree(destpath)
    os.makedirs(destpath)

    #init sql, including creating db file.
    #(we dont really need sql, deleting/creating db every time fs is changed)
    conn = sqlite3.connect(os.path.join(destpath, 'pics.db'))
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE pics (fname TEXT PRIMARY KEY, ts INTEGER)')

    for root,dirs,files in os.walk(mntpath):
        for file in files:
            fp = os.path.join(root,file)
            destfp = os.path.join(destpath,file)
            try:
                shutil.copyfile(fp,destfp)
            except OSError as e:
                #break loop on first FileNotFoundError: probably means mnt point is empty (drive unplugged)
                #(also, copyfile might have failed but still written to destfp--get rid of it)
                if os.path.isfile(destfp):
                    os.remove(destfp)
                break

    for file in os.listdir(destpath):
        fp = os.path.join(destpath,file)
        with Image.open(fp) as image:
            converted = convert(image, settings.orientation, settings.mode, settings.background)
            my_date = get_date(image.getexif(), True)
            #get something like destpath/image.heic.PNG
            converted.save(fp, 'PNG')
            #write record to db. pk fname doesnt need png ext
            cursor.execute('INSERT OR REPLACE INTO pics (fname, ts) VALUES (?, ?)',
                            (file, int(my_date.timestamp()))) #NOTE could use f-strings here the same way. affects when they eval?

    conn.commit()
    conn.close()

#some of this originally from waveshare website and saschiwy/heic_converter
def convert(input_image:Image.Image,o,m,b) -> Image.Image:

    if(b == 'light'):
        display_background = (255,255,255)
    else:
        display_background = (0,0,0)

    # force rgb/a
    if input_image.mode == "CMYK":
        input_image = input_image.convert("RGB")
    if input_image.mode not in ("RGB", "RGBA", "L", "P"):
        input_image = input_image.convert("RGBA")

    # actually rotate exif rotation
    input_image = ImageOps.exif_transpose(input_image)

    #target w,h is always 800x480
    if(o == 'portrait'):
        input_image = input_image.transpose(Image.Transpose(ROTATE_270))

    #(done pre processing/transposing)

    width, height = input_image.size
    target_width = 800
    target_height = 480
    scale = max(target_width/width, target_height/height)

    #crop from center
    if m == 'fill':
        new_width = int(width*scale)
        new_height = int(height*scale)
        temp_image = input_image.resize((new_width,new_height), Image.LANCZOS)
        left = (new_width - target_width) // 2
        top = (new_height - target_height) // 2
        right = left + target_width
        bottom = top + target_height
        target_image = temp_image.crop((left,top,right,bottom))
    elif m == 'fit':
        # content_scale = min(1/scale[0],1/scale[1])
        # temp_image = input_image.resize((int(width*content_scale),int(height*content_scale)), Image.Resampling.LANCZOS) #ImageOps.scale cant use fancy resampling
        # #padding to concat: padding = (target_height - temp_image.size[0], target_width - temp_image.size[1])
        # target_image = ImageOps.pad(temp_image, (target_width,target_height), color=display_background) #TODO test padding methods other than pad
        #(imageops pad scales+pads+centers already?)
        target_image = ImageOps.pad(
            input_image,
            (target_width, target_height),
            method=Image.Resampling.LANCZOS,
            color=display_background
        )
    elif m == 'stretch':
        target_image = input_image.resize((target_width,target_height))
    return target_image

#from saschiwy/heic_converter
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

#(on every draw): if filter() draw(file)
#  (desired application: filter = fn(ts){ true if ts' season is real season now })

#or query every draw??
#  for i=0; i<max; i++, if(i==max-1) i = 0;
#     list = select * from files where filter() sort by sortcol asc
#     i = i % len(list) #is this all it needs?
#     draw(list[i][0])
