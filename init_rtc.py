#set rtc from internet
#(tip: ``sudo timedatectl set-ntp false && sudo timedatectl set-ntp true'' on systemd distros to set time from internet based on os locales)
#but basically for this project, try to use python to replace os stuff for portability/simplicity.
#this should only need to run once ever. in main, we assume rtc is right.

#NOTE could use ZoneInfo() instead! timezone objects can nicely handle DST (via TZ.utcoffset(), which fromtimestamp() calls from its second arg on its first arg), but timezone(timedelta()) is a constant timezone (.utcoffset() always tz). however, since we are prototyping for embedded, not caring about dst is probably good enough!

import sys
from datetime import datetime, timezone
import ntplib

from waveshare_DS3231 import DS3231

tz = sys.argv[1]
try:
    # Connect to a public pool of NTP servers
    client = ntplib.NTPClient()
    response = client.request('pool.ntp.org', version=3)

    cur_dt = datetime.fromtimestamp(response.tx_time, tz)
    #print(f'time now: {cur_dt}')

except Exception as e:
    print("Failed to fetch time from NTP:", e)
    sys.exit(1)

RTC = DS3231.DS3231(add=0x68)
RTC.SET_Hour_Mode(24)
RTC.SET_Time(cur_dt.hour, cur_dt.minute, cur_dt.second)
RTC.SET_Calendar(cur_dt.year, cur_dt.month, cur_dt.day)
RTC.SET_Day(cur_dt.weekday())

sys.exit(0)
