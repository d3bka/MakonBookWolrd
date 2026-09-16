(function(){
  'use strict';
  function debounce(fn,wait){var t;return function(){clearTimeout(t);t=setTimeout(fn,wait);};}
  document.querySelectorAll('[data-v50210-live-form]').forEach(function(form){var go=debounce(function(){form.requestSubmit?form.requestSubmit():form.submit();},280);form.querySelectorAll('input[type=search],select').forEach(function(el){el.addEventListener(el.tagName==='SELECT'?'change':'input',go);});});
})();
