#!/usr/bin/env python3
"""Ordered USB transfers -> RTMS messages -> H.265. Metadata occurs once/message."""
import sys, struct, re, json
MAGIC=bytes.fromhex('c6ea8578')
class Framer:
    def __init__(self,out):
        self.out=out; self.pending={}; self.last=None; self.started=False; self.params={}
        self.stats=dict(packs=0,messages=0,incomplete=0,bad=0,gaps=0)
    def message(self,seq,data):
        if self.last is not None and seq != self.last+1:
            self.started=False;self.stats['gaps']+=1
        self.last=seq
        if len(data)<24: self.stats['bad']+=1;return
        n=struct.unpack_from('<I',data,20)[0]
        if n!=len(data)-24: self.stats['bad']+=1;self.started=False;return
        data=data[24:]
        matches=list(re.finditer(b'\x00\x00(?:\x00)?\x01',data))
        for j,m in enumerate(matches):
            end=matches[j+1].start() if j+1<len(matches) else len(data)
            nal=data[m.start():end]; typ=(data[m.end()]>>1)&63
            if typ in (32,33,34):self.params[typ]=nal
            if not self.started:
                if typ not in (19,20) or len(self.params)!=3:continue
                self.out.write(b''.join(self.params[t] for t in (32,33,34)));self.started=True
            self.out.write(nal)
        self.stats['messages']+=1
    def flush(self,upto):
        for seq in sorted(s for s in self.pending if s<=upto):
            num,parts=self.pending.pop(seq)
            if len(parts)==num and all(i in parts for i in range(num)):
                self.message(seq,b''.join(parts[i] for i in range(num)))
            else:self.stats['incomplete']+=1;self.started=False
        self.out.flush()
    def transfer(self,x):
        p=0
        while p+8<=len(x):
            if x[p:p+4]!=MAGIC:self.stats['bad']+=1;return
            total=struct.unpack_from('<H',x,p+6)[0]+8
            if total<8 or p+total>len(x):self.stats['bad']+=1;return
            z=x[p:p+total];p+=total;self.stats['packs']+=1
            if len(z)<32 or z[17]!=2 or z[18]&15:continue
            seq,num,idx=struct.unpack_from('<IHH',z,24)
            if not num or idx>=num:self.stats['bad']+=1;continue
            if self.last is not None and seq<=self.last:continue
            old,parts=self.pending.setdefault(seq,(num,{}))
            if old!=num:self.stats['bad']+=1;continue
            parts[idx]=z[32:]
            self.flush(seq-4)
        if p!=len(x):self.stats['bad']+=1

def main():
    inp=sys.stdin.buffer; f=Framer(sys.stdout.buffer)
    def readn(n):
        b=bytearray()
        while len(b)<n:
            c=inp.read(n-len(b))
            if not c:return None
            b.extend(c)
        return bytes(b)
    while True:
        h=readn(4)
        if h is None:break
        n=struct.unpack('<I',h)[0]
        if n>65536:raise ValueError('Invalid USB transfer length')
        x=readn(n)
        if x is None:break
        f.transfer(x)
    f.flush(2**32)
    print(json.dumps(f.stats),file=sys.stderr)
if __name__=='__main__':main()
