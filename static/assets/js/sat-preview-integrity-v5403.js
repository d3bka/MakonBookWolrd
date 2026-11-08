(function(){
  'use strict';

  document.addEventListener('DOMContentLoaded', function(){
    var picker = document.querySelector('[data-integrity-picker]');
    if (!picker) return;

    var locked = picker.dataset.locked === 'true';
    var max = picker.dataset.maxViolations || '3';
    var defaultFullscreen = picker.dataset.fullscreenRequired === 'true';
    var note = picker.querySelector('[data-integrity-note-text]');
    var storageKey = 'makonbook:practice-integrity-mode';

    function selectedInput(){
      return picker.querySelector('input[name="preview_integrity_mode"]:checked');
    }

    function selectedMode(){
      var checked = selectedInput();
      return checked ? checked.value : 'standard';
    }

    function fullscreenFor(mode){
      if (mode === 'off') return false;
      return defaultFullscreen !== false;
    }

    function setMode(mode){
      if (locked) return;
      var input = picker.querySelector('input[name="preview_integrity_mode"][value="' + mode + '"]');
      if (input) input.checked = true;
    }

    function repaint(){
      var mode = selectedMode();
      var fullscreen = fullscreenFor(mode);

      picker.querySelectorAll('.sat54-integrity-option').forEach(function(label){
        var input = label.querySelector('input');
        label.classList.toggle('is-selected', !!input && input.checked);
      });

      if (note) {
        if (mode === 'off') {
          note.textContent = 'Anti-Cheat is off. No strikes, fullscreen requirement, tab/app monitoring or copy restrictions will be applied.';
        } else if (mode === 'strict') {
          note.textContent = 'Strict mode uses up to ' + max + ' strikes, requires fullscreen, and adds copy/paste, right-click, shortcut and page-leave protection.';
        } else {
          note.textContent = 'Standard mode uses up to ' + max + ' strikes and monitors tab/app switching, inactivity and fullscreen exit.';
        }
      }

      document.querySelectorAll('[data-integrity-hidden-mode]').forEach(function(n){ n.value = mode; });
      document.querySelectorAll('[data-integrity-hidden-max]').forEach(function(n){ n.value = max; });
      document.querySelectorAll('[data-integrity-hidden-fullscreen]').forEach(function(n){ n.value = fullscreen ? '1' : '0'; });

      if (!locked) {
        try { localStorage.setItem(storageKey, mode); } catch (_error) {}
      }
    }

    // Independent practice remembers the student's last choice.
    if (!locked) {
      try {
        var saved = localStorage.getItem(storageKey);
        if (saved === 'off' || saved === 'standard' || saved === 'strict') {
          setMode(saved);
        }
      } catch (_error) {}
    }

    picker.querySelectorAll('input[name="preview_integrity_mode"]').forEach(function(input){
      input.addEventListener('change', repaint);
    });

    repaint();

    // GET start links receive the selected policy before navigation.
    if (!locked) {
      document.querySelectorAll('a[data-start-test-link]').forEach(function(link){
        link.addEventListener('click', function(){
          if (!link.href) return;
          var mode = selectedMode();
          var fullscreen = fullscreenFor(mode);
          try {
            var url = new URL(link.href, window.location.href);
            url.searchParams.set('integrity_mode', mode);
            url.searchParams.set('integrity_max_violations', max);
            url.searchParams.set('integrity_fullscreen_required', fullscreen ? '1' : '0');
            link.href = url.toString();
          } catch (_error) {}
        }, {capture:true});
      });
    }
  });
})();