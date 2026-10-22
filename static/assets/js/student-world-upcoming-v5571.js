(function(){
  'use strict';
  var shell=document.querySelector('[data-student-workspace]');
  var alertBox=document.querySelector('[data-world-upcoming-alert]');
  if(!shell||!alertBox)return;
  var timer=null;
  function hide(){
    clearTimeout(timer);
    if(!alertBox.classList.contains('is-visible'))return;
    alertBox.classList.add('is-leaving');
    alertBox.classList.remove('is-visible');
    alertBox.setAttribute('aria-hidden','true');
    setTimeout(function(){alertBox.classList.remove('is-leaving');},320);
  }
  function show(){
    clearTimeout(timer);
    alertBox.classList.remove('is-leaving');
    alertBox.setAttribute('aria-hidden','false');
    // Restart the drop animation even on repeated clicks.
    alertBox.classList.remove('is-visible');
    void alertBox.offsetWidth;
    alertBox.classList.add('is-visible');
    timer=setTimeout(hide,4800);
  }
  shell.querySelectorAll('[data-world-upcoming]').forEach(function(link){
    link.addEventListener('click',function(event){
      event.preventDefault();
      show();
    });
  });
  var close=alertBox.querySelector('[data-world-upcoming-close]');
  if(close)close.addEventListener('click',hide);
  document.addEventListener('keydown',function(event){if(event.key==='Escape')hide();});
})();
