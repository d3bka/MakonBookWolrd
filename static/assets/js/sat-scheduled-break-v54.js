(function(){
  'use strict';
  document.addEventListener('DOMContentLoaded',function(){
    var body=document.body;
    var total=Math.max(Number(body.dataset.breakSeconds||0),0);
    var monoNow=function(){return (window.performance&&typeof window.performance.now==='function')?window.performance.now():Date.now()};
    var endMono=monoNow()+(total*1000);
    var remaining=total;
    var clock=document.querySelector('[data-break-clock]');
    var track=document.querySelector('[data-break-track]');
    var btn=document.querySelector('[data-break-continue]');
    var skipBtn=document.querySelector('[data-break-skip]');
    var url=body.dataset.continueUrl||window.location.href;
    var skipUrl=body.dataset.skipBreakUrl||'';
    var cover=document.createElement('div');
    cover.className='sat54-break-privacy-cover';
    cover.innerHTML='<div><strong>Break page hidden</strong><span>Return to this tab to continue the scheduled break.</span></div>';
    document.body.appendChild(cover);

    function showCover(){cover.classList.add('is-visible');}
    function hideCover(){cover.classList.remove('is-visible');}

    function fmt(v){
      v=Math.max(Math.ceil(v),0);
      return Math.floor(v/60)+':'+String(v%60).padStart(2,'0');
    }

    function paint(){
      // Derive remaining time from a monotonic deadline instead of subtracting
      // one second per interval tick. Hidden/background tabs throttle timers and
      // previously made students wait longer than the real scheduled break.
      remaining=Math.max(Math.ceil((endMono-monoNow())/1000),0);
      if(clock) clock.textContent=fmt(remaining);
      if(track) track.style.width=(total?Math.max(0,remaining/total*100):0)+'%';
      if(btn && remaining<=0){
        btn.disabled=false;
        clearInterval(timer);
      }
    }

    function go(target){
      if(!target) return;
      window.location.assign(target);
    }

    paint();
    var timer=setInterval(paint,500);
    if(btn) btn.addEventListener('click',function(){go(url)});
    if(skipBtn) skipBtn.addEventListener('click',function(){go(skipUrl||url)});

    document.addEventListener('visibilitychange',function(){if(document.hidden)showCover();else hideCover();});
    window.addEventListener('blur',showCover);
    window.addEventListener('focus',hideCover);
  });
})();
