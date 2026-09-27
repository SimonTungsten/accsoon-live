"""Password-gated LAN live feed. Page, playlist, and segments share a session."""
import hashlib,hmac,http.server,http.client,secrets,time,re,os
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
ROOT=Path(__file__).resolve().parent
PASSWORD=os.environ.get('STREAM_PASSWORD','').encode()
if not PASSWORD:raise SystemExit('Set STREAM_PASSWORD to a non-empty private password before starting.')
KEYFILE=ROOT/'.session-key'
try:fd=os.open(KEYFILE,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
except FileExistsError:pass
else:
 with os.fdopen(fd,'wb') as keyfile:keyfile.write(secrets.token_bytes(32))
KEY=KEYFILE.read_bytes()
LOGIN='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Live</title><style>html,body{height:100%;margin:0;background:#090909;color:#eee;font:16px system-ui}body{display:grid;place-items:center}form{width:min(280px,80vw)}label{display:block;margin-bottom:12px}input,button{box-sizing:border-box;width:100%;padding:14px;border-radius:4px;border:1px solid #555;font:inherit}input{background:#181818;color:white}button{margin-top:12px;cursor:pointer}p{font-size:14px;color:#ddd}</style><form method="post" action="/login"><label for="password">Stream password</label><input id="password" name="password" type="password" autocomplete="current-password" required autofocus><button>Watch live</button>ERROR</form></html>'''
def signature(value):return hmac.new(KEY,value.encode(),hashlib.sha256).hexdigest()
class H(http.server.BaseHTTPRequestHandler):
 def reply(self,status,body=b'',mime='text/plain',extra=(),head=False):
  self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
  self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
  for k,v in extra:self.send_header(k,v)
  self.end_headers()
  if not head:
   try:self.wfile.write(body)
   except (BrokenPipeError,ConnectionResetError):pass
 def authorized(self):
  try:
   c=SimpleCookie(self.headers.get('Cookie',''));value=c['stream_session'].value
   expiry,nonce,sig=value.split('.')
   return time.time()<int(expiry) and hmac.compare_digest(signature(expiry+'.'+nonce),sig)
  except (KeyError,ValueError):return False
 def proxy_rtc(self):
  if not self.authorized():return self.reply(401)
  path=urlsplit(self.path).path
  if not re.fullmatch(r'/rtc/live/whep(?:/[a-zA-Z0-9-]+)?',path):return self.reply(404)
  try:n=int(self.headers.get('Content-Length','0'))
  except ValueError:return self.reply(400)
  if not 0<=n<=65536:return self.reply(413)
  conn=http.client.HTTPConnection('127.0.0.1',8889,timeout=6)
  try:
   conn.request(self.command,path[4:],body=self.rfile.read(n),headers={'Content-Type':self.headers.get('Content-Type','application/sdp')})
   r=conn.getresponse();body=r.read();extra=[]
   location=r.getheader('Location')
   if location:
    loc=urlsplit(location).path
    if not loc.startswith('/'):loc='/live/'+loc
    extra.append(('Location','/rtc'+loc))
   self.reply(r.status,body,r.getheader('Content-Type','application/sdp'),extra)
  except (OSError,http.client.HTTPException):self.reply(502)
  finally:conn.close()
 def do_DELETE(self):self.proxy_rtc()
 def do_POST(self):
  if self.path.startswith('/rtc/'):return self.proxy_rtc()
  if urlsplit(self.path).path!='/login':return self.reply(404)
  try:n=int(self.headers.get('Content-Length','0'))
  except ValueError:return self.reply(400)
  if not 0<n<4096:return self.reply(400)
  password=parse_qs(self.rfile.read(n).decode('utf-8',errors='replace')).get('password',[''])[0].encode()
  if not hmac.compare_digest(password,PASSWORD):
   return self.reply(401,LOGIN.replace('ERROR','<p>Incorrect password.</p>').encode(),'text/html; charset=utf-8')
  value=str(int(time.time())+31536000)+'.'+secrets.token_hex(16)
  cookie='stream_session='+value+'.'+signature(value)+'; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000'
  self.reply(303,extra=[('Location','/'),('Set-Cookie',cookie)])
 def do_HEAD(self):self.do_GET(head=True)
 def do_GET(self,head=False):
  path=urlsplit(self.path).path
  if not self.authorized():
   if path in ('/','/index.html','/login'):
    return self.reply(200,LOGIN.replace('ERROR','').encode(),'text/html; charset=utf-8',head=head)
   return self.reply(401,b'Authentication required',head=head)
  assets={'/':('index.html','text/html'),'/index.html':('index.html','text/html'),'/player.js':('player.js','text/javascript'),'/realtime.js':('realtime.js','text/javascript'),'/hls.min.js':('hls.min.js','text/javascript')}
  if path in assets:
   name,mime=assets[path];file=ROOT/'web'/name
  elif path in ('/stream.m3u8','/v0.m3u8','/v1.m3u8'):file=Path('/tmp/accsoon_hls')/path[1:];mime='application/vnd.apple.mpegurl'
  elif re.fullmatch(r'/live\d+\.ts',path):file=Path('/tmp/accsoon_hls')/path[1:];mime='video/mp2t'
  else:return self.reply(404,head=head)
  try:body=file.read_bytes()
  except OSError:return self.reply(404,head=head)
  if path=='/stream.m3u8':
   body=re.sub(rb',AVERAGE-BANDWIDTH=\d+',b'',body)
   body=body.replace(b'#EXT-X-VERSION:6',b'#EXT-X-VERSION:6\n#EXT-X-START:TIME-OFFSET=-5.0,PRECISE=NO')
  extra=[]
  if path in ('/','/index.html'):
   value=str(int(time.time())+31536000)+'.'+secrets.token_hex(16)
   extra=[('Set-Cookie','stream_session='+value+'.'+signature(value)+'; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000')]
  self.reply(200,body,mime,extra,head=head)
 def log_message(self,*args):pass
if __name__=='__main__':
 http.server.ThreadingHTTPServer.allow_reuse_address=True
 http.server.ThreadingHTTPServer((os.environ.get('STREAM_HOST','127.0.0.1'),int(os.environ.get('STREAM_PORT','8888'))),H).serve_forever()
