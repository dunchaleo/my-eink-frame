#runs on udev device insertion trigger, or first bootup.

import os

system = os.system("findmnt -n -o SOURCE") #/dev/mmcblk0 on rpi sdcard /

names = open(".blk_devices.txt").read().splitlines() #devices from last udev trigger

newnames = os.system("lsblk -d -o NAME,MOUNTPOINT").splitlines()
