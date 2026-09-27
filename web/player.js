window.startHls = () => {
  const video=document.getElementById('v');
  let hls=null,lastTime=-1,lastProgress=performance.now(),lastAction=-Infinity;
  let soft=0,hard=0,mediaRecovery=0,lastBuild=-Infinity,networkRetry=null;
  const play=()=>video.play().catch(()=>{});
  const ahead=()=>{for(let i=0;i<video.buffered.length;i++)if(video.buffered.start(i)<=video.currentTime+.1&&video.buffered.end(i)>video.currentTime)return video.buffered.end(i)-video.currentTime;return 0;};
  function build(){
    const now=performance.now();
    if(document.hidden||now-lastBuild<3000)return;
    if(networkRetry){clearTimeout(networkRetry);networkRetry=null;}
    if(hls){hls.destroy();hls=null;}
    if(lastBuild!==-Infinity)hard++;
    lastBuild=lastProgress=lastAction=now;lastTime=-1;
    video.removeAttribute('src');video.load();
    if(video.canPlayType('application/vnd.apple.mpegurl') && (!Hls.isSupported() || (/Safari/.test(navigator.userAgent) && !/Chrome|Chromium|Edg/.test(navigator.userAgent)))){
      video.src='/stream.m3u8';play();
    }else if(window.Hls&&Hls.isSupported()){
      const retry={maxNumRetry:8,retryDelayMs:200,maxRetryDelayMs:1000};
      const policy={default:{maxTimeToFirstByteMs:1500,maxLoadTimeMs:4000,timeoutRetry:retry,errorRetry:retry}};
      hls=new Hls({lowLatencyMode:false,liveSyncDurationCount:4,liveMaxLatencyDurationCount:12,
        maxLiveSyncPlaybackRate:1,maxBufferLength:12,backBufferLength:8,
        startLevel:0,abrEwmaDefaultEstimate:2000000,capLevelToPlayerSize:true,
        highBufferWatchdogPeriod:1,nudgeOffset:.1,nudgeMaxRetry:3,
        manifestLoadPolicy:policy,playlistLoadPolicy:policy,fragLoadPolicy:policy});
      hls.loadSource('/stream.m3u8');hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED,play);
      hls.on(Hls.Events.ERROR,(_,d)=>{
        if(d.response?.code===401){location.reload();return;}
        if(!d.fatal)return;
        if(d.type===Hls.ErrorTypes.MEDIA_ERROR&&performance.now()-mediaRecovery>2000){
          mediaRecovery=performance.now();hls.recoverMediaError();soft++;
        }else if(d.type===Hls.ErrorTypes.NETWORK_ERROR){
          // Restart loaders only; keep buffered frames and the video element.
          if(!networkRetry)networkRetry=setTimeout(()=>{networkRetry=null;if(hls){hls.startLoad(-1);soft++;}},500);
        }
      });
    }
  }
  function recover(){
    const now=performance.now();
    if(document.hidden||now-lastAction<1200)return;
    lastAction=now;soft++;play();
    // Move across a small buffered gap, rather than throwing the buffer away.
    for(let i=0;i<video.buffered.length;i++){
      const start=video.buffered.start(i),end=video.buffered.end(i);
      if(start>video.currentTime+.05&&end-start>.1){video.currentTime=start+.05;return;}
    }
    if(ahead()>.25){video.currentTime+=.05;return;}
    if(hls)hls.startLoad(-1);
  }
  video.addEventListener('loadedmetadata',play);
  video.addEventListener('error',()=>{if(hls)recover();});
  setInterval(()=>{
    if(document.hidden)return;
    const now=performance.now();
    if(Math.abs(video.currentTime-lastTime)>.025){lastTime=video.currentTime;lastProgress=now;}
    else if(now-lastProgress>4000){
      // Last resort only: decoding/loading is still stuck after soft recovery.
      fetch('/stream.m3u8',{cache:'no-store',signal:AbortSignal.timeout(1500)})
        .then(r=>{if(r.status===401)location.reload();}).catch(()=>{});
      build();
    }else if(now-lastProgress>1000)recover();
    if(video.paused)play();
  },250);
  function resume(){if(document.hidden)return;play();recover();}
  document.addEventListener('visibilitychange',resume);
  window.addEventListener('online',resume);
  window.streamStatus=()=>({transport:"hls",time:video.currentTime,buffer:ahead(),softRecoveries:soft,
    hardRecoveries:hard,level:hls?.currentLevel,bandwidth:hls?.bandwidthEstimate});
  build();
};
