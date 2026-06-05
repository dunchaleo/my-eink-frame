#!/usr/bin/env python3

import sys
import os
import logging
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

#waveshare driver imports, following examples
import epaper
epd7in3e = epaper.epaper('epd7in3e')
from waveshare_DS3231 import DS3231
RTC = DS3231.DS3231(add = 0x68)

#notes on auto mounting and detecting device plug-ins:
#claude made example w/ pyudev + asyncio, i found a similar usage of that here:
#  https://github.com/foresto/joystickwake/blob/leave-github/joystickwake
#claude: "add_reader is asyncio's exposure of the reactor pattern"
#helpful: https://www.packtpub.com/en-us/product/nodejs-design-patterns-second-edition-9781785885587/chapter/1-welcome-to-the-nodejs-platform-1/section/the-reactor-pattern-ch01lvl1sec04

#for systemd logging to file
sys.stdout.reconfigure(line_buffering=True)


IMAGE_EXTS = {'.JPEG', '.JPG', '.PNG', '.GIF', '.SVG', '.WEBP', '.BMP', '.JFIF', '.HEIC'}

dev_add_evt = asyncio.Event()

context = pyudev.Context()
monitor = pyudev.Monitor.from_netlink(context)
monitor.filter_by(subsystem='block', device_type='partition')

try_init = True
#SPF_PWROFF_TOL = 1200 #past this SPF setting, poweroff after draw, rely on rtc for SPF to wake
SPF_PWROFF_TOL = sys.maxsize #(TODO implement this, probably need another/different rtc)

DEV = '/dev/sda1'
MNTPATH = '/mnt/ext/'
STORAGEPATH = '/var/lib/piframe-service/storage'

SETTINGS_FILENAME = 'settings.txt' #in root dir of removable media
VARS_FILENAME = '.vars'


class Settings:
    def __init__(self,path:str,power_threshold):
        self.N = 9 #const num of settings
        self.path = path
        self.power_threshold = power_threshold
        (
            self.orientation, self.mode, self.background,
            self.spf, self.direction, self.ssortcol, self.sorderby,
            self.filtermode, self.tz, # no filtercol, only support preset filter modes w/ 'ts'
            self.set_rtc, self.rtc_spf
        ) = self.fread()
        print([self.orientation, self.mode, self.background, self.spf, self.direction, self.ssortcol, self.sorderby, self.filtermode, self.tz, self.rtc_spf, self.set_rtc])

    def fread(self):
        #landscape/portrait
        #fill/fit/stretch
        #light/dark

        #int seconds per frame
        #forwards/backwards/random
        #str ssortcol (ts)

        #month/season/all
        #int utc offset hours (e.g. est/dst = -4/-5)

        #bool set rtc from internet

        the_settings = ['portrait','fill','light','60','forwards','ts','month','-5', 'true']
        if self.path:
            try:
                with open(self.path, 'r') as f:
                    the_read_settings = f.read().splitlines()
                    i = the_settings.len()
                    while i < self.N:
                        the_settings.append(the_read_settings[i])
                        i+=1
            except FileNotFoundError:
                pass
        #process the settings literals and return real settings object
        ret:list[str|int|bool] = list(the_settings) #list() is like strdup, helps type checker
        # adjust types
        ret[3] = int(the_settings[3])
        ret[7] = int(the_settings[7])
        # add sql query string order by
        my_replace = lambda s: (
            s.replace('forwards', 'ASC') if s.endswith('forwards') else
            s.replace('backwards', 'DESC') if s.endswith('backwards') else
            'RANDOM()'
        )
        sorderby = 'ORDER BY '+my_replace(f'{the_settings[5]} {the_settings[4]}')
        ret.insert(6,sorderby)
        # adjust SPF: if > poweroff threshold, set to 0. append real spf.
        ret.append(ret[3])
        if ret[3] >= self.power_threshold:
            ret[3] = 0
        return ret


async def main():
    monitor.start() #socket will start populating now
    loop = asyncio.get_running_loop()
    #remember, this basically means poll_udev can run whenever evt loop is open
    loop.add_reader(monitor.fileno(), poll_udev)

    set_time() #set os time from rtc

    #decent first time/bootup behavior: only do init() when storage path empty or nonexistent.
    #check for that here, but other path existence cases are handled inside settings constructor, init(), and run().
    #intended use: on very first boot, ensure drive plugged in. subsequent optional. you can hot swap a drive while on but not while off (have to trigger init() somehow)
    if os.path.exists(STORAGEPATH):
        settings = Settings(os.path.join(STORAGEPATH, SETTINGS_FILENAME), SPF_PWROFF_TOL)
        #modify said behavior slightly by allowing a bool setting to decide if init() should be run anyway providing there's a device already present before boot:
        if try_init:
           for device in context.list_devices(subsystem='block', device_type='partition'):
               if device.get('ID_FS_LABEL') == DEV:
                   dev_add_evt.set()
    else:
        dev_add_evt.set()
    # if try_init:
    #     for device in context.list_devices(subsystem='block', device_type='partition'):
    #         if device.get('ID_FS_LABEL') == DEV:
    #             dev_add_evt.set()
    # elif os.path.exists(STORAGEPATH):
    #     settings = Settings(os.path.join(STORAGEPATH, 'settings.txt'))
    # else:
    #     dev_add_evt.set()

    while True:
        print('main() loop')
        if dev_add_evt.is_set():
            dev_add_evt.clear()
            #mount device now (TODO: think abt race condition where drive disappears before here? i really think it's fine)
            subprocess.run(('mount', DEV, MNTPATH))
            #reset settings
            settings = Settings(os.path.join(MNTPATH,SETTINGS_FILENAME), SPF_PWROFF_TOL)
            #convert images, save in storage dir, create db (sync init() call will probably take noticeable time)
            print('init() call')
            init(MNTPATH, STORAGEPATH, settings)
            print('init() return')
            #let init finish before unmount
            subprocess.run(('umount', DEV))
        await run(STORAGEPATH,settings)
def poll_udev():
    #runs whenever fd/socket representing udev events is readable (basically always?) and the asyncio event loop is available.
    #(for this project, theres only one possible device, the open rpi usb port, but might still want to add checks like ``if device.get() == DEV'')


    #pyudev monitor is a stream, acts as a queue where poll() pop()s. build a history aka drain the socket, and check last action:
    events = []
    while True:
        device = monitor.poll(timeout=0) #timeout=0 never blocks, can return None (but shouldnt at first since this is the callback)
        if device:
            events.append(device.action)
        else:
            break #drained

    #cancel any pending debounce task
    if debounce_handle:
        debounce_handle.cancel()

    if events and events[-1] == 'add':
       dev_add_evt.set()
    #NOTE without drain+check, in a case where some blocking code is running, and user plugs in a device, that would cause the monitor reader to find an add once the blocking is done and the event loop is open. that's good but what if they plugged but quickly unplugged during the blocking? poll still finds add, evt is set, but drive isnt really there.

async def run(storagepath, settings:Settings):
    print('run() enter')
    #async but note each line blocks except wait_for and the timeout

    #TODO add some i2c buttons: filter toggle, sort toggle, force re-init

    conn = sqlite3.connect(os.path.join(storagepath, 'pics.db'))
    cursor = conn.cursor()

    squery = f'SELECT fname,ts FROM pics {settings.sorderby}'
    files:list[tuple[str,int]] = cursor.execute(squery).fetchall()

    print(files)
    i = get_resume_idx(storagepath)
    while i < len(files):
        print(f'run() loop: file idx {i}')

        epd = epd7in3e.EPD()
        epd.init() #^have to do this here? would rather have it at top of run()

        set_resume_idx(storagepath,i) #set now, not after waiting

        file:str = f'{files[i][0]}.PNG'
        fp:str = os.path.join(storagepath,file)
        ts:int = files[i][1]

        if filter(ts, settings.filtermode, settings.tz, verbose=True):
            print(f'run(): filter passed!')
            with Image.open(fp) as image:
                print(f'attempting draw {fp}')
                try: #this block from waveshare examples
                    epd.display(epd.getbuffer(image))
                    epd.sleep()
                except Exception as e:
                    print(f'waveshare err: {e}')
                    # Ensure proper cleanup
                    if hasattr(epd, 'epdconfig'):
                        epd.epdconfig.module_exit()
                    return ''
            try:
                #we "want" this to raise timeout err for normal operation.
                #(event flag toggles (drive plugged in), Event.wait() returns, we quit run()).
                await asyncio.wait_for(dev_add_evt.wait(), settings.spf)
                conn.close()
                if hasattr(epd, 'epdconfig'):
                    epd.epdconfig.module_exit()
                return ''
            except asyncio.TimeoutError:
                #SPF seconds passed
                pass

            if settings.spf == 0:
                handle_shutdown(i, settings.rtc_spf)

        if hasattr(epd, 'epdconfig'): #have to do this every iteration?
            epd.epdconfig.module_exit()

        i+=1
        if i >= len(files):
            i=0
            print('run() drew all files once')
def filter(ts:int,filtermode:str,tz:int, verbose=False):
    #filtering could be much more dynamic, instead i'm hardcoding day/month/season filtering

    # we dont store python datetimes in db.
    dt = datetime.fromtimestamp(ts, tz=timezone.utc) #have to pass utc tz obj to prevent conversion to os timezone. #NOTE is it common to have exif datetimes calculated from utc or other default, like a naive camera app? or if the camera's timezone is wrong but date is right? in that case, would i want to add geographical tz calc to get_date()? probably not, wouldnt matter much for month/season filtering, and bottom line if the camera is wrong about the date, thats outside the scope of any of these features.
    #(testing, ignore) datetime.fromtimestamp(datetime.now().timestamp(), timezone(timedelta(hours=-4))).strftime("%d %m %y %I:%M%p")
    cur_dt = datetime.now()
    cur = [cur_dt.day, cur_dt.month, my_dt_season(cur_dt)]
    if verbose:
        sdt = dt.strfmtime('%B %d, %Y %H:%M:%S')
        scur_dt = cur_dt.strfmtime('%B %d, %Y %H:%M:%S')
        print(f'format(): {sdt} @ {scur_dt}')
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
    #(regular sync function, does not get interrupted through copying or converting)
    print('init() enter')

    run_init_rtc(settings.set_rtc, settings.tz)

    #first clear destpath, preserving resume_idx
    resume_idx = get_resume_idx(destpath) #returns 0 if not found
    try:
        shutil.rmtree(destpath)
    except FileNotFoundError:
        pass
    os.makedirs(destpath)
    set_resume_idx(destpath,resume_idx)

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

    register_heif_opener()
    for file in os.listdir(destpath):
        if os.path.splitext(file)[1].upper() not in IMAGE_EXTS:
            #filtering here, we keep settings.txt and everything else in removable media
            print(f'init(): skip conversion of {file}')
            continue
        fp = os.path.join(destpath,file)
        with Image.open(fp) as image:
            print(f'init(): attempting convert {fp}')
            converted = convert(image, settings.orientation, settings.mode, settings.background)
            my_date = get_date(image.getexif(), True)
            #get something like destpath/image.heic.PNG
            converted.save(f'{fp}.PNG', 'PNG')
            #write record to db. pk fname doesnt need png ext
            squery_ins = f'INSERT OR REPLACE INTO pics (fname, ts) VALUES ({file}, {int(my_date.timestamp})'
            print(f'init(): sqlite: {squery_ins}')
            cursor.execute(squery_ins)

    conn.commit()
    conn.close()

def handle_shutdown(resume_idx, spf):
    #TODO write resume index to fs, shut down
#for get/set resume_idx, we want to read/write FS every time. that way, on power loss or manual shutdown, the position isn't lost
    return ''
def run_init_rtc(init_rtc:bool, tz:int):
    #set rtc from the internet
    subcall = [sys.executable, 'init_rtc.py', tz]
    subprocess.run(subcall)
def set_time():
    #for the rest of the program after calling this, can just rely on OS time as long as it gets set here, dont have to call DS3231 lib anywhere else.
    #TODO make sure raspios isnt fighting this by setting OS time itself
    #(instead, could also just use the raspios kernel driver, but this is more self contained)
    RTC.SET_Hour_Mode(24)
    RTC.Read_Calendar()
    t="%02x-%02x-%02x"%(RTC.Read_Year_BCD(),RTC.Read_Month_BCD(),RTC.Read_Date_BCD())
    subprocess.run("date -s %s"%(t))
    h="%x:%x:%x"%(RTC.Read_Time_Hour_BCD(),RTC.Read_Time_Min_BCD(),RTC.Read_Time_Sec_BCD())
    subprocess.run("date -s %s"%(h))
def get_resume_idx(path:str) -> int:
    try:
        with open(os.path.join(path,VARS_FILENAME), 'r') as file:
            return int(file.readline().strip())
    except:
        return 0
def set_resume_idx(path:str, idx:int):
    try:
        with open(os.path.join(path,VARS_FILENAME), 'w') as file:
            file.write(f'{idx}')
    except:
        pass



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
        input_image = input_image.transpose(Image.Transpose.ROTATE_270)

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

    #dithering
    # Create a palette object
    pal_image = Image.new("P", (1,1))
    pal_image.putpalette( (0,0,0,  255,255,255,  255,255,0,  255,0,0,  0,0,0,  0,0,255,  0,255,0) + (0,0,0)*249)
    # The color quantization and dithering algorithms are performed, and the results are converted to RGB mode
    quantized_image = target_image.quantize(dither=Image.Dither.FLOYDSTEINBERG, palette=pal_image).convert('RGB')

    #bandaid--driver is upside down
    quantized_image = quantized_image.transpose(Image.Transpose.ROTATE_180)

    return quantized_image

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
            print(f'No EXIF data found for image\n')

    return date



asyncio.run(main())
