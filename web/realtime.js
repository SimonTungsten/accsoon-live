(() => {
 const video=document.getElementById('v');
 let pc=null,session=null,failures=0,timer=null,watch=null,lastFrames=0,lastProgress=performance.now(),stopped=false;
 const play=()=>video.play().catch(()=>{});
 async function cleanup(){
  if(pc){pc.onconnectionstatechange=null;pc.close();pc=null;}
  video.srcObject=null;
  if(session){fetch(session,{method:'DELETE',keepalive:true}).catch(()=>{});session=null;}
 }
 function retry(){
  if(stopped||timer)return;
  timer=setTimeout(()=>{timer=null;connect();},500);
 }
 async function connect(){
  if(stopped||document.hidden)return;
  await cleanup();
  if(failures>=3){stopped=true;clearInterval(watch);window.startHls();return;}
  failures++;lastProgress=performance.now();lastFrames=0;
  const peer=new RTCPeerConnection({iceServers:[]});pc=peer;
  peer.addTransceiver('video',{direction:'recvonly'});
  peer.ontrack=e=>{video.srcObject=e.streams[0]||new MediaStream([e.track]);play();};
  peer.onconnectionstatechange=()=>{if(peer.connectionState==='failed')retry();};
  try{
   await peer.setLocalDescription(await peer.createOffer());
   await new Promise(resolve=>{
    if(peer.iceGatheringState==='complete')return resolve();
    const done=()=>{peer.removeEventListener('icegatheringstatechange',changed);clearTimeout(timeout);resolve();};
    const changed=()=>{if(peer.iceGatheringState==='complete')done();};
    const timeout=setTimeout(done,1200);peer.addEventListener('icegatheringstatechange',changed);
   });
   if(pc!==peer)return;
   const response=await fetch('/rtc/live/whep',{method:'POST',headers:{'Content-Type':'application/sdp'},body:peer.localDescription.sdp,signal:AbortSignal.timeout(5000)});
   if(response.status===401){location.reload();return;}
   if(response.status!==201)throw new Error('Connection unavailable');
   const location=response.headers.get('Location');
   if(pc!==peer){if(location)fetch(location,{method:'DELETE'}).catch(()=>{});return;}
   session=location;await peer.setRemoteDescription({type:'answer',sdp:await response.text()});
  }catch(e){if(pc===peer)retry();}
 }
 window.streamStatus=async()=>{
  const data={transport:'webrtc',state:pc?.connectionState,time:video.currentTime,width:video.videoWidth,attempts:failures};
  if(pc)for(const s of (await pc.getStats()).values())if(s.type==='inbound-rtp'&&s.kind==='video')Object.assign(data,{frames:s.framesDecoded,lost:s.packetsLost,jitter:s.jitter,jitterBufferDelay:s.jitterBufferDelay,jitterBufferEmittedCount:s.jitterBufferEmittedCount});
  return data;
 };
 watch=setInterval(async()=>{
  if(stopped||document.hidden||!pc)return;
  const peer=pc;let frames=0;
  try{for(const s of (await peer.getStats()).values())if(s.type==='inbound-rtp'&&s.kind==='video')frames=s.framesDecoded||0;}catch{return;}
  if(peer!==pc)return;
  if(frames>lastFrames){lastFrames=frames;lastProgress=performance.now();if(frames>90)failures=0;}
  else if(performance.now()-lastProgress>2500)retry();
 },500);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!stopped){play();if(pc?.connectionState!=='connected')retry();}});
 window.addEventListener('online',()=>{if(!stopped)retry();});
 window.addEventListener('pagehide',()=>{stopped=true;clearInterval(watch);clearTimeout(timer);cleanup();});
 const publicHls=new URLSearchParams(location.search).get('transport')==='hls'||/\.ngrok(?:-free)?\.(app|dev|io)$/.test(location.hostname);
 if(!publicHls&&window.RTCPeerConnection)connect();else {stopped=true;clearInterval(watch);window.startHls();}
})();
