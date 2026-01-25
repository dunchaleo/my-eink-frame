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
    #on instantiation, we expect files.csv to be in the right order.
    def __init__(self):
        self.files = [] #row in files.csv has ``filename,timestamp'' (+ more cols?), see convert()
        self.ordering = [] #array of indexes--this is what actually gets sorted in mem! TODO can this be made a stream/generator?
        self.sortby = 1 #default sorting is timestamp,
        self.desc = False# (ascending)
    def mwrite(self):
        #only do once on init
        with open('./files.csv', 'r') as f:
            reader = csv.reader(f)
            i = 0
            for row in reader:
                self.files.append(row)
                self.ordering.append(i)
                i+=1
    def fwrite(self):
        with open('./files.csv', 'w') as f: #w mode clears file first
            writer = csv.writer(f)
            for row in self.files:
                f.write(row)
    def mfree(self):
        self.files = []
        self.ordering = []
    def chsort(self, sortby, desc):
        #could this could be optimized a lot?
        #easy example: if just toggling desc/asc, reversal is faster than list.sort()
        #  (TODO look into ``reversed(list)'' rather than ``list.reverse''--still O(n) for file writing lol)
        self.ordering.sort(reverse=desc, key=lambda i: self.files[i][sortby])
        #also a setter
        self.sortby=sortby
        self.desc=desc
    def insert(self, newfile): #newfile looks just like a row of files.csv
        #see comment in ./converter/convert.py,
        #by expected use case insertion sort is probably really good here,
        #unless user picked from their recents the wrong way,
        #then comparison just needs to be reversed first (but how can you tell?)
        #   we could say if pos >= len-3 (or len-[tolerance]), we had a "hard" insert.
        #   more than 5 (or [also tolerance]?) hard inserts in a row means it might be worth ordering.reverse() and sortby=!sortby
        newlen = len(self.files)+1
        self.files.append(newfile)
        pos = newlen-1
        for i in range(pos-1,-1,-1):#for(i=pos-1;i>=0;i--,pos--){..comp(,ordering[i]);..}
            if self.compare(newfile, self.ordering[i]):
                break
            pos-=1
        #insert real position into ordering after pos
        self.ordering.append(0)
        for i in range(newlen-1,pos+1,-1):
            self.ordering[i] = self.ordering[i-1]
        self.ordering[pos+1] = newlen - 1
        #fwrite() #insert really doesnt need this. fwrite is when user "applies changes", having the buffer open (self.files/ordering) means changes to file dont need to be made.
    def compare(self, new_elt, elt_idx):
        new_data = new_elt[self.sortby]
        elt_data = self.files[elt_idx][self.sortby]
        if(self.desc):
            return (int(new_data)<int(elt_data)) #im stupid
        else:
            return (int(new_data)>int(elt_data))
    def file_stream(self): #for(i=0; i<len; i++){ret[i] = files[self.ordering[i]];}
        return (self.files[i] for i in self.ordering)
    def close(self):
        #this should be called in between server instances (writes csv in order)
        #self.files = self.files_list()
        self.files = [self.files[i] for i in self.ordering] #needs to be list comprehension for random-access, obviously.
        #   (a generator would actually be the same speed due to the listexpression being an indexing operation,
        #   so that encoded as a rule in a generator would be the same speed)
        fwrite()
        return self.files #useful
#usage:
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
