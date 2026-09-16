(function(){
  'use strict';
  document.querySelectorAll('[data-sf28-modal-open]').forEach(function(btn){btn.addEventListener('click',function(){var id=btn.getAttribute('data-sf28-modal-open');var layer=document.querySelector('[data-sf28-modal="'+id+'"]');if(layer){layer.classList.add('is-open');layer.setAttribute('aria-hidden','false');var first=layer.querySelector('select,input,textarea,button');if(first)setTimeout(function(){first.focus();},120);}});});
  function close(layer){if(!layer)return;layer.classList.remove('is-open');layer.setAttribute('aria-hidden','true');}
  document.querySelectorAll('[data-sf28-modal-close]').forEach(function(btn){btn.addEventListener('click',function(){close(btn.closest('[data-sf28-modal]'));});});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')document.querySelectorAll('[data-sf28-modal].is-open').forEach(close);});
  document.querySelectorAll('[data-sf28-assignment-type]').forEach(function(select){var sync=function(){var root=select.closest('form');if(!root)return;root.querySelectorAll('[data-sf28-type-field]').forEach(function(el){var types=(el.getAttribute('data-sf28-type-field')||'').split(',');el.hidden=types.indexOf(select.value)<0;el.querySelectorAll('select,input,textarea').forEach(function(field){field.disabled=el.hidden;});});};select.addEventListener('change',sync);sync();});
  document.querySelectorAll('[data-v524-toast]').forEach(function(toast){var btn=toast.querySelector('[data-v524-toast-close]');var dismiss=function(){toast.classList.add('is-leaving');setTimeout(function(){toast.remove();},220);};if(btn)btn.addEventListener('click',dismiss);setTimeout(dismiss,5200);});
})();
