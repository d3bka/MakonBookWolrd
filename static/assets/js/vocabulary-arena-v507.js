(()=>{
  const root=document.querySelector('[data-vocab-arena]');
  if(!root)return;
  const dataNode=document.getElementById('vocab-arena-data');
  const words=JSON.parse(dataNode?.textContent||'[]');
  const card=root.querySelector('[data-arena-card]');
  const footer=root.querySelector('[data-arena-footer]');
  const counter=root.querySelector('[data-arena-counter]');
  const meter=root.querySelector('[data-arena-progress]');
  const mode=root.dataset.mode;
  const maxLives=Math.max(1,Number(root.dataset.lives)||3);
  let index=0,score=0,locked=false,lives=maxLives,streak=0;

  const csrf=()=>{
    for(const name of ['makonbook_csrftoken_v35','csrftoken']){
      const part=document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith(name+'='));
      if(part)return decodeURIComponent(part.split('=').slice(1).join('='));
    }
    return '';
  };
  const escapeHtml=(value)=>String(value??'').replace(/[&<>"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
  const normalize=(value)=>String(value??'').toLocaleLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]/g,'');

  async function save(wordId,outcome){
    try{
      const response=await fetch(root.dataset.markUrl,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest','Accept':'application/json'},body:JSON.stringify({word_id:wordId,outcome})});
      return response.ok;
    }catch(_){return false;}
  }
  function progress(){
    if(counter)counter.textContent=`${Math.min(index+1,words.length)} / ${words.length}`;
    if(meter)meter.style.width=`${words.length?index/words.length*100:100}%`;
  }
  function pulse(type='success'){
    root.classList.remove('is-success','is-error');
    void root.offsetWidth;
    root.classList.add(type==='error'?'is-error':'is-success');
    window.setTimeout(()=>root.classList.remove('is-success','is-error'),360);
  }
  function vibrate(pattern){
    try{if('vibrate' in navigator)navigator.vibrate(pattern);}catch(_){}
  }
  function done(){
    if(meter)meter.style.width='100%';
    if(counter)counter.textContent=`${words.length} / ${words.length}`;
    card.innerHTML=`<div class="va507-center va507-result"><span class="va507-icon-orb"><i class="bi bi-check-lg"></i></span><span class="va507-kicker">Session complete</span><h2>${score} strong recalls</h2><p>${words.length} cards practiced. Your saved deck progress has been updated.</p></div>`;
    footer.innerHTML=`<a class="va507-btn" href="${root.dataset.deckUrl}">Back to deck</a><button class="va507-btn primary" type="button" data-restart>Practice again <i class="bi bi-arrow-repeat"></i></button>`;
    footer.querySelector('[data-restart]')?.addEventListener('click',()=>{index=0;score=0;lives=maxLives;streak=0;locked=false;render();});
  }
  function next(){
    index+=1;locked=false;
    if(index>=words.length){done();return;}
    render();
  }
  function choicesFor(current){
    const others=words.filter(w=>w.id!==current.id).sort(()=>Math.random()-.5).slice(0,3);
    return [current,...others].sort(()=>Math.random()-.5);
  }
  function shuffle(chars){
    const arr=[...chars];
    for(let i=arr.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[arr[i],arr[j]]=[arr[j],arr[i]];}
    return arr;
  }
  function renderArenaHud(label,extra=''){
    return `<div class="va507-card-head"><span class="va507-kicker">${label}</span>${extra}</div>`;
  }

  function renderAnimated(w){
    card.innerHTML=`${renderArenaHud('Animated Immersion','<span class="va507-pill">Guided recall</span>')}<div class="va507-center va507-immersion"><div class="va507-word va507-reveal">${escapeHtml(w.word)}</div><div class="va507-divider va507-reveal"></div><div class="va507-meaning va507-reveal">${escapeHtml(w.meaning)}</div>${w.example?`<div class="va507-example va507-reveal"><span>Example</span>${escapeHtml(w.example)}</div>`:''}</div>`;
    footer.innerHTML=`<button class="va507-btn danger" type="button" data-again><i class="bi bi-arrow-counterclockwise"></i> Again</button><button class="va507-btn primary" type="button" data-got>Got it <i class="bi bi-arrow-right"></i></button>`;
    footer.querySelector('[data-again]').onclick=async()=>{pulse('error');await save(w.id,'again');next();};
    footer.querySelector('[data-got]').onclick=async()=>{score++;pulse('success');await save(w.id,'known');next();};
  }

  function renderBounce(w){
    const target=normalize(w.word);
    if(!target){save(w.id,'again').finally(next);return;}
    const bank=shuffle(target);
    let accepted='';
    let hintUsed=false;

    const hearts=()=>Array.from({length:maxLives},(_,i)=>`<span class="va507-heart ${i<lives?'alive':'lost'}"><i class="bi bi-heart${i<lives?'-fill':''}"></i></span>`).join('');
    const slots=()=>[...target].map((_,i)=>`<span class="va507-slot ${i<accepted.length?'filled':''}">${i<accepted.length?escapeHtml(accepted[i]):''}</span>`).join('');
    const tiles=()=>bank.map((letter,i)=>`<span class="va507-letter" data-bank-index="${i}" data-letter="${escapeHtml(letter)}" style="--r:${(i%2?1:-1)*(1+(i%3))}deg">${escapeHtml(letter)}</span>`).join('');

    card.innerHTML=`${renderArenaHud('Word Bounce',`<div class="va507-bounce-hud"><span><b data-bounce-score>${score}</b><small>score</small></span><span><b data-bounce-streak>${streak}</b><small>streak</small></span><div class="va507-lives" data-bounce-lives>${hearts()}</div></div>`)}<div class="va507-center va507-bounce"><div class="va507-prompt-label">Build the word from the meaning</div><div class="va507-muted va507-bounce-meaning">${escapeHtml(w.meaning)}</div><div class="va507-slots" data-bounce-slots>${slots()}</div><div class="va507-letters" data-bounce-bank>${tiles()}</div><label class="va507-typebox"><span>Type one letter at a time</span><input class="va507-input" inputmode="text" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="1" aria-label="Type the next letter"></label><div class="va507-feedback" data-bounce-feedback>Every letter is checked instantly.</div></div>`;
    footer.innerHTML=`<button class="va507-btn" type="button" data-hint-btn><i class="bi bi-lightbulb"></i> Hint</button><button class="va507-btn" type="button" data-skip><i class="bi bi-skip-forward"></i> Skip</button>`;

    const input=card.querySelector('.va507-input');
    const slotsNode=card.querySelector('[data-bounce-slots]');
    const bankNode=card.querySelector('[data-bounce-bank]');
    const livesNode=card.querySelector('[data-bounce-lives]');
    const feedback=card.querySelector('[data-bounce-feedback]');
    const scoreNode=card.querySelector('[data-bounce-score]');
    const streakNode=card.querySelector('[data-bounce-streak]');

    function paint(){
      if(slotsNode)slotsNode.innerHTML=slots();
      if(livesNode)livesNode.innerHTML=hearts();
      if(scoreNode)scoreNode.textContent=score;
      if(streakNode)streakNode.textContent=streak;
    }
    function consume(letter){
      const candidate=[...bankNode.querySelectorAll('.va507-letter:not(.is-used)')].find(node=>node.dataset.letter===letter);
      if(candidate){candidate.classList.add('is-used');}
    }
    async function complete(){
      locked=true;
      score+=hintUsed?0:1;
      streak=hintUsed?0:streak+1;
      paint();
      feedback.textContent=hintUsed?'Completed with a hint. Keep it in learning.':'Perfect build. Word locked in.';
      feedback.dataset.tone='success';
      pulse('success');
      await save(w.id,hintUsed?'learning':'known');
      window.setTimeout(next,650);
    }
    async function gameOver(){
      locked=true;
      streak=0;
      vibrate([120,60,120]);
      await save(w.id,'again');
      card.innerHTML=`<div class="va507-center va507-result va507-gameover"><span class="va507-icon-orb danger"><i class="bi bi-heartbreak"></i></span><span class="va507-kicker">Out of lives</span><h2>${escapeHtml(w.word)}</h2><p>${escapeHtml(w.meaning)}</p><small>You reached ${score} correct words before the run ended.</small></div>`;
      footer.innerHTML=`<a class="va507-btn" href="${root.dataset.deckUrl}">Back to deck</a><button class="va507-btn primary" type="button" data-retry>Retry run <i class="bi bi-arrow-repeat"></i></button>`;
      footer.querySelector('[data-retry]').onclick=()=>{index=0;score=0;streak=0;lives=maxLives;locked=false;render();};
    }
    function wrong(char){
      lives=Math.max(0,lives-1);streak=0;paint();
      feedback.textContent=`“${char.toUpperCase()}” is not the next letter. ${lives?`${lives} ${lives===1?'life':'lives'} left.`:'No lives left.'}`;
      feedback.dataset.tone='error';
      card.classList.remove('is-shaking');void card.offsetWidth;card.classList.add('is-shaking');
      window.setTimeout(()=>card.classList.remove('is-shaking'),360);
      pulse('error');vibrate([65,35,65]);
      if(lives===0){locked=true;window.setTimeout(gameOver,320);}
    }
    function accept(char,fromHint=false){
      accepted+=char;consume(char);paint();
      feedback.textContent=fromHint?'Hint placed the next letter.':'Nice. Keep going.';
      feedback.dataset.tone=fromHint?'hint':'success';
      pulse('success');
      if(accepted.length===target.length)complete();
    }
    function processChar(raw){
      if(locked)return;
      const char=normalize(raw).slice(-1);
      input.value='';
      if(!char)return;
      const expected=target[accepted.length];
      if(char===expected)accept(char,false);else wrong(char);
    }
    input.addEventListener('input',()=>processChar(input.value));
    input.addEventListener('keydown',event=>{
      if(event.key==='Enter'){event.preventDefault();return;}
    });
    footer.querySelector('[data-hint-btn]').onclick=()=>{
      if(locked||hintUsed)return;
      hintUsed=true;
      const expected=target[accepted.length];
      if(expected)accept(expected,true);
      footer.querySelector('[data-hint-btn]').disabled=true;
    };
    footer.querySelector('[data-skip]').onclick=async()=>{if(locked)return;locked=true;streak=0;await save(w.id,'again');next();};
    window.setTimeout(()=>input.focus(),0);
  }

  function renderMeaning(w){
    const opts=choicesFor(w);
    card.innerHTML=`${renderArenaHud('Meaning Match','<span class="va507-pill">Precision round</span>')}<div class="va507-center va507-match-head"><div class="va507-word">${escapeHtml(w.word)}</div><div class="va507-muted">Choose the definition that matches this word.</div></div><div class="va507-options">${opts.map(o=>`<button class="va507-option" type="button" data-option data-id="${o.id}"><span>${escapeHtml(o.meaning)}</span><i class="bi bi-arrow-up-right"></i></button>`).join('')}</div><div class="va507-score"><span><b>${score}</b> score</span><span>${words.length-index} remaining</span></div>`;
    footer.innerHTML='<span class="va507-footer-note"><i class="bi bi-bullseye"></i> Accuracy first. One precise choice per word.</span>';
    card.querySelectorAll('[data-option]').forEach(btn=>btn.onclick=async()=>{
      if(locked)return;locked=true;
      const ok=Number(btn.dataset.id)===w.id;
      btn.classList.add(ok?'correct':'wrong');
      if(ok){score++;pulse('success');await save(w.id,'known');window.setTimeout(next,520);}
      else{pulse('error');vibrate(60);await save(w.id,'again');card.querySelector(`[data-option][data-id="${w.id}"]`)?.classList.add('correct');window.setTimeout(next,900);}
    });
  }

  function render(){
    if(!words.length){card.innerHTML='<div class="va507-center va507-result"><h2>No words in this deck.</h2></div>';footer.innerHTML=`<a class="va507-btn primary" href="${root.dataset.deckUrl}">Back to deck</a>`;return;}
    progress();
    const w=words[index];
    if(mode==='animated-immersion')renderAnimated(w);
    else if(mode==='word-bounce')renderBounce(w);
    else renderMeaning(w);
  }
  render();
})();
