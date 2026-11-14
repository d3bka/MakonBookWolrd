/* MakonBook V70 — Mako the panda.
 *
 * Panda(svg)   one rig: emotions, gaze that follows the pointer, blinking,
 *              talking, ear perks. Emotions blend through CSS transitions.
 * Companion    the corner Mako on student pages: greets once per session
 *              (by time of day or holiday), reacts to pokes (too many make
 *              him angry), gets bored and falls asleep when you are away,
 *              notices dark/light switches, toasts and the connection.
 * Home         Mako greets next to "Welcome back" and mirrors the server-side mood.
 *
 * Nothing here talks to the server; everything degrades to a calm panda.
 */
(() => {
  'use strict';
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = (list) => list[(Math.random() * list.length) | 0];
  const store = {
    get(area, key) { try { return window[area].getItem(key); } catch (e) { return null; } },
    set(area, key, value) { try { window[area].setItem(key, value); } catch (e) { /* storage blocked */ } },
  };

  // ------------------------------------------------------------------ rig
  class Panda {
    constructor(svg) {
      this.svg = svg;
      this.base = 'idle';
      this.timer = 0;
      this.locked = false;
      this.scheduleBlink();
    }

    get emotion() { return this.svg.dataset.emotion; }

    /** Show an emotion; with `hold` it returns to the base emotion afterwards. */
    set(emotion, hold = 0) {
      clearTimeout(this.timer);
      // restart CSS animations when the same emotion is set again
      if (this.svg.dataset.emotion === emotion) { this.svg.dataset.emotion = 'idle'; void this.svg.getBoundingClientRect(); }
      this.svg.dataset.emotion = emotion;
      if (hold) this.timer = setTimeout(() => { this.svg.dataset.emotion = this.base; }, hold);
    }

    setBase(emotion) { clearTimeout(this.timer); this.base = emotion; this.svg.dataset.emotion = emotion; }

    /** Point the pupils at a screen position (clamped inside the eye). */
    look(x, y) {
      if (['bored', 'sleepy', 'thinking', 'skeptical', 'sad'].includes(this.emotion)) {
        this.svg.style.removeProperty('--px'); this.svg.style.removeProperty('--py');
        return;
      }
      const r = this.svg.getBoundingClientRect();
      if (!r.width) return;
      const cx = r.left + r.width / 2, cy = r.top + r.height * .45;
      const dx = x - cx, dy = y - cy, d = Math.hypot(dx, dy) || 1;
      const reach = Math.min(1, d / 260) * 6.5;
      this.svg.style.setProperty('--px', `${(dx / d) * reach}px`);
      this.svg.style.setProperty('--py', `${(dy / d) * reach * .8}px`);
    }

    relaxGaze() { this.svg.style.removeProperty('--px'); this.svg.style.removeProperty('--py'); }

    blink() {
      if (this.emotion === 'sleepy') return;
      this.svg.classList.add('is-blink');
      setTimeout(() => this.svg.classList.remove('is-blink'), 120);
    }

    scheduleBlink() {
      setTimeout(() => {
        if (!document.hidden) {
          this.blink();
          if (Math.random() < .22) setTimeout(() => this.blink(), 260); // the occasional double blink
        }
        this.scheduleBlink();
      }, rand(2400, 6200));
    }

    talk(ms) {
      if (reduceMotion.matches) return;
      this.svg.classList.add('is-talking');
      clearTimeout(this.talkTimer);
      this.talkTimer = setTimeout(() => this.svg.classList.remove('is-talking'), ms);
    }

    perk() {
      this.svg.classList.remove('is-perk'); void this.svg.getBoundingClientRect();
      this.svg.classList.add('is-perk');
    }
  }

  const pandas = Array.from(document.querySelectorAll('[data-panda]')).map((svg) => new Panda(svg));
  if (!pandas.length) return;

  // every panda watches the pointer
  let frame = 0, lastPointer = null;
  window.addEventListener('pointermove', (e) => {
    lastPointer = e;
    if (frame) return;
    frame = requestAnimationFrame(() => { frame = 0; pandas.forEach((p) => p.look(lastPointer.clientX, lastPointer.clientY)); });
  }, { passive: true });
  document.addEventListener('pointerleave', () => pandas.forEach((p) => p.relaxGaze()));

  function burstAt(el, count) {
    if (!window.MakonSeason) return;
    const r = el.getBoundingClientRect();
    window.MakonSeason.burst(count, { x: r.left + r.width / 2, y: r.top + r.height / 3 });
  }

  // Pokes: a giggle, a line, and if you overdo it Mako gets cross.
  function pokeable(panda, el, say) {
    const hits = [];
    let calming = 0, cross = 0;
    el.addEventListener('click', () => {
      const now = Date.now();
      if (now < cross) return; // still cross (and then making up): more pokes don't reset that
      hits.push(now);
      while (hits.length && now - hits[0] > 2600) hits.shift();
      clearTimeout(calming);
      if (hits.length >= 5) {
        cross = now + 4700;
        panda.set('angry', 2600);
        say && say(pick(LINES.angry), 2600);
        calming = setTimeout(() => {
          panda.set('skeptical', 2000);
          say && say(pick(LINES.makeUp), 2000);
        }, 2700);
        hits.length = 0;
        return;
      }
      if (hits.length === 1 && Math.random() < .3) {
        panda.set('love', 1800);
        say && say(pick(LINES.love), 2200);
        return;
      }
      panda.set(hits.length >= 3 ? 'surprised' : 'happy', 1700);
      say && say(pick(LINES.poke), 2600);
      if (hits.length === 2) burstAt(el, 10);
    });
    el.addEventListener('dblclick', () => { panda.set('celebrate', 2100); burstAt(el, 26); });
    el.addEventListener('pointerenter', () => { panda.perk(); if (panda.emotion === panda.base && panda.base === 'idle') panda.set('happy', 1100); });
  }

  // ------------------------------------------------------------------ lines
  const LINES = {
    poke: [
      'Hehe, that tickles!', 'Ready for a quick practice set?', 'Small steps, big score.',
      'Bilim — kuch! Knowledge is power.', 'One more question? I believe in you.',
      'Water, a stretch, then one more module?', 'Your future self says thanks.',
      'Mistakes are just answers in disguise.', 'Focus mode: on. Snacks: later.',
    ],
    love: ['Aww. I like studying with you.', 'Best study buddy ever.', 'You make this panda proud.'],
    angry: ['Hey! Stop poking me!', 'Okay, okay — too many pokes!', 'Grr. I am a serious panda.'],
    makeUp: ['…fine. Friends again?', 'Hmph. Apology accepted.', 'Let’s get back to studying.'],
    bored: ['Psst… still there?', 'I counted every pixel twice.', 'Bamboo break is over, right?'],
    sleepy: ['Zzz… wake me up for the next question…', 'Just resting my eyes…'],
    wake: ['Oh! I’m awake, I’m awake!', 'Huh? Yes! Studying!', 'Back already? Great!'],
    welcomeBack: ['Welcome back!', 'There you are! Shall we continue?', 'Missed you. Let’s go!'],
    dark: ['Ooh, dark mode. Very night-owl.', 'Lights off — focus on.'],
    light: ['Bright and clear. Nice!', 'Light mode — fresh start.'],
    success: ['Done! Nicely handled.', 'Saved. You’re on a roll!', 'That worked. 🎉'],
    error: ['Hmm, something went wrong. Let’s try again.', 'Oops — check that once more?'],
    offline: ['Uh-oh, the internet just left.', 'We’re offline. I’ll wait here.'],
    online: ['We’re back online!', 'Internet’s back. Phew!'],
  };

  const SEASON_LINES = {
    spring: 'Bahor keldi! Spring is the best time to grow.',
    summer: 'Yoz! Stay cool, stay curious.',
    autumn: 'Kuz — the season of harvest. Let’s harvest some points.',
    winter: 'Qish! Warm tea, warm brain.',
  };

  function greeting(name, holiday) {
    if (holiday) return `${holiday} ${name ? `${name}, ` : ''}let’s make it a great day.`;
    const h = new Date().getHours();
    const who = name ? `, ${name}` : '';
    if (h >= 23 || h < 5) return `Late study session${who}? Don’t forget to sleep — rest helps memory.`;
    if (h < 11) return `Xayrli tong${who}! Fresh mind, fresh start.`;
    if (h < 17) return `Assalomu alaykum${who}! Ready to learn something new?`;
    return `Xayrli kech${who}! A short session still counts.`;
  }

  // ------------------------------------------------------------------ Home widget
  const widget = document.querySelector('[data-mako]');
  if (widget) {
    const svg = widget.querySelector('[data-panda]');
    const panda = pandas.find((p) => p.svg === svg);
    if (panda) {
      const MOOD = { celebrate: 'celebrate', nudge: 'worried', focus: 'thinking', welcome: 'greet', idle: 'happy' };
      const mood = MOOD[widget.dataset.makoState] || 'happy';
      const seen = widget.dataset.makoSeen === '1';
      setTimeout(() => {
        panda.set(seen ? 'happy' : mood, seen ? 1400 : 3200);
        if (!seen && mood === 'celebrate') burstAt(svg, 30);
      }, 350);
      const button = widget.querySelector('[data-mako-hello-panda]') || svg;
      pokeable(panda, button, null);
      // pressing Mako shows his next suggested step
      const steps = Array.from(widget.querySelectorAll('[data-mako-step]'));
      let current = 0;
      if (steps.length > 1) {
        button.addEventListener('click', () => {
          steps[current].hidden = true;
          current = (current + 1) % steps.length;
          steps[current].hidden = false;
        });
      }
    }
  }

  // any other panda wrapped in [data-panda-poke] (e.g. MakonRoom) reacts to pokes too
  const pandaOf = (svg) => pandas.find((p) => p.svg === svg);
  document.querySelectorAll('[data-panda-poke]').forEach((btn) => {
    const p = pandaOf(btn.querySelector('[data-panda]'));
    if (p) pokeable(p, btn, null);
  });
  window.MakonPanda = { of: pandaOf };

  // ------------------------------------------------------------------ corner companion
  const companion = document.querySelector('[data-mako-companion]');
  if (!companion) return;
  if (widget) { companion.hidden = true; return; } // Home already has the big Mako

  const svg = companion.querySelector('[data-panda]');
  const panda = pandas.find((p) => p.svg === svg);
  const bubble = companion.querySelector('[data-mako-bubble]');
  const text = companion.querySelector('[data-mako-text]');
  const pokeBtn = companion.querySelector('[data-mako-poke]');
  const tuckBtn = companion.querySelector('[data-mako-tuck]');
  const name = (companion.dataset.name || '').trim();
  const TUCK_KEY = 'mb-mako-tucked';
  let bubbleTimer = 0;

  function say(message, ms = 3600) {
    if (companion.classList.contains('is-tucked')) return;
    text.textContent = message;
    bubble.classList.add('is-open');
    panda.talk(Math.min(1600, 40 * message.length));
    clearTimeout(bubbleTimer);
    bubbleTimer = setTimeout(() => bubble.classList.remove('is-open'), ms);
  }

  function setTucked(on) {
    companion.classList.toggle('is-tucked', on);
    store.set('localStorage', TUCK_KEY, on ? '1' : '0');
    pokeBtn.setAttribute('aria-label', on ? 'Show Mako the panda' : 'Mako the panda. Press to say hi.');
    if (on) bubble.classList.remove('is-open');
  }

  tuckBtn.addEventListener('click', (e) => { e.stopPropagation(); panda.set('sad', 900); setTimeout(() => setTucked(true), 450); });
  pokeBtn.addEventListener('click', (e) => {
    if (!companion.classList.contains('is-tucked')) return;
    e.stopImmediatePropagation();
    setTucked(false);
    panda.set('greet', 2200);
    say(pick(LINES.welcomeBack), 2600);
  }, true);
  pokeable(panda, pokeBtn, say);

  if (store.get('localStorage', TUCK_KEY) === '1') companion.classList.add('is-tucked');

  // first page of the session: a proper hello
  if (!store.get('sessionStorage', 'mb-mako-greeted')) {
    store.set('sessionStorage', 'mb-mako-greeted', '1');
    setTimeout(() => {
      panda.set('greet', 3000);
      say(greeting(name, companion.dataset.holiday), 5200);
      if (companion.dataset.holiday) burstAt(svg, 24);
    }, 900);
    const seasonLine = SEASON_LINES[companion.dataset.season];
    if (seasonLine && Math.random() < .5) setTimeout(() => { panda.set('happy', 1600); say(seasonLine, 4200); }, 7200);
  } else {
    setTimeout(() => panda.set('happy', 1000), 600);
  }

  // away → bored → asleep; any input wakes him
  let lastInput = Date.now(), mood = 'awake';
  const wake = () => {
    lastInput = Date.now();
    if (mood === 'awake') return;
    const was = mood;
    mood = 'awake';
    panda.setBase('idle');
    panda.set('surprised', 900);
    setTimeout(() => { panda.set('happy', 1400); if (was === 'asleep') say(pick(LINES.wake), 2600); }, 950);
  };
  ['pointerdown', 'keydown', 'wheel', 'touchstart'].forEach((t) => window.addEventListener(t, wake, { passive: true }));
  window.addEventListener('pointermove', () => { if (mood !== 'awake') wake(); else lastInput = Date.now(); }, { passive: true });
  setInterval(() => {
    if (document.hidden) return;
    const idle = Date.now() - lastInput;
    if (mood === 'awake' && idle > 60000) { mood = 'bored'; panda.setBase('bored'); panda.set('bored'); if (Math.random() < .6) say(pick(LINES.bored), 3000); }
    else if (mood === 'bored' && idle > 180000) { mood = 'asleep'; panda.setBase('sleepy'); panda.set('sleepy'); say(pick(LINES.sleepy), 3000); }
  }, 5000);

  // back from another tab after a while
  let hiddenAt = 0;
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { hiddenAt = Date.now(); return; }
    if (hiddenAt && Date.now() - hiddenAt > 120000) { lastInput = Date.now(); mood = 'awake'; panda.setBase('idle'); panda.set('greet', 2200); say(pick(LINES.welcomeBack), 2800); }
  });

  // dark/light switch
  let theme = document.documentElement.dataset.theme;
  new MutationObserver(() => {
    const now = document.documentElement.dataset.theme;
    if (now && now !== theme) { theme = now; panda.set('surprised', 900); setTimeout(() => { panda.set('happy', 1300); say(pick(LINES[now === 'dark' ? 'dark' : 'light']), 2600); }, 900); }
  }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  // success / error toasts anywhere in the workspace
  new MutationObserver((records) => {
    records.forEach((r) => r.addedNodes.forEach((node) => {
      if (!(node instanceof HTMLElement)) return;
      const toast = node.matches('.v524-toast') ? node : node.querySelector?.('.v524-toast');
      if (!toast) return;
      if (toast.classList.contains('success')) { panda.set('happy', 1800); say(pick(LINES.success), 2400); }
      else if (toast.classList.contains('error')) { panda.set('worried', 2000); say(pick(LINES.error), 2800); }
    }));
  }).observe(document.body, { childList: true, subtree: true });
  // toasts rendered with the page itself
  const pageToast = document.querySelector('.v524-toast.success, .v524-toast.error');
  if (pageToast) setTimeout(() => { const ok = pageToast.classList.contains('success'); panda.set(ok ? 'happy' : 'worried', 2000); say(pick(LINES[ok ? 'success' : 'error']), 2600); }, 1400);

  window.addEventListener('offline', () => { panda.set('worried', 2600); say(pick(LINES.offline), 3200); });
  window.addEventListener('online', () => { panda.set('celebrate', 1900); say(pick(LINES.online), 2400); });

  window.MakonMako = {
    react(emotion, message, ms = 2600) { panda.set(emotion, ms); if (message) say(message, ms + 600); },
    emotions: ['idle', 'happy', 'greet', 'celebrate', 'surprised', 'sad', 'angry', 'skeptical', 'bored', 'sleepy', 'thinking', 'love', 'worried'],
  };
})();
