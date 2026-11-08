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
  const items=[...root.querySelectorAll('[data-study-item]')].map(el=>({
    el,
    again:0,
    learning:0,
    timesSeen:Number(el.dataset.timesSeen||0)
  }));
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

  function setSaveState(label,tone='saved'){
    if(!saveState)return;
    saveState.textContent=label;
    saveState.dataset.tone=tone;
  }

  function showToast(message,tone='info',duration=900){
    if(!toast)return;
    clearTimeout(toastTimer);
    toast.textContent=message;
    toast.dataset.tone=tone;
    toast.classList.add('is-visible');
    toastTimer=setTimeout(()=>toast.classList.remove('is-visible'),duration);
  }

  async function postReview(item,outcome){
    const token=csrf();
    if(!token)throw new Error('Secure session token is missing. Reload the page.');

    const payload=JSON.stringify({
      word_id:item.el.dataset.wordId,
      outcome,
      expected_times_seen:item.timesSeen
    });

    const response=await fetch(root.dataset.markUrl,{
      method:'POST',
      credentials:'same-origin',
      keepalive:true,
      headers:{
        'Content-Type':'application/json',
        'X-CSRFToken':token,
        'X-Requested-With':'XMLHttpRequest',
        'Accept':'application/json'
      },
      body:payload
    });

    let data={};
    try{data=await response.json();}catch(_error){data={};}
    if(!response.ok||!data.ok){
      const error=new Error(data.error||'Could not save progress.');
      error.status=response.status;
      error.data=data;
      throw error;
    }
    return data;
  }

  async function saveReview(item,outcome){
    setSaveState('Saving…','saving');
    for(let attempt=0;attempt<2;attempt+=1){
      try{
        const data=await postReview(item,outcome);
        item.timesSeen=Number(data.times_seen||item.timesSeen);
        item.el.dataset.timesSeen=String(item.timesSeen);
        if(data.status)item.el.dataset.status=data.status;
        setSaveState(data.duplicate?'Saved · synced':'Saved','saved');
        return data;
      }catch(error){
        if(error.status===401||error.status===403||error.status===409){
          setSaveState('Not saved','error');
          throw error;
        }
        if(attempt===0){
          await new Promise(resolve=>setTimeout(resolve,350));
          continue;
        }
        setSaveState('Not saved','error');
        throw error;
      }
    }
    throw new Error('Could not save progress.');
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
    if(instruction)instruction.innerHTML='<i class="bi bi-check-circle"></i> Every completed rating is saved.';
    setSaveState('Saved','saved');
    if(knownNode)knownNode.textContent=stats.known;
    if(againNode)againNode.textContent=stats.again;
  }

  async function mark(outcome){
    if(transitioning||!flipped||!current)return;
    transitioning=true;
    updateHud();

    const item=current;
    try{
      const data=await saveReview(item,outcome);
      if(data.status)item.el.dataset.status=data.status;
    }catch(error){
      transitioning=false;
      updateHud();
      const message=error.status===409
        ? 'Progress changed elsewhere. Reload this deck before continuing.'
        : (error.message||'Progress was not saved. Check your connection and try again.');
      showToast(message,'error',2200);
      return;
    }

    stats[outcome]=(stats[outcome]||0)+1;
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
    void mark(button.dataset.outcome);
  }));
  document.addEventListener('keydown',event=>{
    if(event.repeat||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName))return;
    if(event.code==='Space'){event.preventDefault();flip();return;}
    if(!flipped)return;
    if(event.key==='1')void mark('again');
    if(event.key==='2')void mark('learning');
    if(event.key==='3')void mark('known');
  });

  setSaveState('Saved','saved');
  next();
})();
