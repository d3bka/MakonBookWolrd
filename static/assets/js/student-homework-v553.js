(function(){
  'use strict';
  var nodes=Array.from(document.querySelectorAll('[data-v553-deadline]'));
  if(!nodes.length)return;
  function pad(n){return String(Math.max(0,n)).padStart(2,'0');}
  function render(){
    var now=Date.now();
    nodes.forEach(function(node){
      var due=Number(node.getAttribute('data-v553-deadline')||0),out=node.querySelector('[data-v553-countdown]');
      if(!due||!out)return;
      var diff=due-now;
      if(diff<=0){out.textContent='Closed';node.classList.add('is-expired');node.setAttribute('data-urgency','critical');return;}
      var total=Math.floor(diff/1000),days=Math.floor(total/86400);total%=86400;
      var hours=Math.floor(total/3600);total%=3600;var mins=Math.floor(total/60),secs=total%60;
      out.textContent=(days?days+'d ':'')+pad(hours)+'h '+pad(mins)+'m '+pad(secs)+'s';
      node.setAttribute('data-urgency',diff<=3600000?'critical':(diff<=86400000?'soon':'normal'));
    });
  }
  render();window.setInterval(render,1000);
})();
