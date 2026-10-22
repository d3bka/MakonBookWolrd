(function(){
  'use strict';
  function parse(id){var n=document.getElementById(id);if(!n)return{};try{return JSON.parse(n.textContent||'{}')}catch(_e){return{}}}
  function csrf(){
    var n=document.querySelector('[name="csrfmiddlewaretoken"]');if(n&&n.value)return n.value;
    var m=document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);return m?decodeURIComponent(m[1]):'';
  }
  function monoNow(){return (window.performance&&typeof window.performance.now==='function')?window.performance.now():Date.now()}
  function uuid(){return (window.crypto&&window.crypto.randomUUID)?window.crypto.randomUUID():String(Date.now())+'-'+Math.random().toString(16).slice(2)}
  function fullscreenElement(){return document.fullscreenElement||document.webkitFullscreenElement||null}
  function requestFullscreen(){
    var el=document.documentElement,fn=el.requestFullscreen||el.webkitRequestFullscreen;
    return fn?Promise.resolve(fn.call(el)).catch(function(){return false}):Promise.resolve(false);
  }
  function exitFullscreen(){
    var fn=document.exitFullscreen||document.webkitExitFullscreen;
    return fn?Promise.resolve(fn.call(document)).catch(function(){return false}):Promise.resolve(false);
  }

  document.addEventListener('DOMContentLoaded',function(){
    var config=parse('sat-test-config');
    var core=window.SATTest;
    var mode=String(config.integrityMode||'off').toLowerCase();
    var max=Number(config.integrityMaxViolations||3);
    var strike=Number(config.integrityViolationCount||0);
    var violationUrl=config.integrityViolationUrl||'';
    var regular=config.testType==='regular'&&config.mode!=='guest';
    var monitoring=regular&&mode!=='off'&&violationUrl;
    var monitoredEvents=Array.isArray(config.integrityMonitoredEvents)?config.integrityMonitoredEvents:[];
    function monitors(name){return monitoredEvents.indexOf(name)>=0}
    var strict=mode==='strict';
    var fullscreenRequired=Boolean(config.integrityFullscreenRequired)&&monitoring;
    var armed=false,terminated=false,breakOpen=false,warningOpen=false,hadFullscreen=false;
    var suppressUntil=monoNow()+1800,lastEnvironmentAt=0,lastActivity=monoNow(),inactivityStrikeAt=0;
    var awayStartedAt=0,awayViolationRecorded=false;
    var inactivityLimit=strict?120000:180000;

    // Hide/show time.
    var timer=document.getElementById('timer');
    if(timer){
      var wrap=timer.parentElement;
      var tbtn=document.createElement('button');
      tbtn.type='button';tbtn.className='exam54-time-toggle';
      var pref=localStorage.getItem('makonbook:exam:timer-visible');
      var visible=pref!=='0';
      function paintTime(){
        document.body.classList.toggle('exam54-time-hidden',!visible);
        tbtn.classList.toggle('is-time-visible',visible);
        tbtn.classList.toggle('is-time-hidden',!visible);
        tbtn.innerHTML=visible
          ? '<i class="fa fa-eye-slash" aria-hidden="true"></i><span>Hide time</span>'
          : '<i class="fa fa-eye" aria-hidden="true"></i><span>Show time</span>';
        tbtn.setAttribute('aria-pressed',String(!visible));
        tbtn.setAttribute('aria-label',visible?'Hide the timer':'Show the timer');
      }
      tbtn.addEventListener('click',function(){
        if (tbtn.disabled) return;
        visible=!visible;
        try{localStorage.setItem('makonbook:exam:timer-visible',visible?'1':'0')}catch(_e){}
        paintTime();
      });
      wrap.appendChild(tbtn);paintTime();

      window.addEventListener('sat:five-minute-warning', function(){
        visible=true;
        try{localStorage.setItem('makonbook:exam:timer-visible','1')}catch(_e){}
        paintTime();
        tbtn.disabled=true;
        tbtn.classList.add('is-five-minute-locked');
        tbtn.innerHTML='<i class="fa fa-clock-o" aria-hidden="true"></i><span>Visible</span>';
        tbtn.setAttribute('aria-label','Timer stays visible for the final five minutes');

        if (!document.querySelector('[data-five-minute-alert]')) {
          var notice=document.createElement('div');
          notice.className='exam54-five-minute-alert';
          notice.setAttribute('data-five-minute-alert','');
          notice.innerHTML='<div class="exam54-five-minute-alert-card"><span class="exam54-five-minute-kicker">5 minutes remaining</span><strong>The timer will stay visible.</strong><p>Review your unanswered or marked questions before this module ends.</p><button type="button">Continue</button></div>';
          document.body.appendChild(notice);
          notice.querySelector('button').addEventListener('click',function(){notice.remove()});
        }
      }, {once:true});
    }

    // Header tools: unscheduled break. Reuse the native section toolbar instead
    // of positioning a second toolbar over Math/Reading controls.
    var header=document.querySelector('header');
    if(header){
      var tools=header.querySelector('.header-tools');
      var exitLink=header.querySelector('[data-test-exit]');
      if(!tools){
        tools=document.createElement('div');
        tools.className='header-tools exam54-generated-tools';
        if(exitLink && exitLink.parentNode===header){
          header.insertBefore(tools,exitLink);
          tools.appendChild(exitLink);
        }else{
          header.appendChild(tools);
        }
      }

      var breakBtn=document.createElement('button');
      breakBtn.type='button';
      breakBtn.className='header-tool exam54-break-tool';
      breakBtn.title='Take an unscheduled break';
      breakBtn.setAttribute('aria-label','Take an unscheduled break');
      breakBtn.innerHTML='<i class="fa fa-pause" aria-hidden="true"></i>';

      var toolbarExit=tools.querySelector('[data-test-exit]');
      if(toolbarExit) tools.insertBefore(breakBtn,toolbarExit);
      else tools.appendChild(breakBtn);

      breakBtn.addEventListener('click',function(){
        if(terminated||breakOpen)return;breakOpen=true;
        var o=document.createElement('div');o.className='exam54-overlay exam54-break-screen';
        o.innerHTML='<section class="exam54-card"><span class="kicker">Unscheduled break</span><h2>Your test timer keeps running</h2><p>You may step away briefly, but no extra time is added. Return to this screen and select Resume test when you are ready.</p><div class="break-clock">Timer continues</div><div class="actions"><button class="exam54-btn primary" type="button">Resume test</button></div></section>';
        document.body.appendChild(o);o.querySelector('button').addEventListener('click',function(){breakOpen=false;o.remove();lastActivity=monoNow()});
      });
    }

    // Warning UI.
    var toast=document.createElement('div');toast.className='exam54-strike-toast';document.body.appendChild(toast);
    function showStrike1(message){
      toast.innerHTML='<strong>⚠ Warning 1/'+max+'</strong><span>'+message+'</span>';toast.classList.add('is-visible');setTimeout(function(){toast.classList.remove('is-visible')},6500);
    }
    function showStrikeWarning(message,currentStrike){
      warningOpen=true;var o=document.createElement('div');o.className='exam54-overlay';
      var remaining=Math.max(max-currentStrike,0);
      o.innerHTML='<section class="exam54-card"><span class="kicker">Exam integrity warning '+currentStrike+'/'+max+'</span><h2>Another violation was detected</h2><p>'+message+(remaining===1?' One more violation may automatically end this attempt.':' Repeated violations may automatically end this attempt.')+'</p><div class="actions"><button class="exam54-btn primary" type="button">Continue test</button></div></section>';
      document.body.appendChild(o);o.querySelector('button').addEventListener('click',async function(){if(fullscreenRequired&&!fullscreenElement())await requestFullscreen();suppressUntil=monoNow()+1500;warningOpen=false;o.remove();lastActivity=monoNow()});
    }
    function showTermination(resultsUrl){
      terminated=true;armed=false;
      var o=document.createElement('div');o.className='exam54-overlay exam54-termination';
      o.innerHTML='<section class="exam54-card exam54-termination"><span class="kicker">Test terminated</span><h2>Maximum integrity violations reached</h2><p>Your latest server-saved answers were frozen and the remaining questions were submitted unanswered. This attempt can no longer continue.</p><div class="actions">'+(resultsUrl?'<a class="exam54-btn primary" href="'+resultsUrl+'">View results</a>':'')+'</div></section>';
      document.body.appendChild(o);
      var resultsLink=o.querySelector('a');
      if(resultsLink)resultsLink.addEventListener('click',function(){if(window.SATTest)window.SATTest.navigatingAway=true});
    }

    async function record(eventType,message,detail){
      if(!monitoring||!armed||terminated||breakOpen||warningOpen||monoNow()<suppressUntil)return false;
      if(window.SATTest&&window.SATTest.navigatingAway)return false;
      var environment=['tab_hidden','window_blur','fullscreen_exit'];
      if(environment.indexOf(eventType)>=0){
        if(monoNow()-lastEnvironmentAt<1400)return false;
        lastEnvironmentAt=monoNow();
      }
      // Do not keep a stale reference captured before test-eng/test-math creates
      // SATTest. The old code skipped this autosave on every integrity event.
      var activeCore=window.SATTest||core;
      try{if(activeCore&&typeof activeCore.autosave==='function')await activeCore.autosave(true)}catch(_e){}
      var payload={event_id:uuid(),attempt_id:config.attemptId,event_type:eventType,client_occurred_at:new Date().toISOString(),detail:detail||{}};
      try{
        var r=await fetch(violationUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf(),'X-Requested-With':'XMLHttpRequest'},body:JSON.stringify(payload),credentials:'same-origin',keepalive:true});
        var data=await r.json().catch(function(){return{}});
        if(!r.ok||!data.ok||data.ignored)return false;
        var serverStrike=Number(data.strike||strike);
        // Concurrent browser events can return out of order. Never regress the
        // local strike counter/UI from warning 2 back to warning 1.
        if(serverStrike<strike)return true;
        strike=serverStrike;
        if(data.terminated){showTermination(data.results_url||'');return true}
        if(strike===1){
          showStrike1(message);
          if(secureGate){
            var gateCopy=secureGate.querySelector('[data-exam54-gate-copy]');
            if(gateCopy)gateCopy.textContent='Warning 1/'+max+': '+message+' Re-enter fullscreen to continue.';
          }
        }
        else if(strike>=2)showStrikeWarning(message,strike);
        return true;
      }catch(_e){return false}
    }

    // Secure fullscreen gate.
    function arm(){
      if(armed)return;armed=true;lastActivity=monoNow();suppressUntil=monoNow()+1400;
    }
    var secureGate=null;
    function ensureFullscreenGate(){
      if(!fullscreenRequired)return null;
      if(fullscreenElement())return null;
      if(secureGate&&document.body.contains(secureGate))return secureGate;
      var gate=document.createElement('div');gate.className='exam54-overlay exam54-secure-gate';
      gate.innerHTML='<section class="exam54-card"><span class="kicker">Secure exam mode</span><h2>Enter fullscreen to continue</h2><p data-exam54-gate-copy>Do not switch tabs, minimize the browser, open another application or leave fullscreen. You have up to '+max+' integrity violations before automatic submission.</p><div class="actions"><button class="exam54-btn primary" type="button">Enter fullscreen & continue</button></div></section>';
      document.body.appendChild(gate);
      secureGate=gate;
      gate.querySelector('button').addEventListener('click',async function(){
        await requestFullscreen();
        window.setTimeout(function(){
          hadFullscreen=Boolean(fullscreenElement());
          if(hadFullscreen){
            gate.remove();
            secureGate=null;
            suppressUntil=monoNow()+900;
            arm();
            return;
          }
          var copy=gate.querySelector('[data-exam54-gate-copy]');
          if(copy)copy.textContent='Fullscreen was not enabled. Please allow fullscreen in the browser and try again.';
        },120);
      });
      return gate;
    }
    if(fullscreenRequired&&(document.fullscreenEnabled||document.webkitFullscreenEnabled)&&!fullscreenElement()){
      ensureFullscreenGate();
    }else{hadFullscreen=Boolean(fullscreenElement());arm()}

    document.addEventListener('fullscreenchange',function(){if(fullscreenElement()){hadFullscreen=true;suppressUntil=monoNow()+800;if(secureGate){secureGate.remove();secureGate=null;}arm()}else if(fullscreenRequired&&monitors('fullscreen_exit')&&(hadFullscreen||armed)){ensureFullscreenGate();record('fullscreen_exit','Fullscreen mode was exited.')}});
    document.addEventListener('webkitfullscreenchange',function(){if(fullscreenElement()){hadFullscreen=true;suppressUntil=monoNow()+800;if(secureGate){secureGate.remove();secureGate=null;}arm()}else if(fullscreenRequired&&monitors('fullscreen_exit')&&(hadFullscreen||armed)){ensureFullscreenGate();record('fullscreen_exit','Fullscreen mode was exited.')}});

    function markAway(){
      if(!awayStartedAt){awayStartedAt=monoNow();awayViolationRecorded=false;}
    }
    function markAwayViolation(promise){
      Promise.resolve(promise).then(function(recorded){if(recorded)awayViolationRecorded=true}).catch(function(){});
    }
    function handleReturnFromAway(source){
      if(!awayStartedAt)return;
      var awayMs=monoNow()-awayStartedAt;
      awayStartedAt=0;
      lastActivity=monoNow();
      // One continuous leave should be one strike. Previously a long tab/app
      // switch caused an immediate tab/blur strike and then a second inactivity
      // strike on return for the same incident.
      if(!awayViolationRecorded&&monitors('inactivity')&&awayMs>=inactivityLimit){
        inactivityStrikeAt=monoNow();
        var mins=Math.max(1,Math.round(awayMs/60000));
        record('inactivity','You were away from the active test for about '+mins+' minute'+(mins===1?'':'s')+'.',{source:source||'background',away_ms:awayMs});
      }
      awayViolationRecorded=false;
    }

    document.addEventListener('visibilitychange',function(){
      if(document.hidden){
        markAway();
        if(monitors('tab_hidden')){if(fullscreenRequired&&!fullscreenElement())ensureFullscreenGate();markAwayViolation(record('tab_hidden','You left the active test tab.'));}
      }else{
        handleReturnFromAway('visibility');
      }
    });
    window.addEventListener('blur',function(){
      markAway();
      setTimeout(function(){if(monitors('window_blur')&&!document.hasFocus()&&!document.hidden){if(fullscreenRequired&&!fullscreenElement())ensureFullscreenGate();markAwayViolation(record('window_blur','The exam window lost focus.'));}},260)
    });
    window.addEventListener('focus',function(){window.setTimeout(function(){handleReturnFromAway('focus')},80)});
    window.addEventListener('pagehide',function(){
      markAway();
      // Strict mode already records leave_attempt in beforeunload. Do not create
      // a second tab_hidden strike for the same refresh/navigation.
      if(monitors('tab_hidden')&&!monitors('leave_attempt'))markAwayViolation(record('tab_hidden','The exam page was hidden or unloaded.'));
    });

    ['pointerdown','pointermove','keydown','input','scroll','touchstart'].forEach(function(name){document.addEventListener(name,function(){lastActivity=monoNow()},{passive:true,capture:true})});
    setInterval(function(){
      if(!armed||terminated||breakOpen)return;
      if(monitors('inactivity')&&monoNow()-lastActivity>=inactivityLimit&&monoNow()-inactivityStrikeAt>=inactivityLimit){
        inactivityStrikeAt=monoNow();lastActivity=monoNow();record('inactivity','Extended inactivity was detected.');
      }
    },10000);

    if(strict){
      document.addEventListener('copy',function(e){if(!monitors('copy'))return;e.preventDefault();record('copy','Copying test content is restricted.')},true);
      document.addEventListener('paste',function(e){if(!monitors('paste'))return;e.preventDefault();record('paste','Pasting is restricted during this exam.')},true);
      document.addEventListener('contextmenu',function(e){if(!monitors('contextmenu'))return;e.preventDefault();record('contextmenu','Right-click is restricted during this exam.')},true);
      document.addEventListener('keydown',function(e){
        var k=String(e.key||'').toLowerCase(),mod=e.ctrlKey||e.metaKey;
        var restricted=mod&&['c','v','x','p','s','l','t','n'].includes(k);
        if(restricted&&monitors('restricted_shortcut')){e.preventDefault();record('restricted_shortcut','A restricted browser shortcut was used.',{key:k})}
      },true);
      window.addEventListener('beforeunload',function(){
        if(!monitors('leave_attempt'))return;
        if(window.SATTest&&window.SATTest.navigatingAway)return;
        // If visibility/fullscreen already produced an environment strike for
        // this same navigation, do not count the unload as a second violation.
        if(monoNow()-lastEnvironmentAt<1400)return;
        try{
          fetch(violationUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify({event_id:uuid(),attempt_id:config.attemptId,event_type:'leave_attempt',client_occurred_at:new Date().toISOString(),detail:{source:'beforeunload'}}),credentials:'same-origin',keepalive:true});
        }catch(_e){}
      });
    }
  });
})();