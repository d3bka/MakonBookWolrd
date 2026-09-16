(()=>{
  const root=document.querySelector('[data-memory-layers]');
  if(!root)return;
  const stage=root.querySelector('[data-study-stage]');
  const rate=root.querySelector('[data-rate]');
  const counter=root.querySelector('[data-memory-counter]');
  const meter=root.querySelector('[data-memory-progress]');
  const knownNode=root.querySelector('[data-memory-known]');
  const againNode=root.querySelector('[data-memory-again]');
  const toast=root.querySelector('[data-memory-toast]');
  const saveState=root.querySelector('[data-save-state]');
  const instruction=root.querySelector('[data-memory-instruction]');
  const items=[...root.querySelectorAll('[data-study-item]')].map(el=>({el,again:0,learning:0}));
  if(!stage||!items.length)return;

  const total=items.length;
  const queue=items.slice();
  const stats={again:0,learning:0,known:0};
  let current=null;
  let flipped=false;
  let transitioning=false;
  let completed=0;
  let toastTimer=null;

  const csrf=()=>{
    for(const name of ['makonbook_csrftoken_v35','csrftoken']){
      const part=document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith(name+'='));
      if(part)return decodeURIComponent(part.split('=').slice(1).join('='));
    }
    return '';
  };

  function showToast(message,tone='info',duration=900){
    if(!toast)return;
    clearTimeout(toastTimer);
    toast.textContent=message;
    toast.dataset.tone=tone;
    toast.classList.add('is-visible');
    toastTimer=setTimeout(()=>toast.classList.remove('is-visible'),duration);
  }

  function queueSave(wordId,outcome){
    if(saveState)saveState.textContent='Saving…';
    const payload=JSON.stringify({word_id:wordId,outcome});
    const run=(attempt=0)=>fetch(root.dataset.markUrl,{
      method:'POST',credentials:'same-origin',keepalive:true,
      headers:{'Content-Type':'application/json','X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest','Accept':'application/json'},
      body:payload
    }).then(response=>{
      if(!response.ok)throw new Error('save_failed');
      if(saveState)saveState.textContent='Saved';
      return true;
    }).catch(()=>{
      if(attempt<1)return new Promise(resolve=>setTimeout(resolve,180)).then(()=>run(attempt+1));
      if(saveState)saveState.textContent='Sync failed';
      showToast('Progress sync failed. Your session can continue.','error',1500);
      return false;
    });
    void run();
  }

  function updateHud(){
    if(knownNode)knownNode.textContent=stats.known;
    if(againNode)againNode.textContent=stats.again;
    const activeCount=queue.length+(current?1:0);
    if(counter)counter.textContent=current?`${Math.min(completed+1,total)} / ${total}`:`${total} / ${total}`;
    if(meter)meter.style.width=`${total?Math.min(100,(completed/total)*100):100}%`;
    if(instruction)instruction.innerHTML=flipped?'<i class="bi bi-check2-circle"></i> Rate the recall you had before flipping.':'<i class="bi bi-keyboard"></i> Space or click to reveal · then 1 / 2 / 3';
    rate?.querySelectorAll('button').forEach(button=>button.disabled=transitioning||!flipped);
    root.dataset.remaining=String(activeCount);
  }

  function showCurrent(){
    root.querySelectorAll('[data-study-item]').forEach(el=>el.hidden=!current||el!==current.el);
    flipped=false;
    transitioning=false;
    stage.classList.remove('is-flipped','is-leaving','is-entering');
    void stage.offsetWidth;
    stage.classList.add('is-entering');
    updateHud();
  }

  function next(){
    current=queue.shift()||null;
    if(!current){finish();return;}
    showCurrent();
  }

  function flip(){
    if(transitioning||!current)return;
    flipped=!flipped;
    stage.classList.toggle('is-flipped',flipped);
    updateHud();
  }

  function finish(){
    current=null;
    transitioning=true;
    if(meter)meter.style.width='100%';
    if(counter)counter.textContent=`${total} / ${total}`;
    stage.classList.remove('is-flipped','is-leaving','is-entering');
    stage.classList.add('is-complete');
    stage.innerHTML=`<div class="va509-center va509-result"><span class="va509-icon-orb"><i class="bi bi-check-lg"></i></span><span class="va509-kicker">Session complete</span><h2>${stats.known} strong recalls</h2><p>${completed} cards completed · ${stats.learning} still learning · ${stats.again} marked again.</p></div>`;
    if(rate)rate.innerHTML=`<a class="va509-btn" href="${root.dataset.deckUrl}">Back to deck</a><a class="va509-btn primary va509-memory-primary" href="${root.dataset.studyAllUrl}">Review all <i class="bi bi-arrow-repeat"></i></a>`;
    if(instruction)instruction.innerHTML='<i class="bi bi-check-circle"></i> Your progress is saved in the background.';
    if(saveState)saveState.textContent='Saved';
    if(knownNode)knownNode.textContent=stats.known;
    if(againNode)againNode.textContent=stats.again;
  }

  function mark(outcome){
    if(transitioning||!flipped||!current)return;
    transitioning=true;
    stats[outcome]=(stats[outcome]||0)+1;
    const item=current;
    let requeued=false;
    if(outcome==='again'&&item.again<2){
      item.again+=1;
      queue.splice(Math.min(2,queue.length),0,item);
      requeued=true;
    }else if(outcome==='learning'&&item.learning<1){
      item.learning+=1;
      queue.push(item);
      requeued=true;
    }
    if(!requeued)completed+=1;
    queueSave(item.el.dataset.wordId,outcome);
    updateHud();
    const message=outcome==='known'?'+1 strong recall':outcome==='learning'?'One more pass later':'Coming back soon';
    showToast(message,outcome==='known'?'success':outcome==='again'?'error':'info',850);
    stage.classList.add('is-leaving');
    setTimeout(next,430);
  }

  stage.addEventListener('click',flip);
  stage.addEventListener('keydown',event=>{
    if(event.key==='Enter'||event.code==='Space'){event.preventDefault();flip();}
  });
  rate?.querySelectorAll('[data-outcome]').forEach(button=>button.addEventListener('click',event=>{
    event.stopPropagation();
    mark(button.dataset.outcome);
  }));
  document.addEventListener('keydown',event=>{
    if(event.repeat||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName))return;
    if(event.code==='Space'){event.preventDefault();flip();return;}
    if(!flipped)return;
    if(event.key==='1')mark('again');
    if(event.key==='2')mark('learning');
    if(event.key==='3')mark('known');
  });

  next();
})();
