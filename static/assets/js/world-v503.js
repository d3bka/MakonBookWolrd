(function(){
  'use strict';

  const qs=(selector,root=document)=>root.querySelector(selector);
  const qsa=(selector,root=document)=>Array.from(root.querySelectorAll(selector));
  const absolute=url=>new URL(url,window.location.href).toString();
  function cookieValue(name){
    const prefix=`${name}=`;
    for(const part of String(document.cookie||'').split(';')){
      const item=part.trim();
      if(item.startsWith(prefix))return decodeURIComponent(item.slice(prefix.length));
    }
    return '';
  }
  const csrf=()=>{
    const shell=qs('[data-world-shell]');
    const cookieName=String(shell?.dataset?.csrfCookieName||'').trim();
    // Use Django's configured CSRF cookie name, not a hard-coded `csrftoken`.
    // MakonBook intentionally uses a versioned custom cookie name.
    if(cookieName){
      const cookie=cookieValue(cookieName);
      if(cookie&&cookie.length>=32)return cookie;
    }
    // A masked token rendered by {% csrf_token %} is also valid and is the
    // safest fallback when cookies are HttpOnly or unavailable to JS.
    const hidden=qsa('input[name=csrfmiddlewaretoken]').map(el=>String(el.value||'').trim()).find(value=>value.length>=32);
    if(hidden)return hidden;
    // Legacy fallback only for installs that still use Django's default.
    const legacy=cookieValue('csrftoken');
    return legacy&&legacy.length>=32?legacy:'';
  };
  const reducedMotion=()=>window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const worldHome=qs('[data-world-home]');
  if(worldHome){
    document.documentElement.classList.add('mw-world-home-active');
    window.addEventListener('pagehide',()=>document.documentElement.classList.remove('mw-world-home-active'),{once:true});
  }

  function renderWorldMath(root=document){
    if(typeof window.renderMathInElement!=='function')return;
    // SAT prompts frequently contain currency such as $3,000. Treating a
    // single dollar sign as a KaTeX delimiter can swallow the rest of the
    // prompt and leave valid \( ... \) math unrendered. World therefore
    // accepts the unambiguous delimiters used by MakonBook imports only.
    try{
      window.renderMathInElement(root,{
        delimiters:[
          {left:'\\[',right:'\\]',display:true},
          {left:'\\(',right:'\\)',display:false},
          {left:'$$',right:'$$',display:true}
        ],
        throwOnError:false,
        strict:false
      });
    }catch(_error){}
  }

  let statusPoll=null;
  let queueTimer=null;
  let countdownTimer=null;
  let heartbeatTimer=null;
  let matchId=null;
  let queueStarted=0;
  let queueLimit=60;
  let answerSubmitting=false;
  let awaitingNextQuestion=false;
  let queuePollBusy=false;
  let queuePollNow=null;
  let rematchIncomingTimer=null;
  let rematchCountdownTimer=null;
  let activeIncomingInvite=null;
  let rematchRequestPoll=null;

  function xhrJson(url,opts={}){
    return new Promise((resolve,reject)=>{
      const method=String(opts.method||'GET').toUpperCase();
      const xhr=new XMLHttpRequest();
      xhr.open(method,absolute(url),true);
      xhr.withCredentials=true;
      xhr.setRequestHeader('X-Requested-With','XMLHttpRequest');
      const headers={...(opts.headers||{})};
      if(method!=='GET'&&method!=='HEAD'){
        const token=csrf();
        if(token&&!headers['X-CSRFToken']&&!headers['X-Csrftoken'])headers['X-CSRFToken']=token;
        if(opts.body instanceof FormData&&token&&!opts.body.has('csrfmiddlewaretoken'))opts.body.append('csrfmiddlewaretoken',token);
      }
      Object.entries(headers).forEach(([key,value])=>{
        if(value!==undefined&&value!==null)xhr.setRequestHeader(key,String(value));
      });
      xhr.onload=()=>{
        const type=xhr.getResponseHeader('content-type')||'';
        if(!type.includes('application/json')){
          reject(new Error(`World request returned ${xhr.status} instead of JSON.`));
          return;
        }
        let data;
        try{data=JSON.parse(xhr.responseText||'{}');}
        catch(_error){reject(new Error('World returned invalid JSON.'));return;}
        if(xhr.status<200||xhr.status>=300||!data.ok){
          reject(new Error(data.error||`World request failed (${xhr.status}).`));
          return;
        }
        resolve(data);
      };
      xhr.onerror=()=>reject(new Error('Network request failed. Please retry.'));
      xhr.ontimeout=()=>reject(new Error('World request timed out. Please retry.'));
      xhr.timeout=15000;
      xhr.send(opts.body||null);
    });
  }

  async function jsonFetch(url,opts={}){
    const method=String(opts.method||'GET').toUpperCase();
    // Firefox intermittently reports NetworkError for same-origin FormData POSTs
    // on the duel page. XHR is intentionally used for mutating requests.
    if(method!=='GET'&&method!=='HEAD')return xhrJson(url,opts);
    try{
      const res=await fetch(absolute(url),{
        credentials:'same-origin',
        cache:'no-store',
        headers:{'X-Requested-With':'XMLHttpRequest','Cache-Control':'no-cache',...(opts.headers||{})},
        ...opts,
      });
      const type=res.headers.get('content-type')||'';
      if(!type.includes('application/json'))throw new Error(`World request returned ${res.status} instead of JSON.`);
      const data=await res.json();
      if(!res.ok||!data.ok)throw new Error(data.error||'World request failed.');
      return data;
    }catch(error){
      if(error&&/World request returned|World request failed/.test(String(error.message||'')))throw error;
      return xhrJson(url,opts);
    }
  }

  function clearAllPolling(){
    if(statusPoll)clearInterval(statusPoll);
    if(queueTimer)clearInterval(queueTimer);
    if(countdownTimer)clearInterval(countdownTimer);
    if(heartbeatTimer)clearInterval(heartbeatTimer);
    if(rematchIncomingTimer)clearTimeout(rematchIncomingTimer);
    if(rematchCountdownTimer)clearInterval(rematchCountdownTimer);
    if(rematchRequestPoll)clearTimeout(rematchRequestPoll);
    statusPoll=queueTimer=countdownTimer=heartbeatTimer=rematchIncomingTimer=rematchCountdownTimer=rematchRequestPoll=null;
  }

  function animateCount(el){
    const target=Number(el.dataset.worldCountTo||0);
    if(!Number.isFinite(target))return;
    if(reducedMotion()){
      el.textContent=String(target);
      return;
    }
    const duration=Math.min(950,420+Math.abs(target)*.28);
    const started=performance.now();
    const step=now=>{
      const progress=Math.min(1,(now-started)/duration);
      const eased=1-Math.pow(1-progress,3);
      el.textContent=String(Math.round(target*eased));
      if(progress<1)requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  qsa('[data-world-count-to]').forEach(animateCount);

  function syncWorldPlayerRating(subject){
    const card=qs('[data-world-player-card]');
    if(!card)return;
    const key=subject==='rw'?'rw':'math';
    const source=qs(`[data-world-rating-source][data-subject="${key}"]`,card);
    if(!source)return;

    const label=qs('[data-world-rating-label]',card);
    const rating=qs('[data-world-rating-number]',card);
    const tier=qs('[data-world-rating-tier]',card);
    const tierText=qs('[data-world-rating-tier-text]',card);
    const rank=qs('[data-world-rating-rank]',card);
    if(label)label.textContent=`${source.dataset.label||'Math'} rating`;
    if(rating){
      rating.dataset.worldCountTo=String(source.dataset.rating||0);
      animateCount(rating);
    }
    if(tier){
      Array.from(tier.classList).filter(name=>name.startsWith('mw503-tier-')).forEach(name=>tier.classList.remove(name));
      tier.classList.add(`mw503-tier-${String(source.dataset.tier||'BRONZE').toLowerCase()}`);
    }
    if(tierText)tierText.textContent=String(source.dataset.tier||'BRONZE').toUpperCase();
    if(rank)rank.textContent=`#${source.dataset.rank||'-'}`;
    ['wins','losses','draws','streak'].forEach(name=>{
      const node=qs(`[data-world-record="${name}"]`,card);
      if(!node)return;
      node.dataset.worldCountTo=String(source.dataset[name]||0);
      animateCount(node);
    });
  }

  document.addEventListener('change',event=>{
    const label=event.target.closest('.mw503-mode,.mw503-subjects label');
    if(!label)return;
    qsa('label',label.parentElement).forEach(item=>item.classList.toggle('is-active',!!qs('input:checked',item)));
    const input=event.target.closest('input[name="subject"]');
    if(input&&input.closest('[data-world-matchmaker]'))syncWorldPlayerRating(input.value);
  });

  function initRadars(root=document){
    qsa('[data-world-radar]',root).forEach(radar=>{
      if(radar.dataset.radarReady==='1')return;
      radar.dataset.radarReady='1';
      const movingDot=qs('b',radar);
      const blips=qsa('.mw503-radar-blip',radar);

      const randomPoint=(minRadius=7,maxRadius=25)=>{
        const angle=Math.random()*Math.PI*2;
        const radius=minRadius+Math.random()*(maxRadius-minRadius);
        return {
          x:Math.cos(angle)*radius,
          y:Math.sin(angle)*radius,
        };
      };

      const blinkAtRandomPoint=(node,{primary=false}={})=>{
        if(!node)return;
        const point=randomPoint(primary?9:6,primary?27:25);
        node.style.left=`calc(50% + ${point.x.toFixed(1)}px)`;
        node.style.top=`calc(50% + ${point.y.toFixed(1)}px)`;
        node.style.animation='none';
        // Force a fresh animation frame so the same radar contact can blink again.
        void node.offsetWidth;
        const duration=primary?(0.55+Math.random()*0.5):(0.75+Math.random()*0.9);
        node.style.animation=`mwRadarContactBlink ${duration.toFixed(2)}s ease-out both`;
      };

      if(movingDot){
        const primaryLoop=()=>{
          blinkAtRandomPoint(movingDot,{primary:true});
          window.setTimeout(primaryLoop,520+Math.random()*1050);
        };
        primaryLoop();
      }

      blips.forEach((blip,index)=>{
        const loop=()=>{
          blinkAtRandomPoint(blip);
          window.setTimeout(loop,820+Math.random()*1650+(index*120));
        };
        window.setTimeout(loop,index*180);
      });
    });
  }
  initRadars();
  renderWorldMath(document);

  const matchmaker=qs('[data-world-matchmaker]');
  const queueLayer=qs('[data-world-queue]');
  const queueMessage=qs('[data-world-queue-message]');

  function resetQueueUi(){
    if(statusPoll)clearInterval(statusPoll);
    if(queueTimer)clearInterval(queueTimer);
    statusPoll=queueTimer=null;
    queuePollBusy=false;
    queuePollNow=null;
    if(queueLayer)queueLayer.hidden=true;
    const button=qs('[data-world-find]');
    if(button)button.disabled=false;
    const status=qs('[data-world-status]');
    if(status)status.textContent='';
    matchId=null;
  }

  async function cancelQueue({quiet=false}={}){
    if(!matchId){resetQueueUi();return;}
    try{
      await jsonFetch(`/world/queue/${matchId}/cancel/`,{method:'POST',headers:{'X-CSRFToken':csrf()}});
    }catch(error){
      if(!quiet&&queueMessage)queueMessage.textContent=error.message;
    }
    resetQueueUi();
  }

  function showQueue(secondsRemaining){
    if(!queueLayer)return;
    queueLayer.hidden=false;
    initRadars(queueLayer);
    queueStarted=Date.now();
    const initial=Math.max(1,Number(secondsRemaining||queueLimit));
    queueLimit=Math.max(1,Number(queueLimit||60));
    if(queueMessage)queueMessage.textContent='';

    const paint=()=>{
      const elapsed=Math.floor((Date.now()-queueStarted)/1000);
      const remaining=Math.max(0,initial-elapsed);
      const time=qs('[data-world-queue-time]');
      const bar=qs('[data-world-queue-progress]');
      if(time){
        const used=Math.max(0,queueLimit-remaining);
        time.textContent=`${String(Math.floor(used/60)).padStart(2,'0')}:${String(used%60).padStart(2,'0')}`;
      }
      if(bar){
        const percent=Math.min(100,Math.max(0,((queueLimit-remaining)/queueLimit)*100));
        bar.style.width=`${percent}%`;
      }
      if(remaining<=0){
        if(statusPoll)clearInterval(statusPoll);
        if(queueTimer)clearInterval(queueTimer);
        if(queueMessage)queueMessage.textContent='No suitable opponent was found in time. Try again when more players are online.';
        setTimeout(()=>cancelQueue({quiet:true}),1200);
      }
    };
    paint();
    queueTimer=setInterval(paint,1000);

    const pollQueueStatus=async()=>{
      if(queuePollBusy||!matchId)return;
      queuePollBusy=true;
      try{
        const data=await jsonFetch(`/world/queue/${matchId}/status/?_=${Date.now()}`);
        if(data.status==='active'){
          if(statusPoll)clearInterval(statusPoll);
          if(queueTimer)clearInterval(queueTimer);
          statusPoll=queueTimer=null;
          if(queueLayer)queueLayer.hidden=true;
          location.replace(`${data.room_url}?intro=1`);
          return;
        }
        if(data.queue_timed_out||(data.status==='cancelled'&&Number(data.queue_seconds_remaining||0)===0)){
          if(statusPoll)clearInterval(statusPoll);
          if(queueTimer)clearInterval(queueTimer);
          if(queueMessage)queueMessage.textContent='No suitable opponent was found in time. Queue closed automatically.';
          setTimeout(()=>resetQueueUi(),1600);
        }
      }catch(_error){}
      finally{queuePollBusy=false;}
    };
    queuePollNow=pollQueueStatus;
    pollQueueStatus();
    statusPoll=setInterval(pollQueueStatus,250);
  }

  if(matchmaker){
    matchmaker.addEventListener('submit',async event=>{
      event.preventDefault();
      const button=qs('[data-world-find]',matchmaker);
      const status=qs('[data-world-status]',matchmaker);
      if(!button)return;
      button.disabled=true;
      if(status)status.textContent='Entering matchmaking…';
      try{
        const data=await jsonFetch(matchmaker.dataset.joinUrl,{method:'POST',body:new FormData(matchmaker)});
        matchId=data.match_id;
        queueLimit=Number(data.queue_limit_seconds||matchmaker.dataset.queueLimit||60);
        if(data.status==='active'){
          location.replace(`${data.room_url}?intro=1`);
          return;
        }
        if(status)status.textContent='';
        showQueue(data.queue_seconds_remaining||queueLimit);
      }catch(error){
        if(status)status.textContent=error.message;
        button.disabled=false;
      }
    });
  }

  window.addEventListener('focus',()=>{if(queuePollNow)queuePollNow();});
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&queuePollNow)queuePollNow();});

  qs('[data-world-queue-close]')?.addEventListener('click',()=>cancelQueue());

  function renderLeaderboardRows(container,rows){
    qsa('article,.mw503-empty',container).forEach(node=>node.remove());
    if(!rows.length){
      const empty=document.createElement('div');
      empty.className='mw503-empty';
      empty.textContent='No players matched your search.';
      container.appendChild(empty);
      return;
    }
    rows.forEach(row=>{
      const article=document.createElement('article');
      if(row.is_me){article.id='me';article.className='is-me';}

      const place=document.createElement('span');
      place.className='mw503-place';
      place.textContent=String(row.rank);

      const player=document.createElement('span');
      player.className='mw503-player-cell';
      const playerLink=document.createElement('a');
      playerLink.className='mw503-player-link';
      playerLink.href=row.profile_url||'#';
      const avatar=document.createElement('b');
      avatar.className='mw503-row-avatar';
      avatar.textContent=row.initials;
      const info=document.createElement('span');
      const name=document.createElement('strong');
      name.textContent=row.name;
      const username=document.createElement('small');
      username.textContent=`@${row.username}`;
      info.append(name,username);
      playerLink.append(avatar,info);
      player.appendChild(playerLink);
      if(row.is_me){const you=document.createElement('em');you.textContent='You';player.appendChild(you);}

      const tier=document.createElement('span');
      tier.className=`mw503-tier mw503-tier-${String(row.tier).toLowerCase()} small`;
      tier.innerHTML='<i class="bi bi-award"></i>';
      tier.appendChild(document.createTextNode(String(row.tier).toUpperCase()));

      const rating=document.createElement('strong');
      rating.className='mw503-score';
      rating.dataset.worldCountTo=String(row.rating);
      rating.textContent='0';

      const wl=document.createElement('span');
      wl.className='mw503-wl';
      const wins=document.createElement('b');wins.textContent=String(row.wins);
      const slash=document.createTextNode(' / ');
      const losses=document.createElement('em');losses.textContent=String(row.losses);
      wl.append(wins,slash,losses);

      article.append(place,player,tier,rating,wl);
      container.appendChild(article);
      animateCount(rating);
    });
  }

  const rankSearch=qs('[data-world-rank-search]');
  if(rankSearch){
    const input=qs('[data-world-rank-query]',rankSearch);
    const results=qs('[data-world-rank-results]');
    const state=qs('[data-world-rank-search-state]',rankSearch);
    let debounce=null;
    let controller=null;

    const runSearch=async()=>{
      if(!input||!results)return;
      const query=input.value.trim();
      if(state)state.textContent=query?'Searching…':'Top players';
      if(controller)controller.abort();
      controller=new AbortController();
      try{
        const url=new URL(rankSearch.dataset.searchUrl,window.location.href);
        url.searchParams.set('subject',rankSearch.dataset.subject||'math');
        url.searchParams.set('q',query);
        const response=await fetch(url.toString(),{credentials:'same-origin',headers:{'X-Requested-With':'XMLHttpRequest'},signal:controller.signal});
        const data=await response.json();
        if(!response.ok||!data.ok)throw new Error(data.error||'Search failed.');
        renderLeaderboardRows(results,data.rows||[]);
        if(state)state.textContent=query?`${data.rows.length} result${data.rows.length===1?'':'s'}`:'Top players';
        const current=new URL(window.location.href);
        if(query)current.searchParams.set('q',query);else current.searchParams.delete('q');
        history.replaceState(null,'',current.toString());
      }catch(error){
        if(error.name==='AbortError')return;
        if(state)state.textContent='Search unavailable';
      }
    };
    rankSearch.addEventListener('submit',event=>{event.preventDefault();runSearch();});
    input?.addEventListener('input',()=>{
      clearTimeout(debounce);
      debounce=setTimeout(runSearch,220);
    });
  }

  function initImageLightbox(root=document){
    const lightbox=qs('[data-world-image-lightbox]',root);
    if(!lightbox)return;
    qs('[data-world-image-open]',root)?.addEventListener('click',()=>{lightbox.hidden=false;document.body.style.overflow='hidden';});
    const close=()=>{lightbox.hidden=true;document.body.style.overflow='';};
    qs('[data-world-image-close]',lightbox)?.addEventListener('click',close);
    lightbox.addEventListener('click',event=>{if(event.target===lightbox)close();});
    window.addEventListener('keydown',event=>{if(event.key==='Escape'&&!lightbox.hidden)close();});
  }
  initImageLightbox();

  function updateQuestionProgress(data){
    const progress=qs('.mw503-versus>span small');
    if(progress&&Number.isFinite(Number(data.next_question_number))){
      progress.textContent=`QUESTION ${data.next_question_number} / ${data.total_questions}`;
    }
  }

  function showBetweenQuestions(data){
    const stage=qs('.mw503-duel-stage');
    if(!stage)return;
    let wait=qs('[data-world-between-questions]',stage);
    if(!wait){
      wait=document.createElement('section');
      wait.className='mw503-wait-room compact';
      wait.setAttribute('data-world-between-questions','');
      wait.innerHTML='<span class="mw503-radar" data-world-radar><i></i><b></b><em class="mw503-radar-blip"></em><em class="mw503-radar-blip"></em><em class="mw503-radar-blip"></em></span><small>ANSWER LOCKED</small><h2>Waiting for opponent</h2><p data-world-wait-copy></p>';
      stage.appendChild(wait);
    }
    const card=qs('[data-world-question-card]',stage);
    if(card)card.remove();
    const answered=Math.max(0,Number(data.my_answered_count||0));
    const total=Math.max(0,Number(data.total_questions||stage.closest('[data-world-room]')?.dataset.totalQuestions||0));
    const copy=qs('[data-world-wait-copy]',wait);
    if(copy){
      copy.textContent=`You answered question ${answered} / ${total}. The next one opens only after both players finish the current question.`;
    }
    wait.hidden=false;
    initRadars(wait);
  }

  function initMatchIntro(room){
    const intro=qs('[data-world-intro]',room);
    if(!intro||intro.dataset.introRequired!=='1')return;
    intro.hidden=false;
    room.classList.add('is-intro-running');
    const counter=qs('[data-world-intro-count]',intro);
    const phase=qs('[data-world-intro-phase]',intro);
    const playerCards=qsa('.mw503-match-intro-grid article',intro);
    playerCards.forEach((card,index)=>{
      card.style.animation='none';
      void card.offsetWidth;
      card.style.animation=`mwPlayerReveal .62s ${(.12+index*.16).toFixed(2)}s cubic-bezier(.2,.8,.2,1) both`;
    });
    let remaining=Math.max(1,Number(intro.dataset.introSeconds||3));
    if(reducedMotion())remaining=Math.min(remaining,1);
    const paint=()=>{
      if(counter){
        counter.textContent=remaining>0?String(remaining):'GO';
        counter.style.animation='none';
        void counter.offsetWidth;
        counter.style.animation='mwCountdownPop .58s cubic-bezier(.18,.88,.22,1.2) both';
      }
      if(phase){
        if(remaining>=3)phase.textContent='Opponent found · preparing questions…';
        else if(remaining===2)phase.textContent='Syncing both players…';
        else if(remaining===1)phase.textContent='Get ready…';
        else phase.textContent='Go!';
      }
    };
    paint();
    const tick=()=>{
      remaining-=1;
      paint();
      if(remaining<0){
        intro.classList.add('is-leaving');
        window.setTimeout(()=>{
          intro.hidden=true;
          intro.classList.remove('is-leaving');
          room.classList.remove('is-intro-running');
          if(!qs('[data-world-question-card]',room)){
            const nextUrl=new URL(window.location.href);
            nextUrl.searchParams.set('intro','done');
            window.location.replace(nextUrl.toString());
          }
        },reducedMotion()?80:360);
        return;
      }
      window.setTimeout(tick,reducedMotion()?260:760);
    };
    window.setTimeout(tick,reducedMotion()?260:820);
  }

  const room=qs('[data-world-room]');
  if(room){
    initImageLightbox(room);
    initRadars(room);
    awaitingNextQuestion=!!qs('[data-world-between-questions]',room);
    const introNode=qs('[data-world-intro]',room);
    const introRequired=!!introNode&&introNode.dataset.introRequired==='1';
    const resultView=!!qs('.mw503-result-card',room);
    initMatchIntro(room);
    const statusUrl=room.dataset.statusUrl;
    const heartbeatUrl=room.dataset.heartbeatUrl;
    const sendHeartbeat=async()=>{
      if(!heartbeatUrl||resultView)return;
      const token=csrf();
      if(!token||token.length<32)return;
      const body=new FormData();
      body.append('csrfmiddlewaretoken',token);
      try{
        const data=await jsonFetch(heartbeatUrl,{method:'POST',body});
        // A completed result page is terminal. Never reload it from heartbeat;
        // otherwise the page can enter an endless GET -> heartbeat -> reload loop.
        if(data.status==='completed'&&!qs('.mw503-result-card',room)){
          clearAllPolling();
          location.reload();
        }
      }catch(_error){}
    };
    if(heartbeatUrl&&!resultView){sendHeartbeat();heartbeatTimer=setInterval(sendHeartbeat,10000);}

    // While MATCH FOUND is running, this browser deliberately owns its local
    // countdown. Do not let the room-status poll notice question_ready and
    // reload ?intro=1, which would restart the animation over and over on the
    // player who entered matchmaking first.
    if(!introRequired&&qs('.mw503-wait-room',room)&&!qs('.mw503-duel-stage',room)&&!resultView){
      statusPoll=setInterval(async()=>{
        try{
          const data=await jsonFetch(statusUrl);
          if(data.status==='active'){clearAllPolling();location.reload();}
          else if(data.status==='cancelled'){clearAllPolling();location.href='/world/';}
        }catch(_error){}
      },1200);
    }else if(!introRequired&&qs('.mw503-duel-stage',room)){
      const pollRoomStatus=async()=>{
        try{
          const data=await jsonFetch(statusUrl);
          const mine=qs('[data-world-my-score]');
          const theirs=qs('[data-world-opponent-score]');
          if(mine&&mine.textContent!==String(data.my_score)){
            mine.dataset.worldCountTo=String(data.my_score);animateCount(mine);
          }
          if(theirs&&theirs.textContent!==String(data.opponent_score)){
            theirs.dataset.worldCountTo=String(data.opponent_score);animateCount(theirs);
          }
          updateQuestionProgress(data);
          if(data.status==='completed'){
            clearAllPolling();
            location.reload();
            return;
          }
          const hasQuestionCard=!!qs('[data-world-question-card]',room);
          if(data.status==='active'&&data.question_ready&&(awaitingNextQuestion||!hasQuestionCard)){
            clearAllPolling();
            location.reload();
          }
        }catch(_error){}
      };
      pollRoomStatus();
      statusPoll=setInterval(pollRoomStatus,450);
    }
  }

  async function submitAnswer(form,{timeout=false}={}){
    if(answerSubmitting)return;
    answerSubmitting=true;
    awaitingNextQuestion=true;
    const button=form.querySelector('button[type=submit]');
    const buttonLabel=qs('[data-world-lock-label]',form);
    const card=form.closest('[data-world-question-card]');
    if(button){button.disabled=true;button.classList.add('is-busy');}
    if(buttonLabel)buttonLabel.textContent=timeout?'Time expired':'Locking…';
    if(card)card.classList.add('is-submitted');
    if(timeout)qsa('input[name=answer]',form).forEach(input=>{input.required=false;input.checked=false;});
    try{
      const action=form.getAttribute('action')||window.location.href;
      const data=await jsonFetch(action,{method:'POST',body:new FormData(form)});
      const mine=qs('[data-world-my-score]');
      if(mine&&Number.isFinite(Number(data.my_score))){
        mine.dataset.worldCountTo=String(data.my_score);animateCount(mine);
      }
      if(data.status==='completed'){
        location.href=data.redirect_url;
        return;
      }
      showBetweenQuestions(data);
      if(buttonLabel)buttonLabel.textContent='Locked';
      answerSubmitting=false;
    }catch(error){
      answerSubmitting=false;
      awaitingNextQuestion=false;
      if(button){button.disabled=false;button.classList.remove('is-busy');}
      if(buttonLabel)buttonLabel.textContent='Lock answer';
      if(card)card.classList.remove('is-submitted');
      if(timeout){location.reload();return;}
      window.alert(error.message);
    }
  }
  qs('[data-world-answer]')?.addEventListener('submit',event=>{event.preventDefault();submitAnswer(event.currentTarget);});

  const countdown=qs('[data-world-countdown]');
  if(countdown){
    let remaining=Math.max(0,Number(countdown.dataset.seconds||0));
    const output=countdown.querySelector('b');
    const paint=()=>{
      if(output)output.textContent=String(remaining);
      countdown.classList.toggle('is-low',remaining<=10);
    };
    paint();
    countdownTimer=setInterval(()=>{
      remaining=Math.max(0,remaining-1);
      paint();
      if(remaining<=0){
        clearInterval(countdownTimer);countdownTimer=null;
        const form=qs('[data-world-answer]');
        if(form)submitAnswer(form,{timeout:true});
      }
    },1000);
  }

  qs('[data-world-cancel-form]')?.addEventListener('submit',async event=>{
    event.preventDefault();
    try{
      const action=event.currentTarget.getAttribute('action')||window.location.href;
      await jsonFetch(action,{method:'POST',body:new FormData(event.currentTarget)});
      location.href='/world/';
    }catch(error){window.alert(error.message);}
  });

  qs('[data-world-rematch-request]')?.addEventListener('click',async event=>{
    const button=event.currentTarget;
    const form=button.closest('[data-world-rematch-form]');
    const cancelButton=form?qs('[data-world-rematch-cancel]',form):null;
    const status=qs('[data-world-rematch-result-status]');
    const label=qs('span',button);
    button.disabled=true;
    button.classList.add('is-pending');
    if(label)label.textContent='Requesting…';
    if(status)status.textContent='Sending rematch request…';
    try{
      const body=form?new FormData(form):new FormData();
      const data=await jsonFetch(button.dataset.rematchUrl,{method:'POST',body});
      if(data.activated&&data.room_url){location.replace(data.room_url);return;}
      if(status)status.textContent='Waiting for opponent…';
      if(label)label.textContent='Rematch requested';
      if(cancelButton){
        cancelButton.hidden=false;
        cancelButton.dataset.cancelUrl=data.cancel_url||'';
      }
      const waitForAccept=async()=>{
        try{
          const state=await jsonFetch(data.status_url);
          if(state.status==='active'){location.replace(state.room_url);return;}
          if(state.status==='cancelled'){
            button.disabled=false;
            button.classList.remove('is-pending');
            if(label)label.textContent='Rematch';
            if(cancelButton)cancelButton.hidden=true;
            if(status)status.textContent='Rematch declined or expired.';
            return;
          }
          rematchRequestPoll=window.setTimeout(waitForAccept,500);
        }catch(_error){rematchRequestPoll=window.setTimeout(waitForAccept,900);}
      };
      rematchRequestPoll=window.setTimeout(waitForAccept,300);
    }catch(error){
      button.disabled=false;
      button.classList.remove('is-pending');
      if(label)label.textContent='Rematch';
      if(status)status.textContent=error.message;
    }
  });

  qs('[data-world-rematch-cancel]')?.addEventListener('click',async event=>{
    const button=event.currentTarget;
    if(!button.dataset.cancelUrl)return;
    button.disabled=true;
    const status=qs('[data-world-rematch-result-status]');
    try{
      await jsonFetch(button.dataset.cancelUrl,{method:'POST',body:new FormData()});
      if(rematchRequestPoll)clearTimeout(rematchRequestPoll);
      rematchRequestPoll=null;
      button.hidden=true;
      button.disabled=false;
      const requestButton=qs('[data-world-rematch-request]');
      if(requestButton){requestButton.disabled=false;requestButton.classList.remove('is-pending');const label=qs('span',requestButton);if(label)label.textContent='Rematch';}
      if(status)status.textContent='Rematch request cancelled.';
    }catch(error){button.disabled=false;if(status)status.textContent=error.message;}
  });

  qs('[data-world-rematch-accept]')?.addEventListener('submit',async event=>{
    event.preventDefault();
    const form=event.currentTarget;
    const status=qs('[data-world-rematch-status]');
    const button=qs('button[type=submit]',form);
    if(button)button.disabled=true;
    try{
      const data=await jsonFetch(form.getAttribute('action'),{method:'POST',body:new FormData(form)});
      location.replace(data.room_url);
    }catch(error){if(button)button.disabled=false;if(status)status.textContent=error.message;}
  });

  qs('[data-world-rematch-decline]')?.addEventListener('submit',async event=>{
    event.preventDefault();
    const form=event.currentTarget;
    const status=qs('[data-world-rematch-status]');
    try{
      const data=await jsonFetch(form.getAttribute('action'),{method:'POST',body:new FormData(form)});
      location.replace(data.redirect_url||'/world/');
    }catch(error){if(status)status.textContent=error.message;}
  });

  function initIncomingRematches(){
    const shell=qs('[data-world-shell]');
    const popover=qs('[data-world-rematch-popover]');
    const url=shell?.dataset?.rematchIncomingUrl;
    if(!shell||!popover||!url)return;

    const hide=()=>{
      popover.hidden=true;
      popover.classList.remove('is-visible');
      activeIncomingInvite=null;
      if(rematchCountdownTimer){clearInterval(rematchCountdownTimer);rematchCountdownTimer=null;}
    };

    const act=async(kind)=>{
      const invite=activeIncomingInvite;
      if(!invite)return;
      const accept=qs('[data-world-rematch-popover-accept]',popover);
      const decline=qs('[data-world-rematch-popover-decline]',popover);
      if(accept)accept.disabled=true;
      if(decline)decline.disabled=true;
      try{
        const endpoint=kind==='accept'?invite.accept_url:invite.decline_url;
        const data=await jsonFetch(endpoint,{method:'POST',body:new FormData()});
        if(kind==='accept'&&data.room_url){location.replace(data.room_url);return;}
        hide();
      }catch(error){
        if(accept)accept.disabled=false;
        if(decline)decline.disabled=false;
        const foot=qs('.mw503-rematch-popover-foot',popover);
        if(foot)foot.innerHTML=`<span>${String(error.message||'Request failed.')}</span>`;
      }
    };

    qs('[data-world-rematch-popover-accept]',popover)?.addEventListener('click',()=>act('accept'));
    qs('[data-world-rematch-popover-decline]',popover)?.addEventListener('click',()=>act('decline'));
    qs('[data-world-rematch-popover-close]',popover)?.addEventListener('click',()=>act('decline'));

    const show=invite=>{
      activeIncomingInvite=invite;
      const set=(sel,value)=>{const el=qs(sel,popover);if(el)el.textContent=value;};
      set('[data-rematch-requester]',invite.requester);
      set('[data-rematch-requester-copy]',invite.requester);
      set('[data-rematch-initials]',invite.initials||'?');
      set('[data-rematch-rating]',String(invite.rating||1000));
      set('[data-rematch-tier]',String(invite.tier||'BRONZE').toUpperCase());
      set('[data-rematch-format]',`${invite.subject} · ${invite.mode}`);
      const profile=qs('[data-rematch-profile]',popover);if(profile)profile.href=invite.profile_url||'#';
      const accept=qs('[data-world-rematch-popover-accept]',popover);if(accept)accept.disabled=false;
      const decline=qs('[data-world-rematch-popover-decline]',popover);if(decline)decline.disabled=false;
      popover.hidden=false;
      requestAnimationFrame(()=>popover.classList.add('is-visible'));
      let remaining=Math.max(0,Number(invite.seconds_remaining||0));
      const render=()=>set('[data-rematch-seconds]',`${remaining}s`);
      render();
      if(rematchCountdownTimer)clearInterval(rematchCountdownTimer);
      rematchCountdownTimer=setInterval(()=>{remaining=Math.max(0,remaining-1);render();if(remaining<=0)hide();},1000);
    };

    let busy=false;
    const schedule=delay=>{
      if(rematchIncomingTimer)clearTimeout(rematchIncomingTimer);
      rematchIncomingTimer=setTimeout(poll,delay);
    };
    const poll=async()=>{
      if(busy){schedule(2500);return;}
      if(document.hidden){schedule(12000);return;}
      busy=true;
      try{
        const data=await jsonFetch(`${url}${url.includes('?')?'&':'?'}_=${Date.now()}`);
        if(data.invite){
          if(!activeIncomingInvite||activeIncomingInvite.id!==data.invite.id)show(data.invite);
        }else if(activeIncomingInvite){hide();}
      }catch(_error){}finally{
        busy=false;
        // Rematch discovery does not need sub-second polling. Keeping it adaptive
        // avoids competing with lobby/play synchronization on slower browsers/DBs.
        schedule(activeIncomingInvite?2500:5000);
      }
    };
    poll();
    document.addEventListener('visibilitychange',()=>{
      if(document.hidden){schedule(12000);return;}
      poll();
    });
  }

  initIncomingRematches();

  window.addEventListener('beforeunload',clearAllPolling,{once:true});
})();
