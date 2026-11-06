(function () {
  "use strict";

  var storageKey = "sat-makon-theme";
  var allowed = { system: true, light: true, dark: true };
  var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;

  function getSavedMode() {
    try {
      var saved = localStorage.getItem(storageKey);
      return allowed[saved] ? saved : "system";
    } catch (error) {
      return "system";
    }
  }

  function saveMode(mode) {
    try {
      if (mode === "system") localStorage.removeItem(storageKey);
      else localStorage.setItem(storageKey, mode);
    } catch (error) {}
  }

  function resolveMode(mode) {
    if (mode === "light" || mode === "dark") return mode;
    return media && media.matches ? "light" : "dark";
  }

  function iconFor(mode, resolved) {
    if (mode === "system") return resolved === "light" ? "◑" : "◐";
    return mode === "light" ? "☀" : "☾";
  }

  function currentLocale() {
    var code = (document.documentElement.getAttribute('lang') || 'en').toLowerCase().split('-')[0];
    return code === 'ru' || code === 'uz' ? code : 'en';
  }

  var localized = {
    en: {system:'System', light:'Light', dark:'Dark', device:'Device', subtitleSystem:'Follow device',
      subtitleLight:'Bright interface', subtitleDark:'Low-light interface', change:'Change color theme', options:'Theme options'},
    ru: {system:'Системная', light:'Светлая', dark:'Тёмная', device:'Устройство', subtitleSystem:'Как на устройстве',
      subtitleLight:'Светлый интерфейс', subtitleDark:'Тёмный интерфейс', change:'Изменить тему', options:'Выбор темы'},
    uz: {system:'Tizim', light:'Yorug‘', dark:'Qorong‘i', device:'Qurilma', subtitleSystem:'Qurilma sozlamasiga mos',
      subtitleLight:'Yorug‘ interfeys', subtitleDark:'Qorong‘i interfeys', change:'Ko‘rinishni tanlash', options:'Ko‘rinish rejimi'}
  };

  function labelFor(mode, resolved) {
    var t = localized[currentLocale()];
    return mode === 'system' ? t.system + ' · ' + t[resolved] : t[mode];
  }

  function localizeMenu(switcher) {
    var t = localized[currentLocale()];
    var menu = switcher.querySelector('[data-theme-menu]');
    if (menu) menu.setAttribute('aria-label', t.options);
    switcher.querySelectorAll('[data-theme-choice]').forEach(function (choice) {
      var key = choice.dataset.themeChoice;
      if (!allowed[key]) return;
      var strong = choice.querySelector('strong');
      var small = choice.querySelector('small');
      if (strong) strong.textContent = t[key];
      if (small && key !== 'system') small.textContent = t['subtitle' + key[0].toUpperCase() + key.slice(1)];
      if (small && key === 'system') small.textContent = t.subtitleSystem;
    });
  }

  function applyTheme(mode) {
    var resolved = resolveMode(mode);
    var root = document.documentElement;
    root.dataset.themeMode = mode;
    root.dataset.theme = resolved;
    root.style.colorScheme = resolved;

    document.querySelectorAll("[data-theme-switcher]").forEach(function (switcher) {
      var label = switcher.querySelector("[data-theme-label]");
      var icon = switcher.querySelector("[data-theme-icon]");
      var status = switcher.querySelector("[data-theme-system-status]");
      var toggle = switcher.querySelector("[data-theme-toggle]");
      if (label) label.textContent = labelFor(mode, resolved);
      if (icon) icon.textContent = iconFor(mode, resolved);
      localizeMenu(switcher);
      if (status) status.textContent = localized[currentLocale()].device + ' · ' + localized[currentLocale()][resolved];
      if (toggle) toggle.setAttribute('aria-label', labelFor(mode, resolved) + '. ' + localized[currentLocale()].change);

      switcher.querySelectorAll("[data-theme-choice]").forEach(function (choice) {
        choice.setAttribute("aria-checked", String(choice.dataset.themeChoice === mode));
      });
    });
  }

  function closeSwitcher(switcher, restoreFocus) {
    if (!switcher) return;
    switcher.classList.remove("is-open");
    var toggle = switcher.querySelector("[data-theme-toggle]");
    if (toggle) {
      toggle.setAttribute("aria-expanded", "false");
      if (restoreFocus) toggle.focus();
    }
  }

  function closeAll(except) {
    document.querySelectorAll("[data-theme-switcher].is-open").forEach(function (switcher) {
      if (switcher !== except) closeSwitcher(switcher, false);
    });
  }

  function focusChoice(switcher, index) {
    var choices = Array.prototype.slice.call(switcher.querySelectorAll("[data-theme-choice]"));
    if (!choices.length) return;
    index = (index + choices.length) % choices.length;
    choices[index].focus();
  }

  function setupSwitcher(switcher) {
    var toggle = switcher.querySelector("[data-theme-toggle]");
    var choices = Array.prototype.slice.call(switcher.querySelectorAll("[data-theme-choice]"));

    if (toggle) {
      toggle.addEventListener("click", function (event) {
        event.stopPropagation();
        var willOpen = !switcher.classList.contains("is-open");
        closeAll(switcher);
        switcher.classList.toggle("is-open", willOpen);
        toggle.setAttribute("aria-expanded", String(willOpen));
        if (willOpen) {
          var current = choices.findIndex(function (item) { return item.getAttribute("aria-checked") === "true"; });
          window.setTimeout(function () { focusChoice(switcher, current < 0 ? 0 : current); }, 20);
        }
      });
      toggle.addEventListener("keydown", function (event) {
        if (event.key === "ArrowDown") {
          event.preventDefault();
          if (!switcher.classList.contains("is-open")) toggle.click();
          else {
            var current = choices.findIndex(function (item) { return item.getAttribute("aria-checked") === "true"; });
            focusChoice(switcher, current < 0 ? 0 : current);
          }
        }
      });
    }

    choices.forEach(function (choice, index) {
      choice.addEventListener("click", function (event) {
        event.stopPropagation();
        var mode = choice.dataset.themeChoice;
        if (!allowed[mode]) return;
        closeSwitcher(switcher, true);
        var commit = function () { saveMode(mode); applyTheme(mode); };
        var animator = document.querySelector('.mb56-nav-wrap') && window.MakonBookLandingTransition;
        if (animator && mode !== getSavedMode()) {
          animator.run(commit).catch(function (error) {
            console.error('[MakonBook] Theme transition failed:', error);
            if (getSavedMode() !== mode) commit();
          });
        } else {
          commit();
        }
      });
      choice.addEventListener("keydown", function (event) {
        if (event.key === "ArrowDown") { event.preventDefault(); focusChoice(switcher, index + 1); }
        else if (event.key === "ArrowUp") { event.preventDefault(); focusChoice(switcher, index - 1); }
        else if (event.key === "Home") { event.preventDefault(); focusChoice(switcher, 0); }
        else if (event.key === "End") { event.preventDefault(); focusChoice(switcher, choices.length - 1); }
        else if (event.key === "Escape") { event.preventDefault(); closeSwitcher(switcher, true); }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-theme-switcher]").forEach(setupSwitcher);
    applyTheme(getSavedMode());
    // Landing language changes html.lang dynamically; reflect that immediately,
    // while keeping the selected light/dark/system mode unchanged.
    new MutationObserver(function (mutations) {
      if (mutations.some(function (mutation) {return mutation.attributeName === 'lang';})) {
        applyTheme(getSavedMode());
      }
    }).observe(document.documentElement, {attributes:true, attributeFilter:['lang']});
  });

  document.addEventListener("click", function () { closeAll(); });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") document.querySelectorAll("[data-theme-switcher].is-open").forEach(function (switcher) { closeSwitcher(switcher, true); });
  });

  if (media) {
    var onSystemThemeChange = function () {
      if (getSavedMode() === "system") applyTheme("system");
    };
    if (media.addEventListener) media.addEventListener("change", onSystemThemeChange);
    else if (media.addListener) media.addListener(onSystemThemeChange);
  }
})();
