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

import pyudev
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
MNTPATH = '/mnt/ext/'
STORAGEPATH = '/var/lib/piframe-service'
#  useradd --system --no-create-home piframe-service
#  chown -R piframe-service:piframe-service /var/lib/piframe-service
#  ^(TODO also set systemd service up)

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

        the_settings = ['portrait','fill','light','60','forwards','ts','month','-5']
        if self.path:
            try:
                with open(self.path, 'r') as f:
                    the_settings = f.read().splitlines()
            except FileNotFoundError:
                pass
        ret:list[str|int] = list(the_settings) #list() is like strdup, helps type checker
        ret[3] = int(the_settings[3])
        ret[7] = int(the_settings[7])
        my_replace = lambda s: (
            s.replace('forwards', 'ASC') if s.endswith('forwards') else
            s.replace('backwards', 'DESC') if s.endswith('backwards') else
            'RANDOM()'
        )
        sorderby = 'ORDER BY '+my_replace(f'{the_settings[5]} {the_settings[4]}')
        ret.insert(6,sorderby)
        return ret


async def main():
    monitor.start()
    loop = asyncio.get_running_loop()
    #remember, this basically means poll_udev can run whenever evt loop is open
    loop.add_reader(monitor.fileno(), poll_udev)

    settings = Settings(os.path.join(MNTPATH, 'settings.txt'))
    #decent first time/bootup behavior: only do init() when storage path empty or nonexistent.
    #basically, user should always boot with a drive plugged in very first time. it might?? be safe to boot with nothing mounted and nothing in storage path--up to how init() copies; run() returning immediately should be ok in main while, and file exceptions in settings constructor is also safe.
    try:
        size = os.path.getsize(STORAGEPATH)
    except:
        size=0
    if size == 0:
        init(MNTPATH, STORAGEPATH, settings)
    while True:
        if dev_add_evt.is_set():
            dev_add_evt.clear()
            #mount device now
            subprocess.run(('mount', DEV, MNTPATH))
            #get settings & set up storage dir with converted files and db
            settings = Settings(os.path.join(MNTPATH,'settings.txt'))
            #convert images, save in storage dir, create db (sync init() call will probably take noticeable time)
            init(MNTPATH, STORAGEPATH, settings)
            #let init finish before unmount
            subprocess.run(('umount', DEV))
        await run(STORAGEPATH,settings)
def poll_udev():
    #runs whenever fd/socket representing udev events is readable (basically always?) and the asyncio event loop is available
    device = monitor.poll(timeout=0)
    if device and device.action == 'add':
        #for this project, theres only one possible device, the open rpi usb port
        dev_add_evt.set()
    #NOTE in a case where some blocking code is running, and user plugs in a device, that would cause the monitor reader to find an add once the blocking is done and the event loop is open. that's good but what if they plugged but quickly unplugged during the blocking? poll still finds add, evt is set, but drive isnt really there.

async def run(storagepath, settings:Settings):
    #async but note each line blocks except wait_for and the timeout

    #TODO on the fly inky 4 buttons: filter on (some in cycle), filter off (all in cycle), sort on (display next in order), sort off (display random next)
    display = inky.auto()
    conn = sqlite3.connect(os.path.join(storagepath, 'pics.db'))
    cursor = conn.cursor()

    squery = f'SELECT fname,ts FROM pics {settings.sorderby}'
    files:list[tuple[str,int]] = cursor.execute(squery).fetchall()
    i = 0
    while i < len(files):
        file:str = f'{files[i][0]}.PNG'
        fp:str = os.path.join(storagepath,file)
        ts:int = files[i][1]

        if filter(ts, settings.filtermode, settings.tz):
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
                pass

        i+=1
        if i >= len(files):
            i=0
def filter(ts:int,filtermode:str,tz:int):
    #filtering could be much more dynamic, instead i'm hardcoding day/month/season filtering

    # we dont store python datetimes in db.
    dt = datetime.fromtimestamp(ts, timezone(timedelta(hours=tz)))
    # datetime.fromtimestamp(datetime.now().timestamp(), timezone(timedelta(hours=-4))).strftime("%d %m %y %I:%M%p")
    cur_dt = datetime.now()
    cur = [cur_dt.day, cur_dt.month, my_dt_season(cur_dt)]
    if filtermode == 'day':
        return (cur[0] == dt.day) and (cur[1] == dt.month)
    elif filtermode == 'month':
        return cur[1] == dt.month
    elif filtermode == 'season':
        return cur[2] == my_dt_season(dt)
    else:
        return True
def my_dt_season(dt:datetime):
    if dt.month in [12, 1, 2]:
        return 1
    elif dt.month in [3, 4, 5]:
        return 2
    elif dt.month in [6, 7, 8]:
        return 3
    elif dt.month in [9, 10, 11]:
        return 4

def init(mntpath, destpath, settings:Settings):
    #indescriminately copy all image files to host disk (destpath) and convert them immediately after all copied.
    #also create sqlite db file.
    #limitation: if user has same filename in different dirs on their drive, the latest read one will overwrite. we arent doing multiple "albums" yet.
    #(regular sync function, does not get interrupted through copying or converting. there are some unsafe cases where bugs would appear like quickly unplugging, plugging, then unplugging again during conversions, which would set dev_add_evt since monitor sees an add when init finishes and evt loop is reopened, and the subproc mount would fail.. but why would you do that?)
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
            except OSError:
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
