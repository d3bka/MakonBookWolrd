(function(){
  'use strict';
  document.addEventListener('DOMContentLoaded',function(){
    var picker=document.querySelector('[data-test-mode-picker]');
    if(!picker)return;
    var selected=picker.dataset.selectedMode||'full_test';
    var subBox=picker.querySelector('[data-single-module-options]');
    var toggle=picker.querySelector('[data-single-module-toggle]');
    var qNode=document.querySelector('[data-test-mode-question-count]');
    var dNode=document.querySelector('[data-test-mode-duration]');

    function allModeButtons(){return Array.from(picker.querySelectorAll('[data-test-mode]'))}
    function syncStartTargets(){
      document.querySelectorAll('[data-start-test-link]').forEach(function(link){
        if(link.tagName==='A'&&link.href){
          try{var url=new URL(link.href,window.location.href);url.searchParams.set('test_mode',selected);link.href=url.toString()}catch(_e){}
        }
      });
    }
    function choose(button){
      if(!button)return;
      selected=button.dataset.testMode||'full_test';
      picker.dataset.selectedMode=selected;
      picker.querySelectorAll('.sat5411-mode-card,[data-single-module-options] button').forEach(function(n){n.classList.remove('is-selected')});
      button.classList.add('is-selected');
      if(selected.indexOf('single_')===0 && toggle)toggle.classList.add('is-selected');
      if(qNode)qNode.textContent=button.dataset.questionCount||qNode.textContent;
      if(dNode)dNode.textContent=(button.dataset.duration||'0')+' min';
      syncStartTargets();
      try{localStorage.setItem('makonbook:test-mode',selected)}catch(_e){}
    }

    allModeButtons().forEach(function(button){button.addEventListener('click',function(){choose(button)})});
    document.querySelectorAll('a[data-start-test-link]').forEach(function(link){
      link.addEventListener('click',function(){syncStartTargets()},{capture:true});
    });
    if(toggle)toggle.addEventListener('click',function(){if(subBox)subBox.hidden=!subBox.hidden});

    try{
      var saved=localStorage.getItem('makonbook:test-mode');
      var candidate=saved&&picker.querySelector('[data-test-mode="'+saved+'"]');
      if(candidate)choose(candidate);else choose(picker.querySelector('[data-test-mode="'+selected+'"]')||allModeButtons()[0]);
    }catch(_e){choose(picker.querySelector('[data-test-mode="'+selected+'"]')||allModeButtons()[0])}
  });
})();
