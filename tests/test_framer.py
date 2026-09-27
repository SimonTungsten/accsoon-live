import io,struct,sys,unittest
sys.path.insert(0,'.')
from framer import Framer
class Reassembly(unittest.TestCase):
 def test_continuation_preserves_24_bytes(self):
  f=Framer(io.BytesIO()); got=[];f.message=lambda s,d:got.append((s,d))
  payload=bytes(range(120)); fragments=[payload[:60],payload[60:]]
  for i,part in enumerate(fragments):
   p=bytearray(32);p[:4]=bytes.fromhex('c6ea8578');struct.pack_into('<H',p,6,len(part)+24);p[17]=2
   struct.pack_into('<IHH',p,24,100,2,i);f.transfer(bytes(p)+part)
  f.flush(100);self.assertEqual(got,[(100,payload)])
 def test_incomplete_never_emitted(self):
  f=Framer(io.BytesIO());got=[];f.message=lambda s,d:got.append(d)
  f.pending[100]=(2,{0:b'partial'});f.flush(100)
  self.assertEqual(got,[]);self.assertEqual(f.stats['incomplete'],1)
unittest.main()
