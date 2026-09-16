(()=>{
  const root=document.querySelector('[data-vocab-arena]');
  if(!root)return;

  const dataNode=document.getElementById('vocab-arena-data');
  const words=JSON.parse(dataNode?.textContent||'[]');
  const card=root.querySelector('[data-arena-card]');
  const footer=root.querySelector('[data-arena-footer]');
  const counter=root.querySelector('[data-arena-counter]');
  const meter=root.querySelector('[data-arena-progress]');
  const toast=root.querySelector('[data-arena-toast]');
  const scoreNode=root.querySelector('[data-arena-score]');
  const streakNode=root.querySelector('[data-arena-streak]');
  const livesWrap=root.querySelector('[data-arena-lives-wrap]');
  const livesNode=root.querySelector('[data-arena-lives]');
  const mode=root.dataset.mode;
  const maxLives=Math.max(1,Number(root.dataset.lives)||3);
  const timing={animated:520,bounceCorrect:560,bounceReveal:1350,bounceSkip:760,meaningCorrect:680,meaningReveal:1450};

  let index=0;
  let score=0;
  let streak=0;
  let lives=maxLives;
  let locked=false;
  let toastTimer=null;
  let activeKeyHandler=null;

  const csrf=()=>{
    for(const name of ['makonbook_csrftoken_v35','csrftoken']){
      const part=document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith(name+'='));
      if(part)return decodeURIComponent(part.split('=').slice(1).join('='));
    }
    return '';
  };
  const escapeHtml=(value)=>String(value??'').replace(/[&<>\"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[ch]));
  const normalize=(value)=>String(value??'').toLocaleLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]/g,'');

  function showToast(message,tone='info',duration=900){
    if(!toast)return;
    window.clearTimeout(toastTimer);
    toast.textContent=message;
    toast.dataset.tone=tone;
    toast.classList.add('is-visible');
    toastTimer=window.setTimeout(()=>toast.classList.remove('is-visible'),duration);
  }

  function queueSave(wordId,outcome){
    const payload=JSON.stringify({word_id:wordId,outcome});
    const run=(attempt=0)=>fetch(root.dataset.markUrl,{
      method:'POST',
      credentials:'same-origin',
      keepalive:true,
      headers:{
        'Content-Type':'application/json',
        'X-CSRFToken':csrf(),
        'X-Requested-With':'XMLHttpRequest',
        'Accept':'application/json'
      },
      body:payload
    }).then(response=>{
      if(!response.ok)throw new Error('save_failed');
      return true;
    }).catch(()=>{
      if(attempt<1)return new Promise(resolve=>window.setTimeout(resolve,180)).then(()=>run(attempt+1));
      showToast('Progress sync failed. Your game can continue.','error',1500);
      return false;
    });
    void run();
  }

  function heartsMarkup(){
    return Array.from({length:maxLives},(_,i)=>`<i class="bi bi-heart${i<lives?'-fill':''} ${i<lives?'alive':'lost'}" aria-hidden="true"></i>`).join('');
  }

  function syncHud(){
    if(scoreNode)scoreNode.textContent=score;
    if(streakNode)streakNode.textContent=streak;
    const bounce=mode==='word-bounce';
    if(livesWrap)livesWrap.hidden=!bounce;
    if(livesNode&&bounce)livesNode.innerHTML=heartsMarkup();
  }

  function progress(){
    if(counter)counter.textContent=`${Math.min(index+1,words.length)} / ${words.length}`;
    if(meter)meter.style.width=`${words.length?(index/words.length)*100:100}%`;
    syncHud();
  }

  function pulse(type='success'){
    root.classList.remove('is-success','is-error');
    void root.offsetWidth;
    root.classList.add(type==='error'?'is-error':'is-success');
    window.setTimeout(()=>root.classList.remove('is-success','is-error'),260);
  }

  function vibrate(pattern){
    try{if('vibrate' in navigator)navigator.vibrate(pattern);}catch(_){/* no-op */}
  }

  function animateCardOut(callback){
    card.classList.add('is-leaving');
    window.setTimeout(()=>{
      card.classList.remove('is-leaving');
      callback();
    },110);
  }

  function advance(delay=180){
    locked=true;
    window.setTimeout(()=>animateCardOut(next),delay);
  }

  function done(){
    activeKeyHandler=null;
    if(meter)meter.style.width='100%';
    if(counter)counter.textContent=`${words.length} / ${words.length}`;
    syncHud();
    card.innerHTML=`<div class="va509-center va509-result"><span class="va509-icon-orb"><i class="bi bi-check-lg"></i></span><span class="va509-kicker">Session complete</span><h2>${score} strong recalls</h2><p>${words.length} cards practiced. Progress is syncing in the background.</p></div>`;
    footer.innerHTML=`<a class="va509-btn" href="${root.dataset.deckUrl}">Back to deck</a><button class="va509-btn primary" type="button" data-restart>Practice again <i class="bi bi-arrow-repeat"></i></button>`;
    footer.querySelector('[data-restart]')?.addEventListener('click',()=>{
      index=0;score=0;streak=0;lives=maxLives;locked=false;render();
    });
  }

  function next(){
    index+=1;
    locked=false;
    if(index>=words.length){done();return;}
    render();
  }

  function choicesFor(current){
    const others=words.filter(w=>w.id!==current.id).sort(()=>Math.random()-.5).slice(0,3);
    return [current,...others].sort(()=>Math.random()-.5);
  }

  function shuffle(chars){
    const arr=[...chars];
    for(let i=arr.length-1;i>0;i--){
      const j=Math.floor(Math.random()*(i+1));
      [arr[i],arr[j]]=[arr[j],arr[i]];
    }
    return arr;
  }

  function renderArenaHud(label,extra=''){
    return `<div class="va509-card-head"><span class="va509-kicker">${label}</span>${extra}</div>`;
  }

  function renderAnimated(w){
    activeKeyHandler=null;
    card.innerHTML=`${renderArenaHud('Animated Immersion','<span class="va509-pill">Guided recall</span>')}<div class="va509-center va509-immersion"><div class="va509-word va509-reveal">${escapeHtml(w.word)}</div><div class="va509-divider va509-reveal"></div><div class="va509-meaning va509-reveal">${escapeHtml(w.meaning)}</div>${w.example?`<div class="va509-example va509-reveal"><span>Example</span>${escapeHtml(w.example)}</div>`:''}</div>`;
    footer.innerHTML=`<button class="va509-btn danger" type="button" data-again><i class="bi bi-arrow-counterclockwise"></i> Again</button><button class="va509-btn primary" type="button" data-got>Got it <i class="bi bi-arrow-right"></i></button>`;

    footer.querySelector('[data-again]').onclick=()=>{
      if(locked)return;
      streak=0;syncHud();pulse('error');showToast('Marked for another review.','error',650);
      queueSave(w.id,'again');advance(timing.animated);
    };
    footer.querySelector('[data-got]').onclick=()=>{
      if(locked)return;
      score+=1;streak+=1;syncHud();pulse('success');showToast(`+1 score · ${streak} streak`,'success',650);
      queueSave(w.id,'known');advance(timing.animated);
    };
  }

  function renderBounce(w){
    const target=normalize(w.word);
    if(!target){queueSave(w.id,'again');advance(0);return;}

    lives=maxLives;
    syncHud();

    const bank=shuffle(target).map((letter,index)=>({id:`${index}-${letter}`,letter,used:false}));
    let accepted='';
    let hintUsed=false;

    const slots=()=>[...target].map((_,i)=>`<span class="va509-slot ${i<accepted.length?'filled':''}">${i<accepted.length?escapeHtml(accepted[i]):''}</span>`).join('');
    const tiles=()=>bank.map((item,i)=>`<button class="va509-letter ${item.used?'is-used':''}" type="button" data-letter-id="${item.id}" data-letter="${escapeHtml(item.letter)}" style="--r:${(i%2?1:-1)*(1+(i%3))}deg" ${item.used?'disabled':''}>${escapeHtml(item.letter)}</button>`).join('');

    card.innerHTML=`${renderArenaHud('Word Bounce','<span class="va509-pill">3 lives per word</span>')}<div class="va509-center va509-bounce"><div class="va509-prompt-label">Build the word from the meaning</div><div class="va509-muted va509-bounce-meaning">${escapeHtml(w.meaning)}</div><div class="va509-slots" data-bounce-slots>${slots()}</div><div class="va509-letters" data-bounce-bank>${tiles()}</div><label class="va509-typebox"><span>Type a letter or tap a tile</span><input class="va509-input" inputmode="text" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="1" aria-label="Type the next letter"></label><div class="va509-feedback" data-bounce-feedback>Every letter is checked instantly.</div></div>`;
    footer.innerHTML=`<button class="va509-btn" type="button" data-hint-btn><i class="bi bi-lightbulb"></i> Hint</button><button class="va509-btn" type="button" data-skip><i class="bi bi-skip-forward"></i> Skip</button>`;

    const input=card.querySelector('.va509-input');
    const slotsNode=card.querySelector('[data-bounce-slots]');
    const bankNode=card.querySelector('[data-bounce-bank]');
    const feedback=card.querySelector('[data-bounce-feedback]');

    function paintSlots(){
      if(slotsNode)slotsNode.innerHTML=slots();
      syncHud();
    }

    function findAvailable(letter){
      return bank.find(item=>!item.used&&item.letter===letter);
    }

    function animateTile(itemId,state='accept'){
      const tile=bankNode?.querySelector(`[data-letter-id="${CSS.escape(itemId)}"]`);
      if(!tile)return;
      tile.classList.remove('is-hit','is-wrong');
      void tile.offsetWidth;
      tile.classList.add(state==='wrong'?'is-wrong':'is-hit');
      if(state==='accept'){
        tile.disabled=true;
        window.setTimeout(()=>{
          tile.classList.add('is-used');
          tile.disabled=true;
        },90);
      }else{
        window.setTimeout(()=>tile.classList.remove('is-wrong'),260);
      }
    }

    function revealCorrectAndMove(){
      accepted=target;
      paintSlots();
      bank.forEach(item=>{item.used=true;});
      bankNode?.querySelectorAll('.va509-letter').forEach(tile=>{
        tile.classList.add('is-used');tile.disabled=true;
      });
      feedback.textContent=`Correct word: ${w.word}`;
      feedback.dataset.tone='answer';
      showToast(`Answer: ${w.word}`,'answer',700);
      queueSave(w.id,'again');
      advance(timing.bounceReveal);
    }

    function wrong(char,sourceTileId=null){
      if(locked)return;
      lives=Math.max(0,lives-1);
      streak=0;
      syncHud();
      if(sourceTileId)animateTile(sourceTileId,'wrong');
      feedback.textContent=`“${char.toUpperCase()}” is not next. ${lives?`${lives} ${lives===1?'life':'lives'} left.`:'Showing the answer…'}`;
      feedback.dataset.tone='error';
      card.classList.remove('is-shaking');
      void card.offsetWidth;
      card.classList.add('is-shaking');
      window.setTimeout(()=>card.classList.remove('is-shaking'),300);
      pulse('error');
      vibrate(lives?[55]:[90,45,90]);
      showToast(lives?`−1 life · ${lives} left`:'Out of lives','error',650);
      if(lives===0){locked=true;window.setTimeout(revealCorrectAndMove,240);}
    }

    function complete(){
      locked=true;
      if(!hintUsed){score+=1;streak+=1;}else{streak=0;}
      syncHud();
      feedback.textContent=hintUsed?'Completed with a hint. Kept in learning.':'Perfect build.';
      feedback.dataset.tone='success';
      pulse('success');
      showToast(hintUsed?'Completed with help':`+1 score · ${streak} streak`,'success',650);
      queueSave(w.id,hintUsed?'learning':'known');
      advance(timing.bounceCorrect);
    }

    function accept(char,fromHint=false,sourceTileId=null){
      if(locked)return;
      const item=sourceTileId?bank.find(entry=>entry.id===sourceTileId&&!entry.used):findAvailable(char);
      if(item){item.used=true;animateTile(item.id,'accept');}
      accepted+=char;
      paintSlots();
      feedback.textContent=fromHint?'Hint placed the next letter.':'Nice. Keep going.';
      feedback.dataset.tone=fromHint?'hint':'success';
      pulse('success');
      if(accepted.length===target.length){locked=true;window.setTimeout(complete,90);}
    }

    function processChar(raw,sourceTileId=null){
      if(locked)return;
      const char=normalize(raw).slice(-1);
      if(input)input.value='';
      if(!char)return;
      const expected=target[accepted.length];
      if(char===expected)accept(char,false,sourceTileId);
      else wrong(char,sourceTileId);
    }

    bankNode?.querySelectorAll('[data-letter]').forEach(tile=>{
      tile.addEventListener('click',()=>processChar(tile.dataset.letter,tile.dataset.letterId));
    });

    input?.addEventListener('input',()=>processChar(input.value));
    input?.addEventListener('keydown',event=>{
      if(event.key==='Enter')event.preventDefault();
    });

    activeKeyHandler=(event)=>{
      if(locked||event.ctrlKey||event.metaKey||event.altKey)return;
      if(document.activeElement===input)return;
      if(/^[a-zA-Z0-9]$/.test(event.key)){
        event.preventDefault();
        processChar(event.key);
      }
    };

    footer.querySelector('[data-hint-btn]').onclick=()=>{
      if(locked||hintUsed)return;
      hintUsed=true;
      const expected=target[accepted.length];
      if(expected)accept(expected,true);
      footer.querySelector('[data-hint-btn]').disabled=true;
      showToast('Hint used · no strong-recall point','info',850);
    };

    footer.querySelector('[data-skip]').onclick=()=>{
      if(locked)return;
      locked=true;
      streak=0;syncHud();
      queueSave(w.id,'again');
      showToast(`Skipped · ${w.word}`,'answer',650);
      advance(timing.bounceSkip);
    };

    window.setTimeout(()=>input?.focus({preventScroll:true}),0);
  }

  function renderMeaning(w){
    activeKeyHandler=null;
    const opts=choicesFor(w);
    let assisted=false;
    let misses=0;

    card.innerHTML=`${renderArenaHud('Meaning Match','<span class="va509-pill">Up to 2 misses</span>')}<div class="va509-center va509-match-head"><div class="va509-word">${escapeHtml(w.word)}</div><div class="va509-muted">Choose the definition that matches this word.</div></div><div class="va509-options">${opts.map(o=>`<button class="va509-option" type="button" data-option data-id="${o.id}"><span>${escapeHtml(o.meaning)}</span><i class="bi bi-arrow-up-right"></i></button>`).join('')}</div><div class="va509-match-feedback" data-match-feedback>Two mistakes are allowed. Or use 50/50 before your first choice.</div>`;
    footer.innerHTML=`<button class="va509-btn helper" type="button" data-fifty><i class="bi bi-circle-half"></i> 50 / 50</button><span class="va509-footer-note"><i class="bi bi-shield-check"></i> Correct answer appears after the second miss.</span>`;

    const feedback=card.querySelector('[data-match-feedback]');
    const fifty=footer.querySelector('[data-fifty]');

    function remainingWrongChoices(){
      return [...card.querySelectorAll('[data-option]')].filter(btn=>!btn.disabled&&Number(btn.dataset.id)!==w.id);
    }

    function revealAnswer(){
      locked=true;
      const correct=card.querySelector(`[data-option][data-id="${w.id}"]`);
      card.querySelectorAll('[data-option]').forEach(option=>option.disabled=true);
      correct?.classList.remove('is-eliminated');
      if(correct)correct.classList.add('correct');
      streak=0;syncHud();pulse('error');vibrate([55,30,55]);queueSave(w.id,'again');
      feedback.textContent=`Correct answer: ${w.meaning}`;
      feedback.dataset.tone='answer';
      showToast('Correct answer shown','answer',1100);
      advance(timing.meaningReveal);
    }

    fifty.onclick=()=>{
      if(locked||assisted||misses>0)return;
      assisted=true;
      const wrongButtons=[...card.querySelectorAll('[data-option]')].filter(btn=>Number(btn.dataset.id)!==w.id);
      shuffle(wrongButtons).slice(0,2).forEach(btn=>{
        btn.disabled=true;
        btn.classList.add('is-eliminated');
      });
      fifty.disabled=true;
      fifty.innerHTML='<i class="bi bi-check2"></i> 50 / 50 used';
      feedback.textContent='Two incorrect choices removed. One miss now reveals the answer.';
      feedback.dataset.tone='hint';
      showToast('50/50 used · 2 choices left','info',1000);
    };

    card.querySelectorAll('[data-option]').forEach(btn=>btn.onclick=()=>{
      if(locked||btn.disabled)return;
      const ok=Number(btn.dataset.id)===w.id;

      if(ok){
        locked=true;
        card.querySelectorAll('[data-option]').forEach(option=>option.disabled=true);
        btn.classList.add('correct');
        const supported=assisted||misses>0;
        if(supported){
          streak=0;
          queueSave(w.id,'learning');
          feedback.textContent=assisted?'Correct with 50/50 assistance.':'Correct on the second try.';
        }else{
          score+=1;streak+=1;
          queueSave(w.id,'known');
          feedback.textContent='Correct on the first try.';
        }
        feedback.dataset.tone='success';syncHud();pulse('success');
        showToast(supported?'Correct · kept in learning':`+1 score · ${streak} streak`,'success',950);
        advance(timing.meaningCorrect);
        return;
      }

      misses+=1;
      btn.classList.add('wrong');
      btn.disabled=true;
      streak=0;syncHud();pulse('error');vibrate(45);
      if(fifty)fifty.disabled=true;

      const noWrongChoicesLeft=remainingWrongChoices().length===0;
      if(misses>=2||noWrongChoicesLeft){
        feedback.textContent='Second miss. Showing the correct answer…';
        feedback.dataset.tone='answer';
        showToast('Answer reveal','answer',800);
        window.setTimeout(revealAnswer,260);
        return;
      }

      feedback.textContent='Not quite. One more mistake is allowed.';
      feedback.dataset.tone='hint';
      showToast('1 miss · 1 chance left','error',900);
    });
  }

  function render(){
    if(!words.length){
      activeKeyHandler=null;
      card.innerHTML='<div class="va509-center va509-result"><h2>No words in this deck.</h2></div>';
      footer.innerHTML=`<a class="va509-btn primary" href="${root.dataset.deckUrl}">Back to deck</a>`;
      return;
    }
    progress();
    card.classList.remove('is-entering');
    void card.offsetWidth;
    card.classList.add('is-entering');
    const w=words[index];
    if(mode==='animated-immersion')renderAnimated(w);
    else if(mode==='word-bounce')renderBounce(w);
    else renderMeaning(w);
  }

  document.addEventListener('keydown',event=>{
    if(activeKeyHandler)activeKeyHandler(event);
  });

  render();
})();
