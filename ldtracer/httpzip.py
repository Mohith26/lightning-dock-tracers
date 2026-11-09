import io, urllib.request, zipfile
class HTTPRangeFile(io.RawIOBase):
    def __init__(self, url):
        self.url=url; self.pos=0
        req=urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req) as r: self.size=int(r.headers['Content-Length'])
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self, off, whence=0):
        self.pos = off if whence==0 else (self.pos+off if whence==1 else self.size+off); return self.pos
    def read(self, n=-1):
        if n is None or n<0: n=self.size-self.pos
        if n==0 or self.pos>=self.size: return b''
        end=min(self.pos+n, self.size)-1
        req=urllib.request.Request(self.url, headers={'Range':f'bytes={self.pos}-{end}'})
        with urllib.request.urlopen(req) as r: data=r.read()
        self.pos+=len(data); return data
    def readinto(self, b):
        d=self.read(len(b)); b[:len(d)]=d; return len(d)
def open_remote_zip(url): return zipfile.ZipFile(io.BufferedReader(HTTPRangeFile(url), buffer_size=1<<16))
