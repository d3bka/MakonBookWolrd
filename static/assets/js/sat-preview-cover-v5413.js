
(function(){
  'use strict';
  document.addEventListener('DOMContentLoaded', function(){
    var shell = document.querySelector('[data-start-setup]');
    if(!shell) return;

    var toggle = shell.querySelector('[data-start-setup-toggle]');
    var panel = shell.querySelector('.sat5413-setup-panel');
    var modeLabel = shell.querySelector('[data-selected-test-mode-label]');
    var integrityLabel = shell.querySelector('[data-selected-integrity-label]');

    function updateModeLabel(){
      if(!modeLabel) return;
      var selected = document.querySelector('[data-test-mode-picker] .sat5411-mode-card.is-selected,[data-test-mode-picker] .sat5411-submodes button.is-selected');
      if(!selected){ modeLabel.textContent = 'Full Test'; return; }
      var strong = selected.querySelector('strong');
      modeLabel.textContent = strong ? strong.textContent.trim() : 'Full Test';
    }

    function updateIntegrityLabel(){
      if(!integrityLabel) return;
      var checked = document.querySelector('input[name="preview_integrity_mode"]:checked');
      var map = {off:'Anti-Cheat: Off', standard:'Anti-Cheat: Standard', strict:'Anti-Cheat: Strict'};
      integrityLabel.textContent = map[(checked && checked.value) || 'standard'] || 'Anti-Cheat: Standard';
    }

    function sync(){ updateModeLabel(); updateIntegrityLabel(); }

    if(toggle && panel){
      toggle.addEventListener('click', function(){
        var open = panel.hasAttribute('hidden');
        if(open) panel.removeAttribute('hidden'); else panel.setAttribute('hidden', 'hidden');
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        toggle.textContent = open ? 'Hide setup' : 'Change setup';
      });
    }

    document.addEventListener('click', function(e){
      if(e.target.closest('[data-test-mode]') || e.target.closest('.sat54-integrity-option')){
        setTimeout(sync, 0);
      }
    });
    document.querySelectorAll('input[name="preview_integrity_mode"]').forEach(function(input){
      input.addEventListener('change', sync);
    });
    sync();
  });
})();
