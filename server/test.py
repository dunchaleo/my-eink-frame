#trying to be flexible enough for portability between SBC and MCU.
#speed vs mem? neither platform has a lot of threads to work with,
#and if all tasks are in series then each task gets to use all the ram...
#so they should be faster and can take more mem.
#(microdot also seems opinionated in favor of async)

from microdot import Microdot, send_file, Request
import subprocess
import csv

app = Microdot()

server_covnersion = True #convert files in browser or on device

class Meta:
    #row in files.csv has ``filename,timestamp'' (+ more cols?), see convert()
    files = []
    ordering = [] #array of indexes--this is what actually gets sorted!
    sortby = 1 #default sorting is timestamp,
    desc = False# (ascending)
    def mwrite():
        with open('./files.csv', 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                self.files.append(row)
    def fwrite():
        with open('./files.csv', 'w') as f: #w mode clears file first
            writer = csv.writer(f)
            for row in self.files:
                f.write(row)
    def mfree():
        self.files = []
        #self.ordering = []
    def chsort(sortby, desc):
        #could this could be optimized a lot?
        ordering.sort(reverse=desc, key=lambda i: files[i])
        #also a setter
        self.sortby=sortby
        self.asc=asc
    def insert(newfile): #newfile looks just like a row of files.csv
        #see comment in ./converter/convert.py,
        #by expected use case insertion sort is probably really good here,
        #unless user picked from their recents the wrong way,
        #then comparison just needs to be reversed first (but how can you tell?)


#usage:
#meta.chsort(1,True)
#meta.insert(convert(file))
#(inserts file into place based on timestamp)

#returns [path, metadata1, ..] (currently only metadata is timestamp)
def convert(path):
    if server_conversion:
        subprocess.run('./converter/venv/bin/python', f'convert.py {path}')
    else:
        lksjfasfj

def client_convert():





    
@app.route('/')
async def index(request):
    return 'Hello, world!'

@app.post('/upload')
async def upload(request):
    path = 'working/'+filename
    with open(path, 'wb') as f:
    ...
    insert(convert(path)) #convert() needs to ret something with exif available for ins() to use
@app.route('/clear')

app.run(port=4000, debug=True)
