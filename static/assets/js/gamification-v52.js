(function(){
  var layer=document.querySelector('[data-gamification-panel]');
  var openers=document.querySelectorAll('[data-gamification-open]');
  if(layer){
    var closers=layer.querySelectorAll('[data-gamification-close]');
    var lastFocus=null;
    function openPanel(){lastFocus=document.activeElement;layer.classList.add('is-open');layer.setAttribute('aria-hidden','false');document.documentElement.classList.add('mb52-panel-open');var close=layer.querySelector('[data-gamification-close]');if(close)close.focus();}
    function closePanel(){layer.classList.remove('is-open');layer.setAttribute('aria-hidden','true');document.documentElement.classList.remove('mb52-panel-open');if(lastFocus&&lastFocus.focus)lastFocus.focus();}
    openers.forEach(function(button){button.addEventListener('click',openPanel);});
    closers.forEach(function(button){button.addEventListener('click',closePanel);});
    document.addEventListener('keydown',function(event){if(event.key==='Escape'&&layer.classList.contains('is-open'))closePanel();});
  }

  // Small count-up is intentionally limited to progression numbers. It gives
  // feedback on load without turning the dashboard into a slot machine.
  if(window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  document.querySelectorAll('[data-gamification-count]').forEach(function(node){
    var target=parseInt(node.getAttribute('data-gamification-count')||'0',10);
    if(!Number.isFinite(target)||target<=0||target>99999)return;
    var duration=Math.min(650,260+target*4),start=null;
    node.textContent='0';
    function frame(now){if(start===null)start=now;var progress=Math.min(1,(now-start)/duration);var eased=1-Math.pow(1-progress,3);node.textContent=String(Math.round(target*eased));if(progress<1)requestAnimationFrame(frame);}
    requestAnimationFrame(frame);
  });
})();
