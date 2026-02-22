#trying to be flexible enough for portability between SBC and MCU.
#speed vs mem? neither platform has a lot of threads to work with,
#and if all tasks are in series then each task gets to use all the ram...
#so they should be faster and can take more mem.
#(microdot also seems opinionated in favor of async)

from microdot import Microdot, send_file, Request
import asyncio
import os
import sys
import subprocess
import struct

import metadata

###global s

app = Microdot()

meta = metadata.Meta()

vis_args =metadata.Visuals.get_args(metadata.Visuals()) #to be improved
insertion_q = asyncio.Queue()

# if server_conversion:
# else:
#    print('todo: wasm/js can convert files in browser as user picks them for upload')

###routes

@app.route('/uploader')
async def index(request):
    meta.mwrite()
    #vis_args = metadata.Visuals().get_args() #to be improved
    return send_file('uploader.html')
@app.post('/upload')
async def upload(request):
  #  filename = request.headers['Content-Disposition'].split(
  #      'filename=')[1].strip('"')
    filename:str = request.headers['filename']
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

###coroutines

async def insertion_listener(): #or "insertion consumer", from consumer/producer pattern
   while True:
       #exif = await (await insertion_q.get())
       next_task = await insertion_q.get()
       #metadata = (await next_task)[meta.sortby] # i think this is valid syntax (dont need this, see Meta.compare)
       metadata = await next_task
       meta.insert(metadata)
async def process_image(filename):
    #(dont just get exif--let this task totally finish conversion).
    #let OS handle threads by making a subprocess. blocking code can be awaited. see comment in converter.py
    #TODO make i/o pipes instead of args?
    subcall = [sys.executable, 'converter.py', filename] + vis_args
    subproc = await asyncio.create_subprocess_exec(
        *subcall, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    #we'll get a byte obj (can it be streamed/chunked?) from converter.py, just needs to be serialized.
    stdout,stderr = await subproc.communicate()
    return decode_subproc_bytes(stdout)
async def start():
    insertion_listener_handle = asyncio.create_task(insertion_listener())
    server = asyncio.create_task(app.start_server(port=4000, debug=True))
    await asyncio.gather(server,insertion_listener_handle)

###helpers/misc
def decode_subproc_bytes(stdout):
    #dont want to be text-parsing so do struct pack/unpack. this gives you a multi-typed tuple.
    #tuples are immutable so copy it to a list and deal with trailing nulls:
    #TODO this is weird just make a fmt string ("@255sI") first and pass it into converter.py
    metadata =  struct.unpack('@255sI',stdout)
    list = [None]*len(metadata)
    i = 0
    for elt in metadata:
        if(type(elt) == type(b'')):
            list[i] = elt.rstrip(b'\x00').decode('utf-8')
        else:
            list[i] = elt
        i+=1
    return list

Request.max_content_length = 1024*1024
server_conversion = True #convert files in browser or on device

###init
#microdot example/gpio.weather has usage of a bg task running concurrently with micodot app.
#(async start() with multiple create_tasks, server being one of them--app.start_server() not app.run)
asyncio.run(start())
