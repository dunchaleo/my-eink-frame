import sys
import struct
import asyncio
import subprocess

async def process_image(filename, ret=False):
    #(dont just get exif--let this task totally finish conversion).
    #let OS handle threads by making a subprocess. blocking code can be awaited. see comment in converter.py
    #TODO make i/o pipes instead of args?
    vis_args = ['o', 'm', 'b']
    subcall = [sys.executable, 'converter.py', filename] + vis_args
    subproc = await asyncio.create_subprocess_exec(
        *subcall, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    #we'll get a byte obj (can it be streamed/chunked?) from converter.py, just needs to be serialized.
    stdout,stderr = await subproc.communicate()
    return decode_subproc_bytes(stdout)

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


async def tester():
    testmeta = await process_image('filename3.jpg')
    print(testmeta)
    return ''



#whatsthis = converter.main('filename3.jpg','o','m','b', True)
#decode_subproc_bytes(whatsthis)
