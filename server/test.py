#trying to be flexible enough for portability between SBC and MCU.
#speed vs mem? neither platform has a lot of threads to work with,
#and if all tasks are in series then each task gets to use all the ram...
#so they should be faster and can take more mem.
#(microdot also seems opinionated in favor of async)

from microdot import Microdot, send_file, Request
import asyncio
import os
import subprocess
import csv

import metadata


#returns [path, metadata1, ..] (currently only metadata is timestamp)
def convert(path):
    if server_conversion:
        subprocess.run('./converter/venv/bin/python', f'convert.py {path}')
    else:
        print('todo: wasm/js can convert files in browser as user picks them for upload')


#def client_convert():


@app.route('/uploader')
async def index(request):
    return send_file('uploader.html')
@app.post('/upload')
async def upload(request):
  #  filename = request.headers['Content-Disposition'].split(
  #      'filename=')[1].strip('"')
    filename = request.headers['filename']
    size = int(request.headers['Content-Length'])
    path = 'working/'+filename
    print(path, size)

    # write the file to the files directory in 1K chunks
    with open(path, 'wb') as f:
        remaining = size
        while remaining > 0:
            chunk = await request.stream.read(min(remaining, 1024))
            f.write(chunk)
            remaining -= len(chunk)
    print(f'{filename} uploaded and written')

    #fire converter task upon upload and immediately enque task handle
    converter_handle = asyncio.create_task(process_image(filename))
    await insertion_q.put(converter_handle)

    return ''

async def insertion_listener(): #or "insertion consumer", from consumer/producer pattern
   while True:
       #exif = await (await insertion_q.get())
       nexttask = await insertion_q.get()
       metadata = (await nexttask)[meta.sortby] # how do i do what i want here
async def process_image(filename):
    #dont just get exif--let this task totally finish conversion
    await converter.convert(filename)
    exif = await converter.get_exif(filename)
    return myexiftostr(exif) #format like row in files.csv




# app.run(port=4000, debug=True)
#microdot example/gpio.weather has usage of a bg task running concurrently with micodot app.
async def start():
    insertion_listener_bgtask = asyncio.create_task(insertion_listener())
    server = asyncio.create_task(app.start_server(port=4000, debug=true))
    await asyncio.gather(server,insertion_listener_bgtask)

app = Microdot()

meta = metadata.Meta()
insertion_q = asyncio.Queue()

Request.max_content_length = 1024*1024
server_covnersion = True #convert files in browser or on device

asyncio.run(start())
