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

    asyncio.create_task(convert_and_insert(filename,size))

#WIP

    meta.insert(future)
    return ''
async def testconvert(filename, size):
    # the point of this test is to show that if large filesize => long conversion time, the conversions will finish in the order of filesize.
    # it's a bad test because task A could have longer run time than task B, but A returns first because it was fired first
    time = (size/239024)*10 #normalized size (max is 239024) to 10
    print(f'\t\t\t\t\t\t\t\033[92m async task started--{time}\033[0m')
    await asyncio.sleep(time)
    print(f'\t\t\t\t\t\t\t\033[91m async task returned: converted {filename} of size {size}\033[0m')
async def convert_and_insert(filename, size):
    time = (size/239024)*10 #normalized size (max is 239024) to 10
    print(f'\t\t\t\t\t\t\t\033[92m async task started (debug: {time})\033[0m')
    converter_handle = await asyncio.sleep(time) #await convert(filename) #conversion time
    insertion_queue.put(converter_handle) #declare promise and enque it in the global insertion queue

    print(f'\t\t\t\t\t\t\t\033[91m async task returned: converted {filename} of size {size}\033[0m')
async def consume_staged_insertions():
    while True:
        nextfile = insertion_queue.get()
        if(nextfile):



app = Microdot()

meta = metadata.Meta()
insertion_queue = asyncio.Queue()

Request.max_content_length = 1024*1024
server_covnersion = True #convert files in browser or on device

app.run(port=4000, debug=True)
