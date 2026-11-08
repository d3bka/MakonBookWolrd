(function(){
  'use strict';
  document.addEventListener('DOMContentLoaded', function(){
    var picker=document.querySelector('[data-integrity-picker]');
    if(!picker)return;
    var locked=picker.dataset.locked==='true';
    var max=picker.dataset.maxViolations||'3';
    var fullscreen=picker.dataset.fullscreenRequired==='true';

    function selectedMode(){
      var checked=picker.querySelector('input[name="preview_integrity_mode"]:checked');
      return checked?checked.value:'standard';
    }
    function repaint(){
      picker.querySelectorAll('.sat54-integrity-option').forEach(function(label){
        var input=label.querySelector('input');
        label.classList.toggle('is-selected',!!input&&input.checked);
      });
      var mode=selectedMode();
      fullscreen=mode!=='off';
      document.querySelectorAll('[data-integrity-hidden-mode]').forEach(function(n){n.value=mode});
      document.querySelectorAll('[data-integrity-hidden-max]').forEach(function(n){n.value=max});
      document.querySelectorAll('[data-integrity-hidden-fullscreen]').forEach(function(n){n.value=fullscreen?'1':'0'});
    }
    picker.querySelectorAll('input[name="preview_integrity_mode"]').forEach(function(input){
      input.addEventListener('change',repaint);
    });
    repaint();

    if(!locked){
      document.querySelectorAll('a[data-start-test-link]').forEach(function(link){
        link.addEventListener('click',function(event){
          if(!link.href)return;
          try{
            var url=new URL(link.href,window.location.href);
            url.searchParams.set('integrity_mode',selectedMode());
            url.searchParams.set('integrity_max_violations',max);
            url.searchParams.set('integrity_fullscreen_required',fullscreen?'1':'0');
            link.href=url.toString();
          }catch(_error){}
        },{capture:true});
      });
    }
  });
})();