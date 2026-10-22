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

  function labelFor(mode, resolved) {
    if (mode === "light") return "Light";
    if (mode === "dark") return "Dark";
    return "System · " + (resolved === "light" ? "Light" : "Dark");
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
      if (status) status.textContent = "Device · " + (resolved === "light" ? "Light" : "Dark");
      if (toggle) toggle.setAttribute("aria-label", "Theme: " + labelFor(mode, resolved) + ". Change color theme");

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
        saveMode(mode);
        applyTheme(mode);
        closeSwitcher(switcher, true);
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
