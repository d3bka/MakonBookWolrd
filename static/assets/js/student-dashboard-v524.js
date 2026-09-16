(function () {
  'use strict';
  var home = document.querySelector('.v523-home');
  var layer = document.querySelector('[data-dashboard-customize-layer]');
  var grid = home && home.querySelector('.v523-home-grid');
  if (!home || !layer || !grid) return;
  var key = 'makonbook.dashboard.layout.v524';
  var builder = layer.querySelector('[data-dashboard-builder]');
  var openers = document.querySelectorAll('[data-dashboard-customize-open]');
  var closers = layer.querySelectorAll('[data-dashboard-customize-close]');
  var save = layer.querySelector('[data-dashboard-save]');
  var reset = layer.querySelector('[data-dashboard-reset]');

  function widgets() { return Array.prototype.slice.call(grid.querySelectorAll('[data-dashboard-widget]')); }
  function defaults() { return widgets().map(function (w) { return {key:w.dataset.dashboardWidget, hidden:w.dataset.dashboardDefaultHidden === '1'}; }); }
  function get() {
    try {
      var raw = JSON.parse(localStorage.getItem(key) || 'null');
      if (!Array.isArray(raw)) return defaults();
      var by = {}; defaults().forEach(function(x){by[x.key]=x;});
      var out = raw.filter(function(x){return x && by[x.key];}).map(function(x){return {key:x.key, hidden:!!x.hidden};});
      defaults().forEach(function(x){if(!out.some(function(y){return y.key===x.key;}))out.push(x);});
      return out;
    } catch(e) { return defaults(); }
  }
  function apply(rows) {
    var map={}; widgets().forEach(function(w){map[w.dataset.dashboardWidget]=w;});
    rows.forEach(function(r){var w=map[r.key];if(!w)return;grid.appendChild(w);w.hidden=!!r.hidden;w.classList.toggle('is-dashboard-hidden',!!r.hidden);});
  }
  function build() {
    builder.innerHTML='';
    get().forEach(function(r){
      var w=grid.querySelector('[data-dashboard-widget="'+r.key+'"]'); if(!w)return;
      var row=document.createElement('div'); row.className='v524-dashboard-builder-row'; row.draggable=true; row.dataset.key=r.key;
      row.innerHTML='<i class="bi bi-grip-vertical"></i><span><strong></strong><small>Drag inside this list to reorder</small></span><div><label class="v525-dashboard-visible"><input type="checkbox" '+(!r.hidden?'checked':'')+'><span>'+(r.hidden?'Hidden':'Visible')+'</span></label></div>';
      row.querySelector('strong').textContent=w.dataset.dashboardLabel||r.key;
      row.querySelector('input').addEventListener('change',function(e){row.querySelector('label span').textContent=e.target.checked?'Visible':'Hidden';});
      builder.appendChild(row);
    });
    var dragging=null;
    builder.querySelectorAll('.v524-dashboard-builder-row').forEach(function(row){
      row.addEventListener('dragstart',function(e){dragging=row;row.classList.add('is-dragging');if(e.dataTransfer){e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',row.dataset.key||'widget');}});
      row.addEventListener('dragend',function(){row.classList.remove('is-dragging');dragging=null;});
      row.addEventListener('dragover',function(e){if(!dragging||dragging===row||!builder.contains(row))return;e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect='move';var box=row.getBoundingClientRect();builder.insertBefore(dragging,e.clientY<box.top+box.height/2?row:row.nextSibling);});
    });
    builder.addEventListener('dragover',function(e){if(dragging){e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect='move';}});
    builder.addEventListener('drop',function(e){if(dragging)e.preventDefault();});
  }
  function toggle(open){layer.classList.toggle('is-open',open);layer.setAttribute('aria-hidden',open?'false':'true');document.documentElement.classList.toggle('mb50-modal-open',open);if(open){build();setTimeout(function(){var b=layer.querySelector('button');if(b)b.focus();},80);}}
  openers.forEach(function(b){b.addEventListener('click',function(){toggle(true);});});
  closers.forEach(function(b){b.addEventListener('click',function(){toggle(false);});});
  if(save) save.addEventListener('click',function(){var rows=Array.prototype.slice.call(builder.children).map(function(r){return {key:r.dataset.key,hidden:!r.querySelector('input').checked};});try{localStorage.setItem(key,JSON.stringify(rows));}catch(e){}apply(rows);toggle(false);});
  if(reset) reset.addEventListener('click',function(){try{localStorage.removeItem(key);}catch(e){}apply(defaults());build();});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&layer.classList.contains('is-open'))toggle(false);});
  apply(get());
})();
