(function(){
  function csrfFrom(root){
    const input = root?.querySelector('input[name="csrfmiddlewaretoken"]') || document.querySelector('input[name="csrfmiddlewaretoken"]');
    if(input?.value) return input.value;
    const names = ['makonbook_csrftoken_v35','csrftoken'];
    for(const name of names){
      const row = document.cookie.split('; ').find((value) => value.startsWith(`${name}=`));
      if(row) return decodeURIComponent(row.split('=').slice(1).join('='));
    }
    return '';
  }

  function setToast(message, tone='success'){
    let toast = document.querySelector('[data-vd50-toast]');
    if(!toast){
      toast = document.createElement('div');
      toast.dataset.vd50Toast = '';
      toast.className = 'vd50-toast';
      toast.setAttribute('role','status');
      toast.setAttribute('aria-live','polite');
      document.body.appendChild(toast);
    }
    toast.dataset.tone = tone;
    toast.innerHTML = `<i class="bi ${tone === 'success' ? 'bi-check-circle-fill' : 'bi-exclamation-circle-fill'}"></i><span></span>`;
    toast.querySelector('span').textContent = message;
    toast.classList.add('is-visible');
    window.clearTimeout(toast._hideTimer);
    toast._hideTimer = window.setTimeout(() => toast.classList.remove('is-visible'), 2600);
  }

  function initCloneForms(){
    document.querySelectorAll('[data-deck-clone-form]').forEach((form) => {
      form.addEventListener('submit', async(event) => {
        event.preventDefault();
        if(form.dataset.busy === '1') return;
        const button = form.querySelector('button[type="submit"]');
        const card = form.closest('[data-library-card]');
        const original = button?.innerHTML || '';
        form.dataset.busy = '1';
        if(button){ button.disabled = true; button.innerHTML = '<span class="vd50-spinner"></span> Adding…'; }
        try{
          const response = await fetch(form.action, {
            method:'POST',
            credentials:'same-origin',
            headers:{
              'X-Requested-With':'XMLHttpRequest',
              'Accept':'application/json',
              'X-CSRFToken':csrfFrom(form),
            },
            body:new FormData(form),
          });
          const data = await response.json().catch(() => ({}));
          if(!response.ok || !data.ok) throw new Error(data.error || 'Could not add this deck.');
          card?.classList.add('is-added');
          const state = card?.querySelector('[data-clone-state]');
          if(state){
            state.className = 'vd50-added-state';
            state.innerHTML = '<i class="bi bi-check-circle-fill"></i> Added';
          }
          if(button){
            button.className = 'vd50-btn is-added';
            button.innerHTML = '<i class="bi bi-check-lg"></i> Added';
            button.disabled = true;
          }
          let open = card?.querySelector('[data-open-cloned]');
          if(!open && card && data.open_url){
            open = document.createElement('a');
            open.className = 'vd50-btn';
            open.dataset.openCloned = '';
            open.textContent = 'Open deck';
            form.parentElement?.insertBefore(open, form);
          }
          if(open && data.open_url){ open.href = data.open_url; open.hidden = false; }
          setToast(data.already_added ? 'Already in My decks.' : `${data.deck_title || 'Deck'} added to My decks.`);
          document.querySelectorAll('[data-deck-count]').forEach((node) => {
            if(data.added){ node.textContent = String((Number(node.textContent) || 0) + 1); }
          });
        }catch(error){
          if(button){ button.disabled = false; button.innerHTML = original; }
          setToast(error.message || 'Could not add this deck.', 'error');
        }finally{
          form.dataset.busy = '0';
        }
      });
    });
  }

  function initDialogs(){
    const pairs = [
      ['[data-deck-create-dialog]','[data-deck-create-open]','[data-deck-create-close]'],
      ['[data-word-create-dialog]','[data-word-create-open]','[data-word-create-close]'],
    ];
    pairs.forEach(([dialogSel,openSel,closeSel]) => {
      const dialog = document.querySelector(dialogSel);
      if(!dialog || typeof dialog.showModal !== 'function') return;
      document.querySelectorAll(openSel).forEach((button) => button.addEventListener('click', () => dialog.showModal()));
      dialog.querySelectorAll(closeSel).forEach((button) => button.addEventListener('click', () => dialog.close()));
      dialog.addEventListener('click', (event) => { if(event.target === dialog) dialog.close(); });
    });
  }

  function initSearch(){
    document.querySelectorAll('[data-deck-search]').forEach((input) => {
      const scope = input.closest('[data-deck-search-scope]') || document;
      const cards = Array.from(scope.querySelectorAll('[data-deck-search-item]'));
      const run = () => {
        const query = input.value.trim().toLowerCase();
        cards.forEach((card) => {
          card.hidden = Boolean(query && !(card.dataset.search || card.textContent || '').toLowerCase().includes(query));
        });
      };
      input.addEventListener('input', run);
    });
  }

  function initStudy(){
    const root = document.querySelector('[data-deck-study]');
    if(!root) return;
    const stage = root.querySelector('[data-study-stage]');
    const rate = root.querySelector('[data-rate]');
    const feedback = root.querySelector('[data-feedback]');
    const counter = root.querySelector('[data-counter]');
    const meter = root.querySelector('[data-session-meter]');
    const saveState = root.querySelector('[data-save-state]');
    const items = Array.from(root.querySelectorAll('[data-study-item]')).map((el) => ({el, again:0, learning:0}));
    if(!stage || !items.length) return;

    const total = items.length;
    const queue = items.slice();
    let current = null;
    let flipped = false;
    let busy = false;
    let completed = 0;
    const stats = {again:0, learning:0, known:0};

    function setFeedback(message, tone='neutral'){
      if(!feedback) return;
      feedback.textContent = message;
      feedback.dataset.tone = tone;
    }
    function setBusy(value){
      busy = value;
      root.classList.toggle('is-saving', value);
      rate?.querySelectorAll('button').forEach((button) => button.disabled = value || !flipped);
      if(saveState) saveState.textContent = value ? 'Saving…' : 'Saved';
    }
    function render(){
      root.querySelectorAll('[data-study-item]').forEach((el) => { el.hidden = !current || el !== current.el; });
      flipped = false;
      stage.classList.remove('is-flipped');
      if(rate) rate.hidden = true;
      if(counter) counter.textContent = `${completed} done · ${queue.length + (current ? 1 : 0)} left`;
      if(meter) meter.style.width = `${total ? Math.min(100,(completed / total) * 100) : 0}%`;
      setFeedback('Recall the word first, then reveal the answer.');
      setBusy(false);
    }
    function next(){
      current = queue.shift() || null;
      if(!current){ finish(); return; }
      render();
    }
    function flip(){
      if(busy || !current) return;
      flipped = !flipped;
      stage.classList.toggle('is-flipped', flipped);
      if(rate) rate.hidden = !flipped;
      rate?.querySelectorAll('button').forEach((button) => button.disabled = !flipped);
      setFeedback(flipped ? 'Rate the recall — not how familiar the answer looks.' : 'Answer hidden. Try to recall it before revealing.');
    }
    function finish(){
      current = null;
      stage.classList.remove('is-flipped');
      stage.innerHTML = `<div class="vd50-session-done"><span class="vd50-done-icon"><i class="bi bi-check-lg"></i></span><h2>Session complete</h2><p>${completed} cards completed · ${stats.known} got it · ${stats.learning} learning · ${stats.again} again</p><div class="vd50-actions"><a class="vd50-btn primary" href="${root.dataset.deckUrl}">Back to deck</a><a class="vd50-btn" href="${root.dataset.studyAllUrl}">Review all</a></div></div>`;
      if(rate) rate.hidden = true;
      if(counter) counter.textContent = `${completed} done`;
      if(meter) meter.style.width = '100%';
      if(saveState) saveState.textContent = 'Saved';
      setFeedback('Your review history is saved.');
    }
    async function mark(outcome){
      if(busy || !flipped || !current) return;
      setBusy(true);
      const token = csrfFrom(root);
      try{
        const response = await fetch(root.dataset.markUrl, {
          method:'POST',
          credentials:'same-origin',
          headers:{'Content-Type':'application/json','X-CSRFToken':token,'X-Requested-With':'XMLHttpRequest','Accept':'application/json'},
          body:JSON.stringify({word_id:current.el.dataset.wordId,outcome}),
        });
        const data = await response.json().catch(() => ({}));
        if(!response.ok || !data.ok) throw new Error(data.error || `Could not save review (${response.status}).`);
        stats[outcome] = (stats[outcome] || 0) + 1;
        current.el.dataset.status = data.status || current.el.dataset.status;
        let requeued = false;
        if(outcome === 'again' && current.again < 2){
          current.again += 1;
          queue.splice(Math.min(2,queue.length),0,current);
          requeued = true;
        }else if(outcome === 'learning' && current.learning < 1){
          current.learning += 1;
          queue.push(current);
          requeued = true;
        }
        if(!requeued) completed += 1;
        next();
      }catch(error){
        setBusy(false);
        setFeedback(error.message || 'Could not save this review. Try again.', 'error');
      }
    }

    stage.addEventListener('click', flip);
    stage.addEventListener('keydown', (event) => { if(event.key === 'Enter' || event.code === 'Space'){ event.preventDefault(); flip(); } });
    rate?.querySelectorAll('[data-outcome]').forEach((button) => button.addEventListener('click', () => mark(button.dataset.outcome)));
    document.addEventListener('keydown', (event) => {
      if(event.repeat || ['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) return;
      if(event.code === 'Space'){ event.preventDefault(); flip(); }
      if(!flipped) return;
      if(event.key === '1') mark('again');
      if(event.key === '2') mark('learning');
      if(event.key === '3') mark('known');
    });
    next();
  }

  initCloneForms();
  initDialogs();
  initSearch();
  initStudy();
})();
