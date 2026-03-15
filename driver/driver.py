#a good power optimization and use case in general is shutting the device off in between draws and having a long time per pic. so persistent mem objects is bad here, should just have to read/write filesystem.
#(anything under ~x mins would not benefit a lot from that but >~x mins really would, still would need a hardware wakeup timer, and x depends on bootup power spike)

#stay away from csv lib here too? use file handles and primitive parsing or just split()ing
import csv
import struct
import time

metadata_path = "./../server/files.csv"
interval_s = 35 #TODO settings.csv in server/

#could do raw bytes files but maybe editable text has advantages.. reading happens very infrequently anyway
def get_var(var:int):
    with open('vars.csv','r') as f:
       reader = csv.reader(f)
       vars = next(reader) #one row
    ret = vars[0]
    match var:
        case -1:
            return vars
        case 0: #displaying img at index ret in files csv
            return int(ret)
def set_var(var:int, val):
    vars = get_var(-1)
    vars[int] = val
    with open('vars.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(vars)



class MetaCsv():
    def __init__(self,path):
        self.files = []
        self.files_n:int = 0
        with open(path,'r') as f:
            reader = csv.reader(f)
            for row in reader:
                self.files.append(row)
        self.files_n = len(files)
def display(idx):
    return "calling pimoroni driver funs"

def main_sleep():
    #CAN use persistent memory objects here..
    #(still consider this process as having to restart every time user goes into the web server)
    current = get_var(0)
    metadata = MetaCsv(metadata_path)
    i = 0
    #interrupt = False
    #while (True and (not interrupt)):
    while True:
        start = time.time()
        display(current + i)
        elapsed = time.time() - start
        time.sleep(max(0, interval_s - elapsed))
        i+=1
        i = i % metadata.files_n
        set_var(0, i) #frequently save idx
        interrupt = detect_interrupt()

def main_shutdown():
    #this cant use any memory at all, have to read from fs to index files csv
    return 0
