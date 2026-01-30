#trying to be flexible enough for portability between SBC and MCU.
#speed vs mem? neither platform has a lot of threads to work with,
#and if all tasks are in series then each task gets to use all the ram...
#so they should be faster and can take more mem.
#(microdot also seems opinionated in favor of async)

from microdot import Microdot, send_file, Request
import os
import subprocess
import csv

import metadata

app = Microdot()
meta = metadata.Meta()

Request.max_content_length = 1024*1024

server_covnersion = True #convert files in browser or on device

#returns [path, metadata1, ..] (currently only metadata is timestamp)
def convert(path):
    if server_conversion:
        subprocess.run('./converter/venv/bin/python', f'convert.py {path}')
    else:
        print('todo: wasm/js can convert files in browser as user picks them for upload')


#def client_convert():


@app.route('/uploader')
async def index(request):
    return send_file('new.html')
@app.post('/upload')
async def upload(request):
  #  filename = request.headers['Content-Disposition'].split(
  #      'filename=')[1].strip('"')
    filename = request.headers['filename']
    size = int(request.headers['Content-Length'])
    path = 'working/'+filename
    print(f'content_length: {request.content_length}')
    print(path, size)

    # write the file to the files directory in 1K chunks
    with open(path, 'wb') as f:
        while size > 0:
            chunk = await request.stream.read(min(size, 1024))
            f.write(chunk)
            size -= len(chunk)
    print('Successfully saved file: ' + filename)
    return ''
#@app.post('/stage')
#async def stage(request):
#    asyncio.create_task()
# @app.route('/rmforce')
# async def rmforce(request):
#     path = 'working/'
#     extensions = [
#         '.jpeg', '.jpg', '.png', '.gif', '.svg', '.webp', '.bmp', '.jfif', '.heic',
#         '.JPEG', '.JPG', '.PNG', '.GIF', '.SVG', '.WEBP', '.BMP', '.JFIF', '.HEIC',
#     ]
#     for filename in os.listdir(path):
#         for extension in extensions:
#             if filename.endswith(extension):
#                 os.remove(os.path.join(path, filename))
#     return ''



app.run(port=4000, debug=True)
