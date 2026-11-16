/* V80: Universities catalogue — instant search with suggestions, filters, sorting and
   Reach / Match / Safety badges for the student's SAT score. Data comes from the page
   (json_script #mk80-uni-data); nothing is sent to the server. */
(function () {
  'use strict';
  var root = document.querySelector('[data-uni-catalogue]');
  var dataNode = document.getElementById('mk80-uni-data');
  if (!root || !dataNode) return;

  var rows = [];
  try { rows = JSON.parse(dataNode.textContent) || []; } catch (error) { rows = []; }

  var PAGE = 24;
  var RANK = { top10: 1, top50: 2, top100: 3, top200: 4, top500: 5, other: 6 };
  var RANK_LABEL = { top10: 'Top 10', top50: 'Top 50', top100: 'Top 100', top200: 'Top 200', top500: 'Top 500', other: '' };
  var POLICY = { required: 'SAT required', optional: 'Test optional', recommended: 'SAT recommended', accepted: 'SAT accepted', blind: 'Test blind' };
  var AID = { need_blind: 'Need-blind aid', need_aware: 'Need-based aid', merit: 'Merit scholarships', limited: 'Limited aid', none: 'No aid' };
  var PLATFORM = { common_app: 'Common App', ucas: 'UCAS', direct: 'University portal', ouac: 'OUAC', coalition: 'Coalition', other: 'Other' };
  var FIT = { reach: 'Reach', match: 'Match', safety: 'Safety' };
  var STORE = 'makonbook.universities.v80';

  var search = root.querySelector('[data-uni-search]');
  var suggest = root.querySelector('[data-uni-suggest]');
  var scoreInput = root.querySelector('[data-uni-score]');
  var grid = root.querySelector('[data-uni-grid]');
  var countNode = root.querySelector('[data-uni-count]');
  var moreButton = root.querySelector('[data-uni-more]');
  var emptyNode = root.querySelector('[data-uni-empty]');
  var resetButtons = root.querySelectorAll('[data-uni-reset]');
  var sortSelect = root.querySelector('[data-uni-sort]');
  var tuitionInput = root.querySelector('[data-uni-filter="tuition"]');
  var tuitionLabel = root.querySelector('[data-uni-tuition-label]');
  var filterToggle = root.querySelector('[data-uni-filter-toggle]');
  var filterCount = root.querySelector('[data-uni-filter-count]');
  var filterPanel = root.querySelector('[data-uni-filters]');
  var detailBase = root.dataset.detailBase || '/student/universities/';

  var state = { q: '', region: '', limit: PAGE, active: -1 };

  function safeGet() { try { return JSON.parse(window.localStorage.getItem(STORE) || 'null'); } catch (error) { return null; } }
  function safeSet(value) { try { window.localStorage.setItem(STORE, JSON.stringify(value)); } catch (error) { /* private mode */ } }

  function fold(text) {
    return String(text || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]+/g, ' ');
  }
  rows.forEach(function (row) {
    row._name = fold(row.n);
    row._hay = fold(row.n + ' ' + row.c + ' ' + row.ci);
    row._words = row._hay.split(' ').filter(Boolean);
    row._initials = row.n.replace(/\(.*?\)/g, '').split(/\s+/).filter(function (w) { return /^[A-Z]/.test(w); }).map(function (w) { return w[0]; }).join('').toLowerCase();
    var paren = /\(([^)]+)\)/.exec(row.n);
    row._alias = paren ? fold(paren[1]) : '';
  });

  function score() {
    var value = parseInt(scoreInput && scoreInput.value, 10);
    return value >= 400 && value <= 1600 ? value : 0;
  }

  /* Same rules as apps/sat/views_admissions.py::university_fit */
  function fit(row, sat) {
    var rate = row.a;
    if (rate !== null && rate < 10) return 'reach';
    if (!sat || row.sk === 'none' || !row.lo) return rate !== null && rate < 20 ? 'reach' : '';
    var high = row.hi || row.lo;
    if (sat < row.lo) return 'reach';
    if (sat < high) return rate !== null && rate < 20 ? 'reach' : 'match';
    return rate === null || rate >= 30 ? 'safety' : 'match';
  }

  function filters() {
    var out = {};
    root.querySelectorAll('[data-uni-filter]').forEach(function (el) { out[el.dataset.uniFilter] = el.value; });
    return out;
  }

  function matchesQuery(row, q) {
    if (!q) return true;
    var words = q.split(' ').filter(Boolean);
    /* Each typed word must start a word of the name, city or country ("mit" finds MIT, not Smith);
       longer words (5+ letters) may also match inside a word. */
    return words.every(function (word) {
      if (row._initials === word || row._alias === word) return true;
      for (var i = 0; i < row._words.length; i += 1) { if (row._words[i].indexOf(word) === 0) return true; }
      return word.length >= 5 && row._hay.indexOf(word) !== -1;
    });
  }

  function queryRank(row, q) {
    if (!q) return 0;
    if (row._alias === q || row._initials === q) return 0;
    if (row._name.indexOf(q) === 0) return 1;
    if (row._name.indexOf(' ' + q) !== -1) return 2;
    return 3;
  }

  function apply() {
    var f = filters();
    var sat = score();
    var q = fold(state.q).trim().replace(/\s+/g, ' ');
    var maxTuition = parseInt(f.tuition, 10);
    var anyTuition = maxTuition >= 70000;
    var list = rows.filter(function (row) {
      row._fit = fit(row, sat);
      if (!matchesQuery(row, q)) return false;
      if (state.region && row.r !== state.region) return false;
      if (f.country && row.c !== f.country) return false;
      if (f.rank && RANK[row.rb] > RANK[f.rank]) return false;
      if (!anyTuition && (row.t === null || row.t > maxTuition)) return false;
      if (f.acceptance) {
        if (row.a === null) return false;
        if (f.acceptance === '50+' ? row.a < 50 : row.a >= parseFloat(f.acceptance)) return false;
      }
      if (f.aid === 'need' ? (row.ai !== 'need_blind' && row.ai !== 'need_aware') : (f.aid && row.ai !== f.aid)) return false;
      if (f.policy === 'uses' ? (row.tp === 'blind' || row.sk === 'none') : (f.policy && row.tp !== f.policy)) return false;
      if (f.platform && row.p !== f.platform) return false;
      if (f.kind && row.k !== f.kind) return false;
      if (f.fit === 'fits' ? (row._fit !== 'match' && row._fit !== 'safety') : (f.fit && row._fit !== f.fit)) return false;
      return true;
    });

    var sort = sortSelect ? sortSelect.value : 'rank';
    var big = 1e9;
    list.sort(function (a, b) {
      if (q) { var qa = queryRank(a, q), qb = queryRank(b, q); if (qa !== qb) return qa - qb; }
      var diff = 0;
      if (sort === 'acceptance') diff = (a.a === null ? big : a.a) - (b.a === null ? big : b.a);
      else if (sort === 'acceptance-desc') diff = (b.a === null ? -1 : b.a) - (a.a === null ? -1 : a.a);
      else if (sort === 'tuition') diff = (a.t === null ? big : a.t) - (b.t === null ? big : b.t);
      else if (sort === 'tuition-desc') diff = (b.t === null ? -1 : b.t) - (a.t === null ? -1 : a.t);
      else if (sort === 'sat') diff = ((b.hi || b.lo || 0) - (a.hi || a.lo || 0));
      else if (sort === 'rank') diff = RANK[a.rb] - RANK[b.rb] || (a.a === null ? big : a.a) - (b.a === null ? big : b.a);
      return diff || a.n.localeCompare(b.n);
    });

    render(list);
    var active = countActive(f);
    if (filterCount) { filterCount.hidden = !active; filterCount.textContent = active; }
    resetButtons.forEach(function (button) { button.hidden = !(active || q || state.region) && button.closest('.mk80-results-head'); });
    if (tuitionLabel) tuitionLabel.textContent = anyTuition ? 'Any' : (maxTuition === 0 ? 'Free' : '$' + Math.round(maxTuition / 1000) + 'k');
    save(f);
  }

  function countActive(f) {
    return Object.keys(f).filter(function (key) { return key === 'tuition' ? parseInt(f[key], 10) < 70000 : !!f[key]; }).length;
  }

  function money(value) {
    if (value === null || value === undefined) return '—';
    if (value === 0) return 'Free*';
    return value >= 1000 ? '$' + Math.round(value / 1000) + 'k' : '$' + value;
  }

  function satText(row) {
    if (row.sk === 'none' || !row.lo) return row.tp === 'blind' ? 'Not used' : '—';
    if (row.sk === 'minimum') return row.lo + '+';
    return row.lo + '–' + (row.hi || row.lo);
  }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  function card(row) {
    var link = el('a', 'mk80-uni-card');
    link.href = detailBase + encodeURIComponent(row.s) + '/';
    var top = el('div', 'mk80-uni-top');
    var place = el('span', 'mk80-uni-place');
    place.appendChild(el('span', 'mk80-flag', row.f));
    place.appendChild(el('span', '', row.ci ? row.ci + ' · ' + row.c : row.c));
    top.appendChild(place);
    if (RANK_LABEL[row.rb]) top.appendChild(el('span', 'mk80-rank mk80-rank-' + row.rb, RANK_LABEL[row.rb]));
    link.appendChild(top);
    var title = el('h3', '', row.n);
    link.appendChild(title);
    if (row._fit) {
      var badge = el('span', 'mk80-fit mk80-fit-' + row._fit, FIT[row._fit]);
      link.appendChild(badge);
    }
    var stats = el('dl', 'mk80-uni-stats');
    [['Accepted', row.a === null ? '—' : row.a + '%'], ['SAT', satText(row)], ['Tuition', money(row.t)]].forEach(function (pair) {
      var item = el('div');
      item.appendChild(el('dt', '', pair[0]));
      item.appendChild(el('dd', '', pair[1]));
      stats.appendChild(item);
    });
    link.appendChild(stats);
    var chips = el('div', 'mk80-chips');
    chips.appendChild(el('span', 'mk80-chip mk80-chip-policy-' + row.tp, POLICY[row.tp] || ''));
    chips.appendChild(el('span', 'mk80-chip mk80-chip-aid-' + row.ai, AID[row.ai] || ''));
    chips.appendChild(el('span', 'mk80-chip', PLATFORM[row.p] || ''));
    link.appendChild(chips);
    return link;
  }

  function render(list) {
    grid.textContent = '';
    var frag = document.createDocumentFragment();
    list.slice(0, state.limit).forEach(function (row) { frag.appendChild(card(row)); });
    grid.appendChild(frag);
    var shown = Math.min(list.length, state.limit);
    countNode.textContent = list.length === rows.length
      ? rows.length + ' universities'
      : 'Showing ' + list.length + ' of ' + rows.length + ' universities';
    if (moreButton) { moreButton.hidden = shown >= list.length; moreButton.textContent = 'Show more (' + (list.length - shown) + ' left)'; }
    emptyNode.hidden = list.length > 0;
  }

  /* ---------------- suggestions */
  function suggestions(q) {
    var term = fold(q).trim().replace(/\s+/g, ' ');
    if (term.length < 1) return [];
    var countries = {};
    var unis = rows.filter(function (row) { return matchesQuery(row, term); })
      .sort(function (a, b) { return queryRank(a, term) - queryRank(b, term) || RANK[a.rb] - RANK[b.rb] || a.n.localeCompare(b.n); })
      .slice(0, 6)
      .map(function (row) { return { kind: 'uni', row: row }; });
    rows.forEach(function (row) { if (fold(row.c).indexOf(term) === 0) countries[row.c] = row.f; });
    var countryItems = Object.keys(countries).slice(0, 2).map(function (name) { return { kind: 'country', name: name, flag: countries[name] }; });
    return countryItems.concat(unis);
  }

  function highlight(text, q) {
    var frag = document.createDocumentFragment();
    var term = String(q || '').trim();
    var index = term ? text.toLowerCase().indexOf(term.toLowerCase()) : -1;
    if (index < 0) { frag.appendChild(document.createTextNode(text)); return frag; }
    frag.appendChild(document.createTextNode(text.slice(0, index)));
    frag.appendChild(el('mark', '', text.slice(index, index + term.length)));
    frag.appendChild(document.createTextNode(text.slice(index + term.length)));
    return frag;
  }

  var currentSuggestions = [];
  function openSuggest() {
    currentSuggestions = suggestions(search.value);
    state.active = -1;
    suggest.textContent = '';
    if (!currentSuggestions.length) { closeSuggest(); return; }
    currentSuggestions.forEach(function (item, index) {
      var option = el('button', 'mk80-suggest-item');
      option.type = 'button';
      option.setAttribute('role', 'option');
      option.id = 'mk80Opt' + index;
      option.dataset.index = index;
      if (item.kind === 'country') {
        option.appendChild(el('span', 'mk80-flag', item.flag));
        var label = el('span', 'mk80-suggest-main');
        label.appendChild(el('strong', '', 'All universities in '));
        label.lastChild.appendChild(highlight(item.name, search.value));
        option.appendChild(label);
        option.appendChild(el('small', '', 'Country'));
      } else {
        option.appendChild(el('span', 'mk80-flag', item.row.f));
        var main = el('span', 'mk80-suggest-main');
        var strong = el('strong');
        strong.appendChild(highlight(item.row.n, search.value));
        main.appendChild(strong);
        main.appendChild(el('small', '', (item.row.ci ? item.row.ci + ', ' : '') + item.row.c));
        option.appendChild(main);
        if (RANK_LABEL[item.row.rb]) option.appendChild(el('small', 'mk80-suggest-rank', RANK_LABEL[item.row.rb]));
      }
      option.addEventListener('mousedown', function (event) { event.preventDefault(); choose(index); });
      suggest.appendChild(option);
    });
    suggest.hidden = false;
    search.setAttribute('aria-expanded', 'true');
  }

  function closeSuggest() {
    suggest.hidden = true;
    search.setAttribute('aria-expanded', 'false');
    search.removeAttribute('aria-activedescendant');
    state.active = -1;
  }

  function choose(index) {
    var item = currentSuggestions[index];
    if (!item) return;
    if (item.kind === 'uni') { window.location.href = detailBase + encodeURIComponent(item.row.s) + '/'; return; }
    var countrySelect = root.querySelector('[data-uni-filter="country"]');
    if (countrySelect) countrySelect.value = item.name;
    search.value = '';
    state.q = '';
    closeSuggest();
    state.limit = PAGE;
    apply();
  }

  function moveActive(step) {
    var options = suggest.querySelectorAll('.mk80-suggest-item');
    if (!options.length) return;
    state.active = (state.active + step + options.length) % options.length;
    options.forEach(function (option, index) { option.classList.toggle('is-active', index === state.active); option.setAttribute('aria-selected', index === state.active ? 'true' : 'false'); });
    search.setAttribute('aria-activedescendant', options[state.active].id);
  }

  var timer = null;
  search.addEventListener('input', function () {
    openSuggest();
    clearTimeout(timer);
    timer = setTimeout(function () { state.q = search.value; state.limit = PAGE; apply(); }, 90);
  });
  search.addEventListener('focus', function () { if (search.value) openSuggest(); });
  search.addEventListener('blur', function () { setTimeout(closeSuggest, 120); });
  search.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowDown') { event.preventDefault(); if (suggest.hidden) openSuggest(); moveActive(1); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); moveActive(-1); }
    else if (event.key === 'Enter') { if (state.active >= 0) { event.preventDefault(); choose(state.active); } else { closeSuggest(); } }
    else if (event.key === 'Escape') { closeSuggest(); }
  });
  document.addEventListener('keydown', function (event) {
    if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey) return;
    var tag = (document.activeElement && document.activeElement.tagName) || '';
    if (/INPUT|TEXTAREA|SELECT/.test(tag) || (document.activeElement && document.activeElement.isContentEditable)) return;
    event.preventDefault();
    search.focus();
  });

  /* ---------------- filters */
  root.querySelectorAll('[data-uni-region]').forEach(function (button) {
    button.addEventListener('click', function () {
      state.region = button.dataset.uniRegion;
      root.querySelectorAll('[data-uni-region]').forEach(function (b) { b.classList.toggle('is-active', b === button); b.setAttribute('aria-pressed', b === button ? 'true' : 'false'); });
      state.limit = PAGE;
      apply();
    });
  });
  root.querySelectorAll('[data-uni-filter], [data-uni-sort]').forEach(function (input) {
    input.addEventListener(input.type === 'range' ? 'input' : 'change', function () { state.limit = PAGE; apply(); });
  });
  if (scoreInput) scoreInput.addEventListener('input', function () { apply(); });
  if (moreButton) moreButton.addEventListener('click', function () { state.limit += PAGE * 2; apply(); });
  resetButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      root.querySelectorAll('[data-uni-filter]').forEach(function (input) { input.value = input.type === 'range' ? input.max : ''; });
      if (sortSelect) sortSelect.value = 'rank';
      search.value = '';
      state.q = '';
      state.region = '';
      root.querySelectorAll('[data-uni-region]').forEach(function (b) { b.classList.toggle('is-active', !b.dataset.uniRegion); });
      state.limit = PAGE;
      apply();
    });
  });
  if (filterToggle && filterPanel) {
    filterToggle.addEventListener('click', function () {
      var open = !root.classList.contains('is-filters-open');
      root.classList.toggle('is-filters-open', open);
      filterToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  /* ---------------- remember filters per viewer */
  function save(f) { safeSet({ f: f, region: state.region, sort: sortSelect ? sortSelect.value : 'rank', score: scoreInput ? scoreInput.value : '' }); }
  (function restore() {
    var saved = safeGet();
    if (!saved || typeof saved !== 'object') return;
    var f = saved.f || {};
    root.querySelectorAll('[data-uni-filter]').forEach(function (input) {
      var value = f[input.dataset.uniFilter];
      if (value === undefined || value === null) return;
      if (input.tagName === 'SELECT' && !Array.prototype.some.call(input.options, function (o) { return o.value === value; })) return;
      input.value = value;
    });
    if (sortSelect && saved.sort) sortSelect.value = saved.sort;
    if (saved.region !== undefined) {
      var regionButton = root.querySelector('[data-uni-region="' + String(saved.region).replace(/"/g, '') + '"]');
      if (regionButton) {
        state.region = saved.region;
        root.querySelectorAll('[data-uni-region]').forEach(function (b) { b.classList.toggle('is-active', b === regionButton); });
      }
    }
    if (scoreInput && saved.score && !scoreInput.dataset.best) scoreInput.value = saved.score;
    else if (scoreInput && saved.score && saved.score !== scoreInput.dataset.best) scoreInput.value = saved.score;
  })();

  apply();
})();
