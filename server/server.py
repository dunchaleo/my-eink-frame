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

###globals

app = Microdot()

meta = metadata.Meta()

vis_args = metadata.Visuals.get_args(metadata.Visuals()) #to be improved
insertion_q = asyncio.Queue()

###main routes

@app.route('/uploader')
async def index(request):
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
@app.get('/refresh_test')
async def refresh_test(request):
    meta.close()
    meta.mfree()
    meta.mwrite()
    return ''

###debug routes

@app.get('/show_test')
async def show_metadata_object(request):
    print(meta.files)
    print(meta.ordering)
    print(list(meta.file_stream()))
@app.post('/call_meta_method')
async def call_meta_method(request):
    print('pressed')
    text = request.body.decode().strip()
    parts = text.split()
    name = parts[0]
    args = parts[1:]
    args_typed = [eval(i) for i in args]
    print(f'{name} {args_typed}')
    func = getattr(meta, name)
    res = func(*args_typed)

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
    file_format_str = struct_format_str(len(filename))
    subcall = [sys.executable, 'converter.py', filename, *vis_args, file_format_str]
    subproc = await asyncio.create_subprocess_exec(
        *subcall, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    #serialize stdout stream:
    stdout,stderr = await subproc.communicate()
    metadata = struct.unpack(file_format_str,stdout) #unpack returns multi-typed tuple
    #(subproc needs to write equivalent of one row of files.csv to stdout as bytes)
    return metadata
async def start():
    insertion_listener_handle = asyncio.create_task(insertion_listener())
    server = asyncio.create_task(app.start_server(port=4000, debug=True))
    await asyncio.gather(server,insertion_listener_handle)

###helpers/misc

#returns the format string used for binary communication with subprocess. it is structurally equivalent to one row of files.csv. for now, it's just '@{len}sQ' for filename,timestamp ('Q': ULL, 8 bytes)
def struct_format_str(length) -> str:
    return f'@{length}sQ'

###setup
Request.max_content_length = 50*1024*1024 #might want to cave and force browser to do some compression
server_conversion = True #convert files in browser or on device
meta.bin_fmt_str = struct_format_str(255) #for writing files.bin, fixed length records.
###init
if(server_conversion):
    #microdot example/gpio.weather has usage of a bg task running concurrently with micodot app.
    #(async start() with multiple create_tasks, server being one of them; app.start_server() not app.run)
    asyncio.run(start())
else:
    print('todo: wasm/js can convert files in browser as user picks them for upload (not implemented)')
