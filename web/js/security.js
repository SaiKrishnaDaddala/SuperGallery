import { $, api, esc, h, icon, modal, toast } from './core.js';

function errorIn(bg, error) { $('.security-error',bg).textContent = error.message; }

async function credentials(title, needsCode, submit, description='') {
  let result;
  return modal({title, icon:'lock', body:`<div class="col security-form"><p class="muted">${esc(description || 'Confirm your current password to continue.')}</p><label>Current password<input class="input password" type="password" autocomplete="current-password" required></label>${needsCode ? '<label>Authenticator or recovery code<input class="input code" autocomplete="one-time-code" spellcheck="false" autocapitalize="off" required></label>' : ''}<p class="security-error danger-text" role="alert"></p></div>`,
    actions:[{label:'Cancel',value:null},{label:'Continue',cls:'primary',validate:async bg=>{
      const button = $('.modal-f .primary',bg); button.disabled=true;
      try { result=await submit({password:$('.password',bg).value,code:$('.code',bg)?.value.trim()}); return true; }
      catch(error) { errorIn(bg,error); return false; }
      finally { button.disabled=false; }
    },value:()=>result}]
  });
}

async function showRecovery(codes) {
  const content = h(`<div class="col"><p>Keep these codes somewhere private, outside this NAS. Each code can replace an authenticator code once. Your password is still required.</p><div class="recovery-codes">${codes.map(code=>`<code>${esc(code)}</code>`).join('')}</div><button class="btn download-codes">${icon('download')}Download recovery codes</button><label class="chk"><input type="checkbox" class="saved">I have saved my recovery codes</label><p class="muted">These codes are shown only once. Generating a new set invalidates the previous set.</p></div>`);
  $('.download-codes',content).onclick=()=>{
    const blob=new Blob(['SuperGallery recovery codes\nKeep these private. Each works once, together with your password.\n\n'+codes.join('\n')+'\n'],{type:'text/plain'});
    const url=URL.createObjectURL(blob), link=document.createElement('a'); link.href=url; link.download='supergallery-recovery-codes.txt'; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
  await modal({title:'Save your recovery codes',icon:'lock',body:content,actions:[{label:'Done',cls:'primary',value:true,validate:()=>$('.saved',content).checked}]});
}

export function securityCard(root) {
  let disposed=false;
  const el=h('<section class="card security-card"><h3>Security</h3><p class="muted">Loading security settings…</p></section>'); root.append(el);
  async function load() {
    try {
      const s=await api('/security'); if(disposed)return;
      el.innerHTML=`<div class="section-title"><h2>${icon('lock')}Security</h2><span class="badge ${s.enabled?'ok':'warn'}">${s.enabled?'Two-step verification on':'Password only'}</span></div><p class="muted">Protect this SuperGallery account with your password and a code from your authenticator app.</p>${!s.secure_transport?`<div class="security-transport"><b>Open the secure connection to set this up</b><p>Authenticator setup requires HTTPS. If your NAS uses a local certificate, your browser may ask you to trust it.</p><a class="btn primary" href="${esc(s.secure_url)}">${icon('lock')}Open secure SuperGallery</a></div>`:`<div class="security-actions">${s.enabled?`<button class="btn recovery">New recovery codes</button><button class="btn danger disable">Turn off verification</button>`:'<button class="btn primary enroll">Set up authenticator</button>'}<button class="btn revoke">Sign out other sessions</button></div>`}<div class="security-facts"><span>${s.sessions} active session${s.sessions===1?'':'s'}</span><span>Sessions expire after ${s.session_hours} hours</span>${s.enabled?`<span>${s.recovery_remaining} recovery codes remaining</span>`:''}</div><p class="security-note">This protects the shared SuperGallery login. The library user picker does not create separate sign-in accounts.</p>`;
      $('.enroll',el)?.addEventListener('click',async()=>{
        const setup=await credentials('Connect an authenticator',false,body=>api('/security/totp/setup',body),'Use an authenticator such as Apple Passwords, Google Authenticator, or Microsoft Authenticator.');
        if(!setup)return;
        let confirmed=null;
        const contents=h(`<div class="col security-form"><p>Scan this QR code using your authenticator app, then enter the six-digit code it shows.</p><img class="authenticator-qr" src="${setup.qr}" alt="Authenticator setup QR code"><details><summary>Enter a setup key instead</summary><code class="authenticator-secret">${esc(setup.secret)}</code><p class="muted">Time-based code · 6 digits · every 30 seconds</p></details><label>Verification code<input class="input code otp-input" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6" placeholder="000000"></label><p class="security-error danger-text" role="alert"></p><p class="muted">Setup expires in 10 minutes. Enabling verification signs out your other sessions.</p></div>`);
        await modal({title:'Verify your authenticator',icon:'lock',body:contents,actions:[{label:'Cancel',value:null},{label:'Enable verification',cls:'primary',value:true,validate:async bg=>{
          const button=$('.modal-f .primary',bg);button.disabled=true;
          try { confirmed=await api('/security/totp/confirm',{code:$('.code',bg).value.trim()});return true; }
          catch(error){errorIn(bg,error);return false;} finally{button.disabled=false;}
        }}]});
        setup.secret=''; setup.qr='';
        if(confirmed){await showRecovery(confirmed.recovery_codes);toast('Two-step verification is on.');}
        else await api('/security/totp/cancel',{}).catch(()=>{});
        load();
      });
      for(const [selector,action,title,description] of [
        ['.recovery','recovery','Replace recovery codes','Your previous recovery codes will stop working. Other sessions will be signed out.'],
        ['.disable','disable','Turn off two-step verification','Your password will be the only sign-in protection. Other sessions will be signed out.'],
        ['.revoke','revoke','Sign out other sessions','Keep this session and sign out everywhere else.']]) {
        $(selector,el)?.addEventListener('click',async()=>{
          const result=await credentials(title,s.enabled,body=>api('/security/'+action,body),description);
          if(result?.recovery_codes) await showRecovery(result.recovery_codes);
          if(result){toast('Security settings updated.');load();}
        });
      }
    } catch(error){if(!disposed)el.innerHTML=`<h3>Security</h3><p>${esc(error.message)}</p><button class="btn retry">Try again</button>`;$('.retry',el)?.addEventListener('click',load);}
  }
  load();return()=>{disposed=true;};
}
