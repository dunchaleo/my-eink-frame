##  maybe ?????

#IDEA: 2 devices connected by ethernet, one a rpi/SPC and the other an
#esp32/MCU. would need to find some solution for powering them together. MCU
#could drive the frame, and would be able to make requests over the wired
#interface to download all the pics. could make this client control when the
#server shuts down () . as soon as these requests finish, the process for
#driving the frame can finally start and run indefinitely.
#easy mode: frame-driver and server must be the same device and share flash
#storage. no more transferring needed.

#on an esp32, this file may be on its own partition? device can reboot into this
#firmware when user toggles hardware switch (turns "configuration mode" on) and
#can be set to reboot into the frame driving firmware when requests finish.

#in support of this idea: downloader client/driver can implement a "select where
#date" (simple, no sqlite, a more proper version would be like an album
#combiner/new album maker, which would also involve being a client)

host = "127.0.0.1"
driver_fs = "../driver/" #running this file from [project]/server/ right now
