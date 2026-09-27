#!/usr/bin/env python3
"""Own the three streaming processes and restart a failed component automatically."""
import fcntl,os,signal,subprocess,time,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
if not os.environ.get('STREAM_PASSWORD'):
 raise SystemExit('Set STREAM_PASSWORD to a non-empty private password before starting.')
(ROOT/'verification').mkdir(exist_ok=True)
lock=open(ROOT/'.service.lock','w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Streaming supervisor already running')
commands={'mediamtx':['mediamtx',str(ROOT/'mediamtx.yml')],
          'http':[sys.executable,str(ROOT/'hlsserve.py')],
          'pipeline':['bash',str(ROOT/'serve-native.sh')]}
children={};started={};running=True
(ROOT/'verification/service.pid').write_text(str(os.getpid()))
def stop(*args):
 global running
 running=False
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
def terminate(p):
 try:os.killpg(p.pid,signal.SIGTERM)
 except ProcessLookupError:pass
try:
 while running:
  for name,cmd in commands.items():
   p=children.get(name)
   if name=='pipeline' and p is not None and p.poll() is None and time.time()-started.get(name,time.time())>20:
    playlist=Path('/tmp/accsoon_hls/v0.m3u8')
    fresh=playlist.stat().st_mtime if playlist.exists() else 0
    if time.time()-fresh>20:
     print(time.strftime('%Y-%m-%d %H:%M:%S'),'pipeline stalled; restarting capture',flush=True)
     terminate(p)
     try:p.wait(timeout=5)
     except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   if p is None or p.poll() is not None:
    if p:terminate(p)
    with open(ROOT/'verification'/f'{name}-service.log','ab') as log:
     p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    started[name]=time.time();children[name]=p;(ROOT/'verification'/f'{name}.pid').write_text(str(p.pid))
    print(time.strftime('%Y-%m-%d %H:%M:%S'),name,'started',p.pid,flush=True)
    time.sleep(.3)
  time.sleep(1)
finally:
 for p in children.values():terminate(p)
 for p in children.values():
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:
   try:os.killpg(p.pid,signal.SIGKILL)
   except ProcessLookupError:pass
