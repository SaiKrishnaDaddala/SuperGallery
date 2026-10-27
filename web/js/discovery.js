import { api, esc, h, modal, num, poll } from './core.js';
import { hasFeature } from './features.js';

export async function indexDialog(mode='files'){
  if(mode==='photos'||mode==='videos'){
    const video=mode==='videos',s=await api('/visual/status?media='+(video?'video':'image'));
    const answer=await modal({title:video?'Search inside videos':'Search photo contents',body:h(`<div class="col"><h3>${num(s.indexed)} ${video?'videos':'photos'} searchable</h3><p>Describe activities, objects and places in English. Your NAS prepares and searches the library locally.</p><p>${num(s.total-s.checked)} waiting · ${num(s.errors)} unreadable</p><p class="muted">${video?'One frame every 15 seconds, up to 120 frames spread across each video. Brief actions between samples can be missed. Open a match to jump to its timestamp.':'Matches are approximate. Small details, negation and complex actions can be missed.'}</p>${s.task?`<p>${esc(s.task.message||'Queued behind other local indexing work.')}</p>`:''}</div>`),actions:[{label:'Close'},{label:s.task?'Pause indexing':'Prepare '+(video?'videos':'photos'),value:s.task?'pause':'start',cls:'primary'}]});
    if(answer==='start')await api('/intelligence/index',{kind:video?'scenes':'visual',retry:true});if(answer==='pause')await api(`/tasks/${s.task.id}/cancel`,{});
  }else{
    const [s,o]=await Promise.all([hasFeature('documents')?api('/search/status'):Promise.resolve({indexed:0,disabled:true}),hasFeature('ocr')?api('/ocr/status'):Promise.resolve({indexed:0,disabled:true})]);
    const answer=await modal({title:'Search text everywhere',body:h(`<div class="col"><h3>Documents, screenshots and scanned pages</h3><p>${num(s.indexed)} documents with extracted text · ${num(o.indexed)} files with recognized text.</p><p>Text recognition runs on this NAS. Printed English works best; handwritten text and other scripts may be inaccurate.</p><p class="muted">OCR covers images up to 50 MB and the first 20 pages of each PDF, with a 90-second limit per file. Digital document text covers up to 80 PDF pages and 10 MB per file.</p><p>Document indexing: ${s.disabled?'disabled':s.task?esc(s.task.status):'idle'} · Text recognition: ${o.disabled?'disabled':o.task?esc(o.task.status):'idle'}.</p></div>`),actions:[{label:'Close'},...(!s.disabled?[{label:s.task?'Pause documents':'Index documents',value:s.task?'pause-doc':'doc'}]:[]),...(!o.disabled?[{label:o.task?'Pause text recognition':'Read images & scans',value:o.task?'pause-ocr':'ocr',cls:'primary'}]:[])]});
    if(answer==='doc'||answer==='ocr')await api('/intelligence/index',{kind:answer==='doc'?'documents':'ocr',retry:true});if(answer==='pause-doc')await api(`/tasks/${s.task.id}/cancel`,{});if(answer==='pause-ocr')await api(`/tasks/${o.task.id}/cancel`,{});
  }
  poll(true);
}
