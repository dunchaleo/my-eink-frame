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
        #could this still be optimized a lot?
        #if just toggling desc/asc, reversal is faster than list.sort()
        if(self.sortby == sortby and self.desc == (not desc)):
            self.files.reverse()
        else:
            self.ordering.sort(reverse=desc, key=lambda i: self.files[i][sortby])
        #also a setter
        self.sortby=sortby
        self.desc=desc
    def insert(self, newfile): #newfile looks just like a row of files.csv
        #see comment in ./converter/convert.py,
        #by expected use case insertion sort is probably really good here,
        #unless user picked from their recents the wrong way,
        #then comparison just needs to be reversed first (but how can you tell?)
        #   we could say if len-pos >= len-3 (or len-[tolerance]), we had a "hard" insert.
        #   more than 5 (or [also tolerance]?) hard inserts in a row means it might be worth ordering.reverse() and sortby=!sortby
        newlen = len(self.files)+1
        pos = newlen-2
        while not self.compare(newfile,self.ordering[pos]):
            pos-=1
            #insert real position into ordering after pos
        self.ordering.append(0)
        i = newlen-1
        while (i>pos+1):
            self.ordering[i] = self.ordering[i-1]
            i-=1
            self.ordering[pos+1] = newlen - 1
            #ensure said real position is real
        self.files.append(newfile)
        #fwrite()
        # ^ insert really doesnt need this. fwrite is when user "applies changes"; having the buffer open (self.files/ordering) means changes to file dont need to be made.
    def compare(self, new_elt, elt_idx):
        new_data = new_elt[self.sortby]
        elt_data = self.files[elt_idx][self.sortby]
        if(self.desc):
            max = int(self.files[0][self.sortby])
            complement = max - int(elt_data)
            new_complement = max - int(new_data)
            return (new_complement > complement)
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
