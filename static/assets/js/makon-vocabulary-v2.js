(function(){
  function getCookie(name){
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for(const cookie of cookies){
      const [key, ...rest] = cookie.trim().split('=');
      if(key === name) return decodeURIComponent(rest.join('='));
    }
    return '';
  }

  function initWordSearch(){
    const search = document.querySelector('[data-vocab-search]');
    if(!search) return;
    const units = Array.from(document.querySelectorAll('[data-vocab-unit]'));
    const status = document.querySelector('[data-vocab-search-status]');
    const run = () => {
      const query = search.value.trim().toLowerCase();
      let shownUnits = 0;
      units.forEach((unit) => {
        const rows = Array.from(unit.querySelectorAll('[data-vocab-word-row]'));
        let shownRows = 0;
        rows.forEach((row) => {
          const visible = !query || (row.dataset.search || '').includes(query);
          row.hidden = !visible;
          if(visible) shownRows += 1;
        });
        const unitVisible = !query || shownRows > 0 || (unit.dataset.search || '').includes(query);
        unit.hidden = !unitVisible;
        if(unitVisible){
          shownUnits += 1;
          if(query && unit.tagName === 'DETAILS') unit.open = true;
        }
      });
      if(status) status.textContent = query ? `${shownUnits} unit${shownUnits === 1 ? '' : 's'} matched.` : `${units.length} units available.`;
    };
    search.addEventListener('input', run);
    run();
  }

  function initFlashcards(){
    const deck = document.querySelector('[data-vocab-deck]');
    if(!deck) return;

    const cards = Array.from(deck.querySelectorAll('[data-flashcard]'));
    if(!cards.length) return;

    const counter = deck.querySelector('[data-deck-counter]');
    const mobileCounter = deck.querySelector('[data-mobile-deck-counter]');
    const progress = deck.querySelector('[data-deck-progress]');
    const status = deck.querySelector('[data-deck-status]');
    const mobileStatus = deck.querySelector('[data-mobile-deck-status]');
    const feedback = deck.querySelector('[data-deck-feedback]');
    const saveState = deck.querySelector('[data-deck-save-state]');
    const mobileSaveState = deck.querySelector('[data-mobile-save-state]');
    const summaryMastered = document.querySelector('[data-summary-mastered]');
    const summaryLearning = document.querySelector('[data-summary-learning]');
    const summaryReviews = document.querySelector('[data-summary-reviews]');
    const summaryAccuracy = document.querySelector('[data-summary-accuracy]');
    const summaryCompletion = document.querySelector('[data-summary-completion]');
    const unitMasteredLabel = deck.querySelector('[data-unit-mastered-label]');
    const unitLearningLabel = deck.querySelector('[data-unit-learning-label]');
    const selectedUnitMastered = document.querySelector('[data-selected-unit-mastered]');
    const mobileMastered = deck.querySelector('[data-mobile-mastered]');
    const mobileLearning = deck.querySelector('[data-mobile-learning]');
    const markUrl = deck.dataset.markUrl;
    const embeddedCsrfToken = deck.dataset.csrfToken || '';
    const csrfToken = (embeddedCsrfToken && embeddedCsrfToken !== 'NOTPROVIDED')
      ? embeddedCsrfToken
      : (getCookie('makonbook_csrftoken_v35') || getCookie('csrftoken'));
    const controls = Array.from(deck.querySelectorAll('[data-outcome]'));
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const outcomeConfig = {
      again: { label:'Again', message:'Marked for immediate repetition.', className:'rating-again' },
      learning: { label:'Learning', message:'Kept in the learning queue.', className:'rating-learning' },
      known: { label:'Know it', message:'Strong recall recorded.', className:'rating-known' }
    };

    const numberFrom = (value, fallback=0) => {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : fallback;
    };

    let summaryMasteredValue = numberFrom(deck.dataset.summaryMastered, numberFrom(summaryMastered?.textContent));
    let summaryLearningValue = numberFrom(deck.dataset.summaryLearning, numberFrom(summaryLearning?.textContent));
    let summaryReviewsValue = numberFrom(deck.dataset.summaryReviews, numberFrom(summaryReviews?.textContent));
    let summaryCorrectValue = numberFrom(deck.dataset.summaryCorrect, 0);
    let summaryIncorrectValue = numberFrom(deck.dataset.summaryIncorrect, 0);
    const summaryTotalValue = Math.max(0, numberFrom(deck.dataset.summaryTotal, cards.length));
    let unitMasteredValue = numberFrom(deck.dataset.unitMastered, numberFrom(unitMasteredLabel?.textContent));
    let unitLearningValue = numberFrom(deck.dataset.unitLearning, numberFrom(unitLearningLabel?.textContent));
    const unitWordCount = Math.max(0, numberFrom(deck.dataset.unitWordCount, cards.length));

    const findResumeIndex = () => {
      const unseenIndex = cards.findIndex((card) => numberFrom(card.dataset.timesSeen, 0) === 0);
      if(unseenIndex >= 0) return unseenIndex;
      const learningIndex = cards.findIndex((card) => (card.dataset.status || 'new') !== 'mastered');
      return learningIndex >= 0 ? learningIndex : 0;
    };

    let index = findResumeIndex();
    let transitionLocked = false;
    let pendingSaves = 0;
    let failedSaves = 0;

    const setFeedback = (message, tone='neutral') => {
      if(!feedback) return;
      feedback.textContent = message;
      feedback.dataset.tone = tone;
    };

    const renderSaveState = (target) => {
      if(!target) return;
      target.classList.toggle('has-error', failedSaves > 0);
      target.classList.toggle('is-saving', pendingSaves > 0);
      if(failedSaves > 0){
        target.textContent = 'Not saved';
      }else if(pendingSaves > 0){
        target.textContent = 'Saving…';
      }else{
        target.textContent = 'Saved';
      }
    };

    const updateSaveState = () => {
      renderSaveState(saveState);
      renderSaveState(mobileSaveState);
    };

    const renderProgressNumbers = () => {
      if(summaryMastered) summaryMastered.textContent = String(summaryMasteredValue);
      if(summaryLearning) summaryLearning.textContent = String(summaryLearningValue);
      if(summaryReviews) summaryReviews.textContent = String(summaryReviewsValue);

      const attempts = summaryCorrectValue + summaryIncorrectValue;
      const accuracy = attempts ? Math.round((summaryCorrectValue / attempts) * 1000) / 10 : 0;
      if(summaryAccuracy) summaryAccuracy.textContent = `${accuracy}%`;
      if(summaryCompletion){
        const completion = summaryTotalValue ? Math.round((summaryMasteredValue / summaryTotalValue) * 10000) / 100 : 0;
        summaryCompletion.textContent = `${completion}%`;
      }

      if(unitMasteredLabel) unitMasteredLabel.textContent = String(unitMasteredValue);
      if(unitLearningLabel) unitLearningLabel.textContent = String(unitLearningValue);
      if(selectedUnitMastered) selectedUnitMastered.textContent = `${unitMasteredValue}/${unitWordCount}`;
      if(mobileMastered) mobileMastered.textContent = String(unitMasteredValue);
      if(mobileLearning) mobileLearning.textContent = String(unitLearningValue);
    };

    const setControlsEnabled = (enabled) => {
      controls.forEach((button) => {
        button.disabled = !enabled;
        button.setAttribute('aria-disabled', String(!enabled));
      });
      deck.classList.toggle('can-rate', enabled);
    };

    const activeCard = () => cards[index];

    const updateDeckMeta = () => {
      const active = activeCard();
      const cardCounter = `${index + 1} / ${cards.length}`;
      const cardStatus = active.dataset.status || 'new';
      if(counter) counter.textContent = cardCounter;
      if(mobileCounter) mobileCounter.textContent = cardCounter;
      if(progress) progress.style.width = `${((index + 1) / cards.length) * 100}%`;
      if(status) status.textContent = cardStatus;
      if(mobileStatus) mobileStatus.textContent = cardStatus;
      setControlsEnabled(active.classList.contains('flipped') && !transitionLocked);
    };

    const activateCard = (nextIndex, direction=1) => {
      index = (nextIndex + cards.length) % cards.length;
      cards.forEach((card, cardIndex) => {
        const isActive = cardIndex === index;
        card.classList.toggle('active', isActive);
        card.classList.remove('flipped', 'is-rating', 'rating-again', 'rating-learning', 'rating-known', 'is-entering-left', 'is-entering-right');
        card.setAttribute('aria-pressed', 'false');
        if(isActive){
          card.classList.add(direction < 0 ? 'is-entering-left' : 'is-entering-right');
          window.setTimeout(() => card.classList.remove('is-entering-left', 'is-entering-right'), prefersReducedMotion ? 0 : 260);
        }
      });
      deck.classList.remove('is-flipped');
      setFeedback('Flip the card, then rate your recall.');
      updateDeckMeta();
    };

    const flip = () => {
      if(transitionLocked) return;
      const active = activeCard();
      const willFlip = !active.classList.contains('flipped');
      active.classList.toggle('flipped', willFlip);
      active.setAttribute('aria-pressed', String(willFlip));
      deck.classList.toggle('is-flipped', willFlip);
      setFeedback(
        willFlip ? 'How well did you recall it? Choose 1, 2, or 3.' : 'Answer hidden. Recall it before flipping again.',
        willFlip ? 'ready' : 'neutral'
      );
      updateDeckMeta();
    };

    const move = (direction) => {
      if(transitionLocked) return;
      transitionLocked = true;
      setControlsEnabled(false);
      const current = activeCard();
      current.classList.add(direction < 0 ? 'is-leaving-right' : 'is-leaving-left');
      const delay = prefersReducedMotion ? 0 : 150;
      window.setTimeout(() => {
        current.classList.remove('is-leaving-left', 'is-leaving-right');
        activateCard(index + direction, direction);
        transitionLocked = false;
        updateDeckMeta();
      }, delay);
    };

    const postReviewOnce = async(wordId, outcome, expectedTimesSeen) => {
      if(!csrfToken){
        const error = new Error('Secure session token is missing. Reload the page and try again.');
        error.noRetry = true;
        throw error;
      }
      const response = await fetch(markUrl, {
        method:'POST',
        credentials:'same-origin',
        headers:{
          'Content-Type':'application/json',
          'X-CSRFToken':csrfToken,
          'X-Requested-With':'XMLHttpRequest'
        },
        body:JSON.stringify({
          word_id:wordId,
          outcome,
          expected_times_seen:expectedTimesSeen
        }),
        keepalive:true
      });
      let data = {};
      try{ data = await response.json(); }catch(error){ data = {}; }
      if(!response.ok || !data.ok){
        const error = new Error(data.error || 'Could not save progress.');
        error.status = response.status;
        error.noRetry = response.status >= 400 && response.status < 500;
        throw error;
      }
      return data;
    };

    const postReview = async(wordId, outcome, expectedTimesSeen) => {
      let lastError = null;
      for(let attempt = 0; attempt < 2; attempt += 1){
        try{
          return await postReviewOnce(wordId, outcome, expectedTimesSeen);
        }catch(error){
          lastError = error;
          if(error.noRetry || attempt === 1) throw error;
          await new Promise((resolve) => window.setTimeout(resolve, 500));
        }
      }
      throw lastError || new Error('Could not save progress.');
    };

    const applyStatusDelta = (previousStatus, nextStatus) => {
      if(previousStatus === nextStatus) return;

      if(previousStatus === 'mastered'){
        summaryMasteredValue = Math.max(0, summaryMasteredValue - 1);
        unitMasteredValue = Math.max(0, unitMasteredValue - 1);
      }else if(previousStatus === 'learning'){
        summaryLearningValue = Math.max(0, summaryLearningValue - 1);
        unitLearningValue = Math.max(0, unitLearningValue - 1);
      }

      if(nextStatus === 'mastered'){
        summaryMasteredValue += 1;
        unitMasteredValue += 1;
      }else if(nextStatus === 'learning'){
        summaryLearningValue += 1;
        unitLearningValue += 1;
      }
    };

    const applySavedReview = (card, outcome, data, expectedTimesSeen) => {
      const previousStatus = card.dataset.status || 'new';
      const nextStatus = data.status || previousStatus;
      const serverTimesSeen = numberFrom(data.times_seen, expectedTimesSeen + 1);
      const countedReview = serverTimesSeen > expectedTimesSeen;

      applyStatusDelta(previousStatus, nextStatus);
      card.dataset.status = nextStatus;
      card.dataset.timesSeen = String(serverTimesSeen);

      const badge = card.querySelector('[data-card-status]');
      if(badge){
        badge.textContent = nextStatus;
        badge.className = `vocab-status vocab-status-${nextStatus}`;
        badge.setAttribute('data-card-status', '');
      }

      if(countedReview){
        summaryReviewsValue += 1;
        if(outcome === 'known') summaryCorrectValue += 1;
        else summaryIncorrectValue += 1;
      }

      renderProgressNumbers();
      if(card === activeCard()){
        if(status) status.textContent = nextStatus;
        if(mobileStatus) mobileStatus.textContent = nextStatus;
      }
    };

    const saveReview = async(card, outcome) => {
      const wordId = card.dataset.wordId;
      const expectedTimesSeen = numberFrom(card.dataset.timesSeen, 0);
      const wasFailed = card.classList.contains('save-failed');
      pendingSaves += 1;
      card.classList.add('is-saving');
      updateSaveState();

      try{
        const data = await postReview(wordId, outcome, expectedTimesSeen);
        if(wasFailed){
          failedSaves = Math.max(0, failedSaves - 1);
        }
        card.classList.remove('save-failed');
        applySavedReview(card, outcome, data, expectedTimesSeen);
        return data;
      }catch(error){
        if(!wasFailed) failedSaves += 1;
        card.classList.add('save-failed');
        setFeedback(error.message || 'Progress was not saved. Check your connection and try again.', 'error');
        return null;
      }finally{
        pendingSaves = Math.max(0, pendingSaves - 1);
        card.classList.remove('is-saving');
        updateSaveState();
      }
    };

    const mark = async(outcome, triggerButton=null) => {
      if(transitionLocked) return;
      const active = activeCard();
      if(!active.classList.contains('flipped')){
        setFeedback('Reveal the answer before rating your recall.', 'warning');
        active.classList.add('needs-flip');
        window.setTimeout(() => active.classList.remove('needs-flip'), 360);
        return;
      }

      const config = outcomeConfig[outcome];
      if(!config) return;

      transitionLocked = true;
      setControlsEnabled(false);
      active.classList.add('is-rating', config.className);
      triggerButton?.classList.add('is-pressed');
      setFeedback('Saving progress…', 'ready');

      const data = await saveReview(active, outcome);
      triggerButton?.classList.remove('is-pressed');
      active.classList.remove('is-rating', config.className);

      if(!data){
        transitionLocked = false;
        updateDeckMeta();
        return;
      }

      setFeedback(config.message, outcome === 'known' ? 'success' : outcome === 'again' ? 'warning' : 'ready');
      const delay = prefersReducedMotion ? 0 : 120;
      window.setTimeout(() => {
        activateCard(index + 1, 1);
        transitionLocked = false;
        updateDeckMeta();
      }, delay);
    };

    deck.querySelector('[data-deck-prev]')?.addEventListener('click', () => move(-1));
    deck.querySelector('[data-deck-next]')?.addEventListener('click', () => move(1));
    controls.forEach((button) => {
      button.addEventListener('click', () => mark(button.dataset.outcome, button));
    });

    cards.forEach((card) => {
      card.addEventListener('click', (event) => {
        if(event.target.closest('button,a')) return;
        flip();
      });
      card.addEventListener('keydown', (event) => {
        if(event.key === 'Enter'){
          event.preventDefault();
          flip();
        }
      });
    });

    document.addEventListener('keydown', (event) => {
      if(event.repeat) return;
      if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) return;
      if(document.activeElement?.closest('button,a')) return;

      if(event.code === 'Space'){
        event.preventDefault();
        flip();
      }else if(event.key === 'ArrowLeft'){
        event.preventDefault();
        move(-1);
      }else if(event.key === 'ArrowRight'){
        event.preventDefault();
        move(1);
      }else if(event.key === '1'){
        event.preventDefault();
        mark('again', deck.querySelector('[data-mark-again]'));
      }else if(event.key === '2'){
        event.preventDefault();
        mark('learning', deck.querySelector('[data-mark-learning]'));
      }else if(event.key === '3'){
        event.preventDefault();
        mark('known', deck.querySelector('[data-mark-known]'));
      }
    });

    window.addEventListener('pageshow', () => {
      updateSaveState();
      updateDeckMeta();
    });

    renderProgressNumbers();
    updateSaveState();
    activateCard(index, 1);
  }

  function initQuizBuilder(){
    const form = document.querySelector('[data-vocab-quiz-builder]');
    if(!form) return;
    const checkboxes = Array.from(form.querySelectorAll('input[name="units"]'));
    const countInput = form.querySelector('input[name="question_count"]');
    const selectedLabel = form.querySelector('[data-selected-units]');
    const availableLabel = form.querySelector('[data-available-words]');
    const submit = form.querySelector('button[type="submit"]');

    const update = () => {
      const selected = checkboxes.filter((box) => box.checked);
      const available = selected.reduce((sum, box) => sum + Number(box.dataset.wordCount || 0), 0);
      if(selectedLabel) selectedLabel.textContent = selected.length;
      if(availableLabel) availableLabel.textContent = available;
      if(countInput){
        countInput.max = Math.max(available, 1);
        if(available && Number(countInput.value) > available) countInput.value = available;
      }
      if(submit) submit.disabled = selected.length === 0 || available < 4;
    };

    checkboxes.forEach((box) => box.addEventListener('change', update));
    form.querySelector('[data-select-all]')?.addEventListener('click', () => {
      checkboxes.forEach((box) => { box.checked = true; });
      update();
    });
    form.querySelector('[data-clear-all]')?.addEventListener('click', () => {
      checkboxes.forEach((box) => { box.checked = false; });
      update();
    });
    form.addEventListener('submit', () => {
      if(submit){ submit.disabled = true; submit.textContent = 'Building quiz...'; }
    });
    update();
  }

  function initQuizTest(){
    const form = document.querySelector('[data-vocab-quiz-test]');
    if(!form) return;
    const groups = Array.from(form.querySelectorAll('[data-question-group]'));
    const answeredLabel = form.querySelector('[data-answered-count]');
    const meter = form.querySelector('[data-answer-meter]');
    const timer = form.querySelector('[data-quiz-timer]');
    const start = Date.now();

    const update = () => {
      let answered = 0;
      groups.forEach((group) => {
        const selected = group.querySelector('input[type="radio"]:checked');
        group.querySelectorAll('.vocab-choice').forEach((choice) => {
          choice.classList.toggle('selected', Boolean(choice.querySelector('input:checked')));
        });
        if(selected) answered += 1;
      });
      if(answeredLabel) answeredLabel.textContent = `${answered} / ${groups.length} answered`;
      if(meter) meter.style.width = `${groups.length ? (answered / groups.length) * 100 : 0}%`;
    };
    form.addEventListener('change', update);
    if(timer){
      window.setInterval(() => {
        const seconds = Math.floor((Date.now() - start) / 1000);
        const minutes = Math.floor(seconds / 60);
        timer.textContent = `${String(minutes).padStart(2,'0')}:${String(seconds % 60).padStart(2,'0')}`;
      },1000);
    }
    form.addEventListener('submit', (event) => {
      const unanswered = groups.filter((group) => !group.querySelector('input[type="radio"]:checked')).length;
      if(unanswered && !window.confirm(`${unanswered} questions are unanswered. Submit anyway?`)){
        event.preventDefault();
        return;
      }
      const button = form.querySelector('button[type="submit"]');
      if(button){ button.disabled = true; button.textContent = 'Checking answers...'; }
    });
    update();
  }

  initWordSearch();
  initFlashcards();
  initQuizBuilder();
  initQuizTest();
})();
