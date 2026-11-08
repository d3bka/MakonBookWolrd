(function(){
'use strict';
const qs=(s,r=document)=>r.querySelector(s);
const qsa=(s,r=document)=>Array.from(r.querySelectorAll(s));
const shell=qs('[data-world-shell]');
const csrfCookieName=shell?.dataset?.csrfCookieName||'csrftoken';
const cookie=name=>document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith(name+'='))?.slice(name.length+1)||'';
const csrf=()=>cookie(csrfCookieName)||qs('input[name=csrfmiddlewaretoken]')?.value||'';
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function post(url,data={}){
  const body=new URLSearchParams(data);
  const token=csrf();
  if(token)body.set('csrfmiddlewaretoken',token);
  const r=await fetch(url,{method:'POST',credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest','X-CSRFToken':token,'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},body,cache:'no-store'});
  const p=await r.json().catch(()=>({ok:false,error:`Request failed (${r.status})`}));
  if(!r.ok||!p.ok){const err=new Error(p.error||`Request failed (${r.status})`);err.payload=p;throw err;}
  return p;
}
function postKeepalive(url,data={}){
  const body=new URLSearchParams(data);
  const token=csrf();
  if(token)body.set('csrfmiddlewaretoken',token);
  return fetch(url,{method:'POST',credentials:'same-origin',keepalive:true,headers:{'X-Requested-With':'XMLHttpRequest','X-CSRFToken':token,'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},body,cache:'no-store'});
}
async function getJSON(url){
  const sep=url.includes('?')?'&':'?';
  const r=await fetch(`${url}${sep}_=${Date.now()}`,{credentials:'same-origin',cache:'no-store',headers:{'X-Requested-With':'XMLHttpRequest'}});
  const p=await r.json().catch(()=>({ok:false,error:`Request failed (${r.status})`}));
  if(!r.ok||!p.ok){const err=new Error(p.error||`Request failed (${r.status})`);err.payload=p;throw err;}
  return p;
}
function wireChoiceGroup(labelSelector, root=document){
  qsa(labelSelector, root).forEach(label=>{
    const input=qs('input',label); if(!input || !input.form) return;
    const sync=()=>qsa(`input[name=\"${input.name}\"]`, input.form).forEach(i=>{
      const host=i.closest(labelSelector); if(host) host.classList.toggle('is-active', i.checked);
    });
    input.addEventListener('change', sync);
    sync();
  });
}
function wireChoices(root=document){
  ['.mw504-choice','.mw503-segment label','.mw503-mode','.mw504-question-count label'].forEach(selector=>wireChoiceGroup(selector, root));
}
wireChoices();

function wireMultiplayerRulesets(){
  qsa('[data-mp-create],[data-mp-public]').forEach(form=>{
    const sync=()=>{
      const mode=qs('input[name="game_mode"]:checked',form)?.value||'ffa';
      const team=mode==='team_2v2';
      const cap3=qs('input[name="capacity"][value="3"]',form);
      const cap4=qs('input[name="capacity"][value="4"]',form);
      if(cap3){cap3.disabled=team;cap3.closest('.mw503-mode')?.classList.toggle('is-disabled',team);}
      if(team&&cap4){cap4.checked=true;cap4.dispatchEvent(new Event('change',{bubbles:true}));}
    };
    qsa('input[name="game_mode"]',form).forEach(input=>input.addEventListener('change',sync));
    sync();
  });
}
wireMultiplayerRulesets();

function wireWorldModeSwitch(){
  const root=qs('[data-world-mode-switch]'); if(!root)return;
  const buttons=qsa('[data-world-mode]',root); const panels=qsa('[data-world-mode-panel]',root);
  const setMode=(mode,{animate=true}={})=>{
    if(!['duel','multiplayer'].includes(mode))mode='duel';
    root.dataset.mode=mode;
    buttons.forEach(btn=>{const active=btn.dataset.worldMode===mode;btn.classList.toggle('is-active',active);btn.setAttribute('aria-selected',active?'true':'false');});
    panels.forEach(panel=>{const active=panel.dataset.worldModePanel===mode;panel.hidden=!active;panel.classList.toggle('is-active',active);if(active&&animate){panel.classList.remove('is-entering');void panel.offsetWidth;panel.classList.add('is-entering');setTimeout(()=>panel.classList.remove('is-entering'),420);}});
    const target=mode==='multiplayer'?'/world/multiplayer/':'/world/';
    try{history.replaceState({worldMode:mode},'',target);}catch(_){}
  };
  buttons.forEach(btn=>btn.addEventListener('click',()=>setMode(btn.dataset.worldMode)));
  let startX=null;
  root.addEventListener('pointerdown',e=>{if(e.pointerType==='mouse')return;startX=e.clientX;},{passive:true});
  root.addEventListener('pointerup',e=>{if(startX===null)return;const dx=e.clientX-startX;startX=null;if(Math.abs(dx)<45)return;setMode(dx<0?'multiplayer':'duel');},{passive:true});
  setMode(root.dataset.initialMode||'duel',{animate:false});
}
wireWorldModeSwitch();
qsa('[data-mp-create],[data-mp-join],[data-mp-public]').forEach(form=>form.addEventListener('submit',async e=>{
  e.preventDefault();
  const out=qs('[data-mp-status]',form); const btn=qs('button[type=submit]',form);
  if(btn)btn.disabled=true; if(out)out.textContent='';
  try{const p=await post(form.action,Object.fromEntries(new FormData(form).entries()));window.location.assign(p.room_url);}catch(err){if(out)out.textContent=err.message;if(btn)btn.disabled=false;}
}));

const room=qs('[data-mp-room]');
if(room){
  let last=null;
  let navigating=false;
  let accessPending=false;
  let readyPending=false;
  let swapPending=false;
  let pollBusy=false;
  let pulseBusy=false;
  let pollTimer=null;
  let pulseTimer=null;
  let stateVersion=Number(room.dataset.stateVersion||0);
  let myReady=room.dataset.myReady==='1';
  const safe=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const acceptState=p=>{const next=Number(p?.state_version||0);if(next&&next<stateVersion)return false;if(next>stateVersion)stateVersion=next;return true;};
  function applyAccessVisual(accessType){
    const isPublic=accessType==='public';
    qsa('[data-mp-private-only]',room).forEach(el=>{el.hidden=isPublic;});
    qsa('[data-mp-public-only]',room).forEach(el=>{el.hidden=!isPublic;});
    const accessLabel=qs('[data-mp-access-label]',room);if(accessLabel)accessLabel.textContent=`${isPublic?'PUBLIC':'PRIVATE'} ARENA`;
  }
  function renderTeamBoard(p){
    const board=qs('[data-mp-team-board]',room);if(!board||!p.is_team_mode)return;
    board.innerHTML=(p.team_standings||[]).map(team=>`<article class="mw504-team-card is-team-${safe(team.team)}${team.is_my_team?' is-mine':''}"><div><small>${safe(team.label).toUpperCase()}</small><strong>${team.members.length}/2 players</strong></div><div class="mw504-team-members">${team.members.map(member=>`<span title="${safe(member.name)}"><b>${safe(member.initials)}</b>${safe(member.name)}</span>`).join('')}</div></article>`).join('');
  }
  function renderSwapState(p){
    const incoming=qs('[data-mp-swap-popover]',room);
    const outgoing=qs('[data-mp-swap-outgoing]',room);
    if(incoming){
      const swap=p.swap_incoming;
      incoming.hidden=!swap;
      incoming.dataset.requestId=swap?.id||'';
      if(swap){
        const name=qs('[data-mp-swap-name]',incoming);if(name)name.textContent=swap.other_name;
        const text=qs('[data-mp-swap-text]',incoming);if(text)text.textContent=`wants to swap seat ${swap.other_seat} with your seat ${swap.my_seat}.`;
      }
    }
    if(outgoing){
      const swap=p.swap_outgoing;
      outgoing.hidden=!swap;
      outgoing.dataset.requestId=swap?.id||'';
      const copy=qs('[data-mp-swap-outgoing-copy]',outgoing);
      if(copy&&swap)copy.textContent=`Waiting for ${swap.other_name} · seat ${swap.other_seat}`;
    }
  }
  function render(p){
    if(p?.removed){
      if(!navigating){navigating=true;window.location.replace(p.redirect_url||'/world/multiplayer/?notice=kicked');}
      return;
    }
    if(!acceptState(p))return;
    last=p;
    if(typeof p.my_ready==='boolean')myReady=p.my_ready;
    if(p.is_host&&p.status==='lobby'&&!qs('[data-mp-start]',room)&&!navigating){navigating=true;window.location.reload();return;}
    const state=qs('[data-mp-room-state]',room);if(state)state.textContent=`${p.ready}/${p.occupied} ready`;
    const copy=qs('[data-mp-room-copy]',room);
    if(copy)copy.textContent=p.status==='active'?'Battle starts together…':(p.can_start?'Everyone is ready. Host can start.':(p.is_team_mode?'Need all 4 players and everyone ready.':'Need at least 3 players and everyone ready.'));
    renderTeamBoard(p);
    renderSwapState(p);
    const progress=qs('[data-mp-progress]',room); if(progress)progress.style.width=`${Math.min(100,Math.round((p.ready/Math.max(1,p.capacity))*100))}%`;
    const start=qs('[data-mp-start]',room); if(start)start.disabled=!p.can_start||p.status!=='lobby';
    if(!accessPending)applyAccessVisual(p.access_type);
    qsa('[data-mp-access-toggle]',room).forEach(btn=>{btn.disabled=accessPending||!p.is_host||p.status!=='lobby';});
    const hasSwap=!!(p.swap_incoming||p.swap_outgoing);
    p.seats.forEach(s=>{
      const el=qs(`[data-seat-number="${s.seat_number}"]`,room); if(!el)return;
      el.classList.toggle('is-occupied',!!s.occupied);el.classList.toggle('is-ready',!!s.is_ready);el.classList.toggle('is-team-a',p.is_team_mode&&s.team==='a');el.classList.toggle('is-team-b',p.is_team_mode&&s.team==='b');
      if(s.occupied){
        const swap=(p.is_team_mode&&!s.is_me&&s.is_active&&p.status==='lobby')?`<button type="button" class="mw504-swap-seat" data-mp-swap-request data-user-id="${s.user_id}" title="Request seat swap" ${hasSwap?'disabled':''}><i class="bi bi-arrow-left-right"></i><span>Swap</span></button>`:'';
        const kick=(p.is_host&&!s.is_host&&s.is_active)?`<button type="button" class="mw504-kick" data-mp-kick data-user-id="${s.user_id}" title="Remove player"><i class="bi bi-person-x-fill"></i><span>Kick</span></button>`:'';
        const stateText=!s.is_active?'LEFT':(!s.is_connected?'RECONNECTING':(s.is_ready?'READY':'NOT READY'));
        const team=p.is_team_mode&&s.team?`<em class="mw504-team-tag">TEAM ${s.team.toUpperCase()}</em> · `:'';
        el.innerHTML=`<span class="mw504-seat-no">${s.seat_number}</span><span class="mw503-avatar">${safe(s.initials)}</span><div class="mw504-seat-copy"><strong>${safe(s.name)}</strong><small>${team}${s.is_host?'HOST · ':''}<span>${stateText}</span></small></div><div class="mw504-seat-actions">${swap}${kick}</div>`;
      }else{
        el.innerHTML=`<span class="mw504-seat-no">${s.seat_number}</span><span class="mw504-empty-icon"><i class="bi bi-person-plus"></i></span><div class="mw504-seat-copy"><strong>Open seat</strong><small>Waiting for player</small></div>`;
      }
    });
    const ready=qs('[data-mp-ready]',room);
    if(ready){
      ready.dataset.readyState=myReady?'1':'0';
      ready.setAttribute('aria-pressed',myReady?'true':'false');
      ready.textContent=myReady?'Not ready':'Ready';
      ready.disabled=readyPending||p.status!=='lobby';
      ready.classList.toggle('is-ready-state',myReady);
    }
    if(p.status==='active'&&!navigating){navigating=true;window.location.assign(p.play_url||room.dataset.playUrl);}
  }
  const schedulePoll=(delay)=>{clearTimeout(pollTimer);if(!navigating)pollTimer=setTimeout(poll,delay);};
  async function poll(){
    if(navigating||accessPending||pollBusy){schedulePoll(document.hidden?3000:1100);return;}
    if(document.hidden){schedulePoll(3000);return;}
    pollBusy=true;
    try{render(await getJSON(room.dataset.statusUrl));}catch(_){}
    finally{pollBusy=false;schedulePoll(1100);}
  }
  const heartbeatUrl=room.dataset.heartbeatUrl||(room.dataset.statusUrl||'').replace(/status\/?$/,'heartbeat/');
  const schedulePulse=(delay=6500)=>{clearTimeout(pulseTimer);if(!navigating)pulseTimer=setTimeout(pulse,delay);};
  async function pulse(){
    if(navigating||pulseBusy||!heartbeatUrl)return;
    if(document.hidden){schedulePulse(9000);return;}
    pulseBusy=true;
    try{const p=await post(heartbeatUrl);acceptState(p);}
    catch(err){const p=err.payload||{};if(p.removed&&!navigating){navigating=true;window.location.replace(p.redirect_url||'/world/multiplayer/?notice=disconnected');return;}}
    finally{pulseBusy=false;if(!navigating)schedulePulse();}
  }
  qs('[data-mp-ready]',room)?.addEventListener('click',async e=>{
    if(readyPending||navigating)return;
    const btn=e.currentTarget;
    const desired=!myReady;
    readyPending=true;
    myReady=desired;
    btn.dataset.readyState=desired?'1':'0';btn.setAttribute('aria-pressed',desired?'true':'false');btn.textContent=desired?'Not ready':'Ready';btn.disabled=true;btn.classList.toggle('is-ready-state',desired);
    try{render(await post(room.dataset.readyUrl,{ready:desired?'1':'0'}));}
    catch(err){myReady=!desired;const copy=qs('[data-mp-room-copy]',room);if(copy)copy.textContent=err.message;poll();}
    finally{readyPending=false;if(last)render(last);}
  });
  qs('[data-mp-start]',room)?.addEventListener('click',async e=>{
    const btn=e.currentTarget;if(btn.disabled||navigating)return;btn.disabled=true;btn.classList.add('is-pending');const original=btn.innerHTML;btn.innerHTML='<i class="bi bi-hourglass-split"></i> Starting…';
    try{const p=await post(room.dataset.startUrl);render(p);}
    catch(err){const copy=qs('[data-mp-room-copy]',room);if(copy)copy.textContent=err.message;btn.disabled=false;btn.classList.remove('is-pending');btn.innerHTML=original;poll();}
  });
  qs('[data-mp-leave-form]',room)?.addEventListener('submit',e=>{
    e.preventDefault();if(navigating)return;navigating=true;clearTimeout(pollTimer);clearTimeout(pulseTimer);
    const btn=qs('[data-mp-leave]',e.currentTarget);if(btn){btn.disabled=true;btn.classList.add('is-pending');btn.textContent='Leaving…';}
    postKeepalive(room.dataset.leaveUrl).catch(()=>{});window.location.replace(room.dataset.leaveRedirectUrl||'/world/multiplayer/');
  });
  qsa('[data-mp-access-form]',room).forEach(form=>form.addEventListener('submit',async e=>{
    e.preventDefault();if(accessPending||navigating)return;
    const target=(new FormData(form).get('access_type')||'').toString();const previous=last?.access_type||(target==='public'?'private':'public');accessPending=true;applyAccessVisual(target);
    qsa('[data-mp-access-toggle]',room).forEach(btn=>{btn.disabled=true;btn.classList.add('is-pending');});
    try{const p=await post(room.dataset.accessUrl,{access_type:target});accessPending=false;qsa('[data-mp-access-toggle]',room).forEach(btn=>btn.classList.remove('is-pending'));render(p);const out=qs('[data-mp-room-copy]',room);if(out&&p.message)out.textContent=p.message;}
    catch(err){accessPending=false;applyAccessVisual(previous);qsa('[data-mp-access-toggle]',room).forEach(btn=>{btn.disabled=false;btn.classList.remove('is-pending');});const out=qs('[data-mp-room-copy]',room);if(out)out.textContent=err.message;poll();}
  }));
  qsa('[data-mp-copy]',room).forEach(b=>b.addEventListener('click',async e=>{const el=e.currentTarget;const value=el.dataset.copyValue||el.dataset.code||'';try{await navigator.clipboard.writeText(value);el.classList.add('is-copied');if(el.matches('.mw503-result-action')){el.dataset.copyLabel=el.textContent.trim();el.innerHTML='<i class="bi bi-check2"></i> Copied';}setTimeout(()=>{el.classList.remove('is-copied');if(el.matches('.mw503-result-action')&&el.dataset.copyLabel)el.innerHTML='<i class="bi bi-copy"></i> '+el.dataset.copyLabel.replace(/^Copied$/,'Copy link');},1100);}catch(_){const copy=qs('[data-mp-room-copy]',room);if(copy)copy.textContent='Could not copy. Select the invite link manually.';} }));
  qs('[data-mp-share]',room)?.addEventListener('click',async e=>{const b=e.currentTarget;const url=b.dataset.shareUrl||room.dataset.inviteUrl;const code=b.dataset.shareCode||'';const data={title:'MakonBook World Multiplayer',text:`Join my MakonBook World battle · room ${code}`,url};try{if(navigator.share){await navigator.share(data);}else{await navigator.clipboard.writeText(url);b.innerHTML='<i class="bi bi-check2"></i> Invite link copied';setTimeout(()=>b.innerHTML='<i class="bi bi-person-plus-fill"></i> Invite friends',1200);}}catch(err){if(err?.name!=='AbortError'){const copy=qs('[data-mp-room-copy]',room);if(copy)copy.textContent='Could not open sharing. Copy the invite link instead.';}}});
  room.addEventListener('click',async e=>{
    const kick=e.target.closest('[data-mp-kick]');
    if(kick){const name=kick.closest('.mw504-seat')?.querySelector('strong')?.textContent||'this player';if(!window.confirm(`Remove ${name} from the room?`))return;kick.disabled=true;try{render(await post(room.dataset.kickUrl,{user_id:kick.dataset.userId}));}catch(err){const copy=qs('[data-mp-room-copy]',room);if(copy)copy.textContent=err.message;kick.disabled=false;}return;}
    const swap=e.target.closest('[data-mp-swap-request]');
    if(swap){if(swapPending)return;swapPending=true;swap.disabled=true;try{render(await post(room.dataset.swapRequestUrl,{target_user_id:swap.dataset.userId}));}catch(err){const copy=qs('[data-mp-room-copy]',room);if(copy)copy.textContent=err.message;swap.disabled=false;}finally{swapPending=false;}return;}
  });
  qs('[data-mp-swap-accept]',room)?.addEventListener('click',async()=>{const box=qs('[data-mp-swap-popover]',room);if(!box?.dataset.requestId||swapPending)return;swapPending=true;try{render(await post(room.dataset.swapRespondUrl,{request_id:box.dataset.requestId,action:'accept'}));}catch(err){const copy=qs('[data-mp-room-copy]',room);if(copy)copy.textContent=err.message;}finally{swapPending=false;}});
  qs('[data-mp-swap-decline]',room)?.addEventListener('click',async()=>{const box=qs('[data-mp-swap-popover]',room);if(!box?.dataset.requestId||swapPending)return;swapPending=true;try{render(await post(room.dataset.swapRespondUrl,{request_id:box.dataset.requestId,action:'decline'}));}catch(err){const copy=qs('[data-mp-room-copy]',room);if(copy)copy.textContent=err.message;}finally{swapPending=false;}});
  qs('[data-mp-swap-cancel]',room)?.addEventListener('click',async()=>{const box=qs('[data-mp-swap-outgoing]',room);if(!box?.dataset.requestId||swapPending)return;swapPending=true;try{render(await post(room.dataset.swapCancelUrl,{request_id:box.dataset.requestId}));}catch(err){const copy=qs('[data-mp-room-copy]',room);if(copy)copy.textContent=err.message;}finally{swapPending=false;}});
  pulse();poll();
  document.addEventListener('visibilitychange',()=>{if(!document.hidden){pulse();poll();}});
  window.addEventListener('focus',()=>{pulse();poll();});
}

const kickedNotice=qs('[data-mp-kicked-notice]');
if(kickedNotice){
  requestAnimationFrame(()=>kickedNotice.classList.add('is-open'));
  const close=()=>{
    kickedNotice.classList.remove('is-open');
    setTimeout(()=>{kickedNotice.hidden=true;},180);
    try{
      const url=new URL(window.location.href);
      url.searchParams.delete('notice');
      history.replaceState(history.state,'',url.pathname+(url.searchParams.toString()?'?'+url.searchParams.toString():'')+url.hash);
    }catch(_){}
  };
  kickedNotice.addEventListener('click',e=>{if(e.target===kickedNotice||e.target.closest('[data-mp-kicked-close]'))close();});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!kickedNotice.hidden)close();});
}

const play=qs('[data-mp-play]');
if(play){
  let initialIndex=Number(play.dataset.questionIndex||0);
  let done=play.dataset.roomStatus==='completed';
  let pollBusy=false;
  let pulseBusy=false;
  let revealMode=play.dataset.roundReveal==='1';
  let launchWaiting=play.dataset.launchWaiting==='1';
  let launchMode=play.dataset.openingCountdown==='1';
  let stateVersion=Number(play.dataset.stateVersion||0);
  let playPollTimer=null;
  let playPulseTimer=null;
  const acceptPlayState=p=>{const next=Number(p?.state_version||0);if(next&&next<stateVersion)return false;if(next>stateVersion)stateVersion=next;return true;};
  function renderScores(p){p.seats?.forEach(s=>{if(!s.occupied)return;const el=qs(`[data-mp-score-user="${s.user_id}"]`);if(el)el.textContent=s.score;});p.team_standings?.forEach(team=>{const el=qs(`[data-mp-team-score="${team.team}"]`);if(el)el.textContent=team.score;});}
  const schedulePlayPoll=(delay)=>{clearTimeout(playPollTimer);if(!done)playPollTimer=setTimeout(pollPlay,delay);};
  async function pollPlay(){
    if(done||pollBusy)return;
    if(document.hidden){schedulePlayPoll(2600);return;}
    pollBusy=true;
    try{
      const p=await getJSON(play.dataset.statusUrl);
      if(p.removed){done=true;window.location.replace(p.redirect_url||'/world/multiplayer/?notice=disconnected');return;}
      if(!acceptPlayState(p))return;
      renderScores(p);
      if(p.status==='completed'){done=true;window.location.replace(play.dataset.playUrl);return;}
      if(launchWaiting&&!p.launch_waiting){done=true;window.location.replace(play.dataset.playUrl);return;}
      if(launchMode&&!p.opening_countdown){done=true;window.location.replace(play.dataset.playUrl);return;}
      if(revealMode&&!p.round_reveal){done=true;window.location.replace(play.dataset.playUrl);return;}
      if(!launchWaiting&&!launchMode&&!revealMode&&Number(p.current_question_index)!==initialIndex){done=true;window.location.replace(play.dataset.playUrl);return;}
    }catch(_){}
    finally{pollBusy=false;if(!done)schedulePlayPoll(950);}
  }
  const playHeartbeatUrl=play.dataset.heartbeatUrl||(play.dataset.statusUrl||'').replace(/status\/?$/,'heartbeat/');
  const schedulePlayPulse=(delay=6500)=>{clearTimeout(playPulseTimer);if(!done)playPulseTimer=setTimeout(pulsePlay,delay);};
  async function pulsePlay(){
    if(done||pulseBusy||!playHeartbeatUrl)return;
    if(document.hidden){schedulePlayPulse(9000);return;}
    pulseBusy=true;
    try{acceptPlayState(await post(playHeartbeatUrl,{arena:'1'}));}
    catch(err){const p=err.payload||{};if(p.removed){done=true;window.location.replace(p.redirect_url||'/world/multiplayer/?notice=disconnected');return;}}
    finally{pulseBusy=false;if(!done)schedulePlayPulse();}
  }
  const form=qs('[data-mp-answer]');
  if(form)form.addEventListener('submit',async e=>{
    e.preventDefault();if(done)return;const btn=qs('button[type=submit]',form);const label=qs('[data-mp-lock-label]',form);if(btn)btn.disabled=true;if(label)label.textContent='Locking…';
    try{const p=await post(play.dataset.answerUrl,Object.fromEntries(new FormData(form).entries()));acceptPlayState(p);renderScores(p);done=false;form.closest('.mw504-question-card').innerHTML='<section class="mw504-inline-wait"><span class="mw503-radar" data-world-radar><i></i><b></b><em class="mw503-radar-blip"></em><em class="mw503-radar-blip"></em></span><small>ANSWER LOCKED</small><h2>Waiting for other players</h2><p>The room advances together.</p></section>';if(p.status==='completed'||p.advanced){await sleep(220);window.location.replace(p.play_url);}}catch(err){if(label)label.textContent=err.message;if(btn)btn.disabled=false;}
  });
  const reveal=qs('[data-mp-rank-reveal]');
  if(reveal){
    const rows=qsa('[data-final-rank]',reveal);
    const scores=rows.map(row=>Number(row.dataset.score||0));
    const maxScore=Math.max(1,...scores);
    const step=rows.length?Math.max(64,rows[0].getBoundingClientRect().height+10):72;
    rows.forEach(row=>{
      const previous=Number(row.dataset.previousRank||row.dataset.finalRank||1);
      const finalRank=Number(row.dataset.finalRank||1);
      const shift=(previous-finalRank)*step;
      row.style.setProperty('--rank-shift',`${shift}px`);
      row.style.setProperty('--score-pct',`${Math.max(10,Math.min(100,(Number(row.dataset.score||0)/maxScore)*100))}%`);
    });
    const animateNumber=(el,from,to,duration=720)=>{
      if(!el)return;
      const start=performance.now();
      const tick=now=>{
        const p=Math.min(1,(now-start)/duration);
        const eased=1-Math.pow(1-p,3);
        el.textContent=Math.round(from+(to-from)*eased);
        if(p<1)requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
      reveal.classList.add('is-live');
      rows.forEach((row,index)=>{
        const score=qs('[data-mp-animated-score]',row);
        const pop=qs('[data-mp-point-pop]',row);
        const from=Number(row.dataset.previousScore||0);
        const to=Number(row.dataset.score||0);
        setTimeout(()=>{
          animateNumber(score,from,to,760);
          if(pop&&Number(row.dataset.lastPoints||0)>0){pop.classList.add('is-visible');setTimeout(()=>pop.classList.remove('is-visible'),1250);}
        },220+(index*95));
      });
    }));
    let left=Math.max(0,Number(reveal.dataset.revealSeconds||0));
    const out=qs('[data-mp-reveal-count]',reveal);
    const bar=qs('[data-mp-reveal-progress]',reveal);
    const total=Math.max(1,left);
    const tickReveal=()=>{
      if(out)out.textContent=Math.max(0,left);
      if(bar)bar.style.width=`${Math.max(0,Math.min(100,((total-left)/total)*100))}%`;
      if(left<=0){pollPlay();return;}
      left-=1;
      setTimeout(tickReveal,1000);
    };
    tickReveal();
  }
  const launch=qs('[data-mp-opening-countdown]');
  if(launch){
    let left=Math.max(0,Number(launch.dataset.startSeconds||0));
    const out=qs('[data-mp-start-count]',launch);
    const bar=qs('[data-mp-start-progress]',launch);
    const total=Math.max(1,left);
    const tickLaunch=()=>{
      if(out)out.textContent=Math.max(0,left);
      if(bar)bar.style.width=`${Math.max(0,Math.min(100,((total-left)/total)*100))}%`;
      if(left<=0){pollPlay();return;}
      left-=1;
      setTimeout(tickLaunch,1000);
    };
    tickLaunch();
  }
  const timer=qs('[data-mp-countdown]');
  if(timer){let left=Math.max(0,Number(timer.dataset.seconds||0));const out=qs('b',timer);const tick=()=>{if(out)out.textContent=Math.max(0,left);if(left<=0){pollPlay();return;}left-=1;setTimeout(tick,1000);};tick();}
  pulsePlay();pollPlay();
  window.addEventListener('focus',()=>{if(!done){pulsePlay();pollPlay();}});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&!done){pulsePlay();pollPlay();}});
}

})();
