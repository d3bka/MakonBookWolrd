(function () {
  'use strict';
  var root = document.querySelector('[data-topic-drill]');
  if (!root) return;
  var slides = Array.prototype.slice.call(root.querySelectorAll('[data-question-slide]'));
  if (!slides.length) return;

  var index = 0;
  var answered = {};
  var prev = root.querySelector('[data-drill-prev]');
  var check = root.querySelector('[data-drill-check]');
  var next = root.querySelector('[data-drill-next]');
  var progress = root.querySelector('[data-drill-progress]');
  var track = root.querySelector('[data-drill-track]');

  function csrf() {
    var match = document.cookie.match(/(?:^|; )makonbook_csrftoken_v35=([^;]+)/) || document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }
  function active() { return slides[index]; }
  function show() {
    slides.forEach(function (slide, slideIndex) { slide.classList.toggle('is-active', slideIndex === index); });
    progress.textContent = (index + 1) + ' / ' + slides.length;
    track.style.width = (((index + 1) / slides.length) * 100) + '%';
    prev.disabled = index === 0;
    var done = !!answered[active().dataset.questionId];
    check.hidden = done;
    next.hidden = !done;
    next.innerHTML = index === slides.length - 1 ? 'Finish <i class="bi bi-check2"></i>' : 'Next <i class="bi bi-arrow-right"></i>';
  }
  function answerValue(slide) {
    if (slide.dataset.open === '1') {
      var input = slide.querySelector('[data-open-answer]');
      return input ? input.value.trim() : '';
    }
    var selected = slide.querySelector('[data-choice].is-selected');
    return selected ? selected.dataset.choice : '';
  }
  function renderFeedback(box, payload) {
    box.hidden = false;
    box.className = 'v523-answer-feedback ' + (payload.correct ? 'is-correct' : 'is-wrong');
    box.innerHTML = '';
    var title = document.createElement('strong');
    title.textContent = payload.correct ? 'Correct' : 'Not quite';
    box.appendChild(title);
    if (!payload.correct) {
      var answer = document.createElement('span');
      answer.textContent = 'Correct answer: ' + String(payload.answer || '');
      box.appendChild(answer);
    }
    if (payload.explanation_html) {
      // Rendered and escaped by the server (apps/sat/rich_text.py).
      var richExplanation = document.createElement('div');
      richExplanation.className = 'mk-rich';
      richExplanation.innerHTML = String(payload.explanation_html);
      box.appendChild(richExplanation);
      if (typeof window.renderMathInElement === 'function') {
        try {
          window.renderMathInElement(richExplanation, { delimiters: [
            { left: '\\(', right: '\\)', display: false },
            { left: '\\[', right: '\\]', display: true }
          ], throwOnError: false });
        } catch (error) { /* math stays as text */ }
      }
    } else if (payload.explanation) {
      var explanation = document.createElement('p');
      explanation.textContent = String(payload.explanation);
      box.appendChild(explanation);
    }
  }

  slides.forEach(function (slide) {
    slide.querySelectorAll('[data-choice]').forEach(function (button) {
      button.addEventListener('click', function () {
        if (answered[slide.dataset.questionId]) return;
        slide.querySelectorAll('[data-choice]').forEach(function (choice) { choice.classList.remove('is-selected'); });
        button.classList.add('is-selected');
      });
    });
    var input = slide.querySelector('[data-open-answer]');
    if (input) input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' && !check.hidden && !check.disabled) {
        event.preventDefault();
        check.click();
      }
    });
  });

  check.addEventListener('click', function () {
    var slide = active();
    var value = answerValue(slide);
    if (!value) {
      var emptyFeedback = slide.querySelector('[data-feedback]');
      emptyFeedback.hidden = false;
      emptyFeedback.className = 'v523-answer-feedback is-wrong';
      emptyFeedback.textContent = 'Choose or type an answer first.';
      return;
    }
    check.disabled = true;
    fetch(root.dataset.checkUrl, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify({ section: root.dataset.section, question_id: Number(slide.dataset.questionId), answer: value })
    }).then(function (response) {
      return response.json().then(function (payload) { return { ok: response.ok, payload: payload }; });
    }).then(function (result) {
      if (!result.ok) throw new Error(result.payload.error || 'Check failed');
      answered[slide.dataset.questionId] = true;
      renderFeedback(slide.querySelector('[data-feedback]'), result.payload);
      slide.querySelectorAll('[data-choice]').forEach(function (choice) { choice.disabled = true; });
      var input = slide.querySelector('[data-open-answer]');
      if (input) input.disabled = true;
      show();
    }).catch(function () {
      var feedback = slide.querySelector('[data-feedback]');
      feedback.hidden = false;
      feedback.className = 'v523-answer-feedback is-wrong';
      feedback.textContent = 'Could not check this answer. Try again.';
    }).finally(function () { check.disabled = false; });
  });

  prev.addEventListener('click', function () { if (index > 0) { index -= 1; show(); } });
  next.addEventListener('click', function () {
    if (index < slides.length - 1) { index += 1; show(); }
    else window.location.href = '/practice/';
  });
  show();
})();
