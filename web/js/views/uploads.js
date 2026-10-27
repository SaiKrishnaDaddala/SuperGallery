import { $, $$, api, bytes, esc, fail, h, icon, pickFolder, poll, shortPath, state } from '../core.js';

const queue=[];let destination='',working=false,paused=false;const listeners=new Set();
const notify=()=>listeners.forEach(fn=>fn());
const digest=async data=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',data))].map(b=>b.toString(16).padStart(2,'0')).join('');
async function fingerprint(file){const edge=1024*1024;return digest(await new Blob([file.name+'|'+file.size+'|'+file.lastModified,file.slice(0,edge),file.slice(Math.max(edge,file.size-edge))]).arrayBuffer());}
async function send(entry){
  entry.status='uploading';entry.error='';notify();
  entry.fingerprint ||= await fingerprint(entry.file);
  const s=await api('/uploads',{name:entry.file.name,size:entry.file.size,destination:entry.destination,fingerprint:entry.fingerprint});entry.id=s.id;entry.done=s.offset;
  if(s.complete){entry.done=entry.file.size;entry.status='done';notify();return;}
  while(entry.done<entry.file.size){
    if(paused){entry.status='paused';notify();return;}
    const data=await entry.file.slice(entry.done,entry.done+s.chunk_size).arrayBuffer();
    const headers={'X-SG-Request':'1','X-Chunk-SHA256':await digest(data),'Content-Type':'application/octet-stream'};
    if(state.scope)headers['X-SG-Users']=state.scope.map(encodeURIComponent).join(',');
    const response=await fetch('/api/uploads/'+entry.id+'?offset='+entry.done,{method:'PUT',headers,body:data});
    if(!response.ok){let message='Upload interrupted. Retry to resume.';try{message=(await response.json()).detail||message;}catch{}throw new Error(message);}
    entry.done=(await response.json()).offset;notify();
  }
  await api('/uploads/'+entry.id+'/finish',{});entry.status='done';notify();poll(true);
}
async function pump(){if(working||paused)return;working=true;try{for(const entry of queue){if(paused)break;if(['queued','paused'].includes(entry.status)){try{await send(entry);}catch(e){entry.status='error';entry.error=e.message;notify();}}}}finally{working=false;notify();}}
window.addEventListener('beforeunload',e=>{if(working){e.preventDefault();e.returnValue='';}});

export function uploadsView(root){
  const el=h(`<div class="view upload-view"><div class="page-head"><div class="grow"><div class="eyebrow">STRAIGHT TO YOUR NAS</div><h1>Add to your library.</h1><p>Photos, videos and files. Pick up where a connection left off.</p></div></div><section class="card upload-drop"><div class="upload-symbol">${icon('upload')}</div><h2>A safe place for new memories.</h2><p class="muted">Choose a folder, then select files from your phone or computer.</p><button class="btn destination">${icon('folder')}Choose destination</button><div class="row wrap upload-choices"><button class="btn primary choose">Choose files</button><button class="btn camera">Take a photo</button><button class="btn pause">Pause uploads</button></div><input class="file-input" type="file" multiple hidden><input class="camera-input" type="file" accept="image/*" capture="environment" hidden><p class="muted upload-note">Keep this page open and your phone awake during uploads. If the page closes, select the same files again to resume in this signed-in session. Partial uploads expire after seven days. Existing originals are never overwritten.</p></section><div class="upload-queue" aria-live="polite"></div></div>`);root.append(el);
  function draw(){const dest=$('.destination',el);dest.innerHTML=icon('folder')+esc(destination?shortPath(destination):'Choose destination');$('.pause',el).textContent=paused?'Resume uploads':'Pause uploads';$('.upload-queue',el).innerHTML=queue.map((e,i)=>`<article class="upload-entry"><div class="row"><strong class="ellipsis grow">${esc(e.file.name)}</strong><span>${esc(e.status)}</span></div><progress max="${Math.max(1,e.file.size)}" value="${e.done}"></progress><div class="row wrap"><small class="grow">${bytes(e.done)} of ${bytes(e.file.size)}${e.error?' · '+esc(e.error):''}</small>${e.status==='error'?`<button class="btn sm retry" data-entry="${i}">Retry & resume</button>`:''}${['error','paused','queued'].includes(e.status)?`<button class="btn sm cancel" data-entry="${i}">Remove from queue</button>`:''}</div></article>`).join('');
    $$('.retry',el).forEach(b=>b.onclick=()=>{queue[+b.dataset.entry].status='queued';paused=false;pump();draw();});
    $$('.cancel',el).forEach(b=>b.onclick=async()=>{const e=queue[+b.dataset.entry];if(e.id)try{await api('/uploads/'+e.id+'/cancel',{});}catch(error){fail(error);return;}e.status='cancelled';draw();});
  }
  $('.destination',el).onclick=async()=>{const path=await pickFolder('Upload to a folder',destination);if(path){destination=path;draw();}};
  async function choose(camera=false){if(!destination){const path=await pickFolder('Upload to a folder');if(!path)return;destination=path;draw();}$(camera?'.camera-input':'.file-input',el).click();}
  $('.choose',el).onclick=()=>choose();$('.camera',el).onclick=()=>choose(true);
  for(const selector of ['.file-input','.camera-input'])$(selector,el).onchange=e=>{for(const file of e.target.files){if(!queue.some(x=>x.file.name===file.name&&x.file.size===file.size&&x.file.lastModified===file.lastModified&&x.destination===destination&&x.status!=='cancelled'))queue.push({file,destination,status:'queued',done:0});}e.target.value='';draw();pump();};
  $('.pause',el).onclick=()=>{paused=!paused;if(!paused)pump();draw();};listeners.add(draw);draw();return()=>listeners.delete(draw);
}
