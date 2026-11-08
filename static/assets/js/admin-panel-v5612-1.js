(function(){
  var shell=document.querySelector('[data-admin-shell]');
  if(!shell)return;
  var open=document.querySelector('[data-admin-menu-open]');
  var close=document.querySelector('[data-admin-menu-close]');
  function setOpen(value){shell.classList.toggle('is-menu-open',!!value);if(open)open.setAttribute('aria-expanded',value?'true':'false');}
  if(open)open.addEventListener('click',function(){setOpen(!shell.classList.contains('is-menu-open'));});
  if(close)close.addEventListener('click',function(){setOpen(false);});
  shell.querySelectorAll('.mb-admin-nav a').forEach(function(link){link.addEventListener('click',function(){if(window.innerWidth<=860)setOpen(false);});});
})();
