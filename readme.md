
# Table of Contents

1.  [links](#org55d391b)
    1.  [solutions](#org8dd43f6)
    2.  [relevant software](#org7931197)
2.  [idea](#org61f00ad)
        1.  [for now](#org57dbfd6)


<a id="org55d391b"></a>

# links


<a id="org8dd43f6"></a>

## solutions

-   <https://www.waveshare.com/wiki/PhotoPainter_(B)>
    -   waveshare has good software and guides, converting/dithering scripts, etc. photopainter works as-is, can be reflashed etc.
-   <https://www.youtube.com/watch?v=9gdemeaTfyI>
    -   china in general seems to have solved the e-ink picture frame many times already. they prefer small embedded devices to run them. some stuff from seeed/waveshare looks vibe coded though.
-   the western way of doing this seems to be with pimoroni&rsquo;s inky line of e-ink displays (NOTE see inkplate). they are not as based, and pi-only, and have a python library. they are probably easier to set up.
    -   <https://github.com/pimoroni/inky>
    -   <https://www.reddit.com/r/raspberry_pi/comments/1pictby/e_ink_picture_frame/>
-   <https://www.youtube.com/watch?v=L5PvQj1vfC4>
    -   heres somebody using a full pi zero and the inky display to accomplish something close to what i want
-   <https://github.com/mehdi7129/inky-photo-frame>
    -   heres somebody who vibe coded something for pi zero + inky, maybe it &ldquo;just works&rdquo;? not ideal uploading (smb)
-   heres somebody with a pretty elegant method, using a non-pimoroni display (not dependent on their python lib) and opting for a plug-in sd card. still using a full pi though.
    -   <https://www.youtube.com/watch?v=lWrWu7VYAFQ>
    -   <https://github.com/EnriqueNeyra/eInkFrame>
-   <https://github.com/FrameOS/frameos>
    -   frameos seeems to make a point of &ldquo;plug and play&rdquo; for ANY type of display, relies on webserver + web ui. frameos CAN run on the same pi zero that&rsquo;s driving the frame, but MUST have a pi to be driving the frame.
-   <https://kyle.cascade.family/posts/an-eink-family-calendar/>
    -   this guy got around the issue of how/where to use a server by doing all image conversions/generation/hosting on his router (all in go), so they can be fetched whenever. `online_image` in esphome is used to get image data from url but home assistant is not running at all. all the hard stuff is done in the go code.
-   <https://soldered.com/product/inkplate-6color-e-paper-display/>
    -   someone pointed out inkplate. similar to waveshare/seeed (but solderedelectronics is EU) they have almost fully &ldquo;done&rdquo; projects
    -   displays sold with esp32 and pre flashed firmware which can do dithering and resizing(!? and converting?). cons: only 1 small color display.


<a id="org7931197"></a>

## relevant software

-   <https://github.com/waveshareteam/e-Paper/tree/master/RaspberryPi_JetsonNano/python/lib/waveshare_epd>
    -   original waveshare python driver lib
    -   rust and go versions???
        -   <https://github.com/nii236/go-waveshare-epaper>
        -   <https://github.com/caemor/epd-waveshare>
-   pimorini
    -   <https://github.com/pimoroni/inky>
        (original inky python driver lib)
    -   *third-party* circuitpython inky drivers <https://github.com/bablokb/circuitpython-inky>
        -   q: how similar are they to inkplate&rsquo;s micropython drivers?
        -   only 7.5 spectra 6 supported?? what about the older non s6 13 inch??
    -   pimorini also has a product called inky-frame, largest 7in. includes pi pico.
        -   [main driver seems to be pico graphics](https://github.com/pimoroni/pimoroni-pico/blob/main/micropython/modules/picographics/README.md#supported-displays) which dont support inky impression&#x2026; main inky-frame github page makes point about micropython having ~190k ram and drawing to 7in display takes 150k. i still think embedded would be better if the problems of user uploads and image manipulation was solvable that way
-   frameos&rsquo; drivers are all python too
    -   <https://github.com/FrameOS/frameos/tree/main/backend/app/drivers>
-   but inkplate is micropython designed for esp32
    -   <https://github.com/SolderedElectronics/inkplate-micropython>
    -   bring your own server (q: any examples where people have used inkplate w esp32 http server?)
-   (hardware)
    -   helpful thread:<https://forums.pimoroni.com/t/how-to-connect-pico-to-inky-impression-7-3/24715/9>


<a id="org61f00ad"></a>

# idea

the inky python library is not for micropython/circuitpython. so you have to use a full pi, not an esp32 or pi pico (though the reddit guy got that to work).
i still dont know how the chinese way works; it&rsquo;s less clear but it seems to be better in some ways.
maybe compromise with 2 main options:

-   have to keep it powered all the time: pi zero on the frame can be running a server all the time, users can connect to it and upload pictures and change settings.
-   battery powered: esp32/pico can be programmed to read data from sd/usb drive (maybe can accept any formatting, and can also take care of image conversion (or not, image data might need to be highly regular coming in)) but it&rsquo;s up to the user to prepare the drive with pictures first.
-   (third option): battery powered but networked, there has to be another server running that sends data to the frame (like the reddit guy)


<a id="org57dbfd6"></a>

### for now

commit to the pi zero, try to make it easy to redo on esp32. avoid bash scripts etc. make efforts to keep power consumption low but lean towards it being plugged in.
most importantly, commit to an http server being run on the device and doing lan wifi, user should be able to log in on browser on phone and upload pics bare minimum.
theres still a ton of different possible implementation details/configurations from that.
also probably a really bad idea to have the thing driving the frame do the image conversions. needs to be a server backend job (which happens to be the same rpi zero driving the frame) or could even make client do it (webasm, you can do pillow in piodide).

