this is the easiest possible way to do this: inky impression python libs, linux on a SPC (pi zero 2 w). no web app, user plugs in flashdrive with pictures they want to display and a settings.txt. 
python handles device detection with pyudev, using a file descriptor reader (asyncio add_reader). script is set up as a systemd service.
image converstions are all (re)done & a sqlite db is created *every time you plug in the drive*, for now there is no persistence on rebooting or saved state. conversions are synchronous, not interrupted. 

no multiple albums. since the inky impression comes with buttons, i put limited support for some on the fly settings changes that are not saved on reboot. 
