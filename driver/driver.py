#a good power optimization and use case in general is shutting the device off in between draws and having a long time per pic. so persistent mem objects is bad here, should just have to read/write filesystem.
#(anything under ~x mins would not benefit a lot from that but >~x mins really would, still would need a hardware wakeup timer, and x depends on bootup power spike)

#i had the wrong idea at first. for potentially very low mem environments, you dont want to load a csv into mem and then index it. you just want to retrieve n bytes from a file at an offset. so the server needs to write a binary file, with fixed-size entries. e.g. 255,sizeof(int) for filename,timestamp. not a csv.
#using a bin file, use fseek in python or fseek/lseek in C
#this could be good to reuse for an mcu+frame that has to connect to a server. for a sbc solution it's not worth thinking about but i'm hung up on the idea that a long battery life would be the best thing about even doing this at all.

import inky
import struct
import time

metadata_path = "./../server/files.bin"
interval_s = 35 #TODO settings.csv in server/
bin_fmt_str = '255sQ' #must == Meta.bin_fmt_str
bin_record_size = struct.calcsize(bin_fmt_str)
def get_N():
    with open(metadata_path, 'rb') as bf:
        bf.seek(-4,2)
        return bf.read(4)
N = get_N() #N files

def run():
    with open(metadata_path,'rb') as bf:
        i=0
        while i < N:
            d = i*bin_record_size
            bf.seek(d,0)
            brecord = bf.read(bin_record_size)
            metadata = decode_bin_record(brecord)

            i+=1
            if i >= N:
                i=0


    # with open(metadata_path, 'rb') as bf:
    #     remaining = N*bin_record_size + 4
    #     while remaining > 4:
    #         chunk = bf.read(bin_record_size)
    #         remaining -= bin_record_size

def decode_bin_record(brecord):
    #turn a files.bin row into a metadata tuple

    record = struct.unpack(bin_fmt_str,brecord) # -> multi-typed tuple
    #clear padding; make list (mutable)
    list = [None]*len(record)
    i = 0
    for elt in record:
        if(type(elt) == type(b'')):
            list[i] = elt.rstrip(b'\x00').decode('utf-8')
        else:
            list[i] = elt
        i+=1
    return tuple(list) #stay tuple
