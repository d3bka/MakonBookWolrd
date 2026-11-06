(function () {
  'use strict';
  var home = document.querySelector('.v523-home');
  var layer = document.querySelector('[data-dashboard-customize-layer]');
  var grid = home && home.querySelector('.v523-home-grid');
  if (!home || !layer || !grid) return;
  var key = home.classList.contains('mb66-dashboard') ? 'makonbook.dashboard.layout.v66' : 'makonbook.dashboard.layout.v524';
  // The editor must sit outside the workspace so the entire shell (including
  // the sidebar) can blur without blurring the dialog itself.
  document.body.appendChild(layer);
  var builder = layer.querySelector('[data-dashboard-builder]');
  var dialog = layer.querySelector('[role="dialog"]');
  var returnFocus = null;
  var previousBodyOverflow = '';

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
  function syncMoveButtons(){
    var rows=Array.prototype.slice.call(builder.querySelectorAll('.v524-dashboard-builder-row'));
    rows.forEach(function(row,index){
      row.querySelector('[data-widget-up]').disabled=index===0;
      row.querySelector('[data-widget-down]').disabled=index===rows.length-1;
    });
  }
  function build() {
    builder.innerHTML='';
    get().forEach(function(r){
      var w=grid.querySelector('[data-dashboard-widget="'+r.key+'"]'); if(!w)return;
      var row=document.createElement('div'); row.className='v524-dashboard-builder-row'; row.draggable=true; row.dataset.key=r.key;
      row.innerHTML='<i class="bi bi-grip-vertical" aria-hidden="true"></i><span><strong></strong><small>Drag to reorder, or use the arrows</small></span><div class="mb661-row-controls"><button type="button" data-widget-up aria-label="Move widget up" title="Move up"><i class="bi bi-arrow-up"></i></button><button type="button" data-widget-down aria-label="Move widget down" title="Move down"><i class="bi bi-arrow-down"></i></button><label class="v525-dashboard-visible"><input type="checkbox" '+(!r.hidden?'checked':'')+'><span>'+(r.hidden?'Hidden':'Visible')+'</span></label></div>';
      row.querySelector('strong').textContent=w.dataset.dashboardLabel||r.key;
      row.querySelector('input').addEventListener('change',function(e){row.querySelector('label span').textContent=e.target.checked?'Visible':'Hidden';});
      row.querySelector('[data-widget-up]').addEventListener('click',function(){if(row.previousElementSibling)builder.insertBefore(row,row.previousElementSibling);syncMoveButtons();});
      row.querySelector('[data-widget-down]').addEventListener('click',function(){if(row.nextElementSibling)builder.insertBefore(row.nextElementSibling,row);syncMoveButtons();});
      builder.appendChild(row);
    });
    syncMoveButtons();
    var dragging=null;
    builder.querySelectorAll('.v524-dashboard-builder-row').forEach(function(row){
      row.addEventListener('dragstart',function(e){dragging=row;row.classList.add('is-dragging');if(e.dataTransfer){e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',row.dataset.key||'widget');}});
      row.addEventListener('dragend',function(){row.classList.remove('is-dragging');dragging=null;syncMoveButtons();});
      row.addEventListener('dragover',function(e){if(!dragging||dragging===row||!builder.contains(row))return;e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect='move';var box=row.getBoundingClientRect();builder.insertBefore(dragging,e.clientY<box.top+box.height/2?row:row.nextSibling);syncMoveButtons();});
    });
    builder.addEventListener('dragover',function(e){if(dragging){e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect='move';}});
    builder.addEventListener('drop',function(e){if(dragging)e.preventDefault();});
  }
  function toggle(open){
    if(open === layer.classList.contains('is-open')) return;
    layer.classList.toggle('is-open',open);
    layer.setAttribute('aria-hidden',open?'false':'true');
    document.documentElement.classList.toggle('mb50-modal-open',open);
    document.body.classList.toggle('mb661-widget-editing',open);
    if(open){
      returnFocus=document.activeElement;
      previousBodyOverflow=document.body.style.overflow;
      document.body.style.overflow='hidden';
      build();
      if(dialog)dialog.focus({preventScroll:true});
    } else {
      document.body.style.overflow=previousBodyOverflow;
      if(returnFocus && returnFocus.isConnected && typeof returnFocus.focus === 'function') returnFocus.focus({preventScroll:true});
      returnFocus=null;
    }
  }
  // Keep keyboard navigation inside the modal, including the save button.
  layer.addEventListener('keydown',function(event){
    if(event.key!=='Tab' || !layer.classList.contains('is-open'))return;
    var focusables=Array.prototype.slice.call(layer.querySelectorAll('button:not([disabled]),input:not([disabled]),a[href]')).filter(function(el){return el.getClientRects().length>0;});
    if(!focusables.length)return;
    var first=focusables[0], last=focusables[focusables.length-1];
    if(event.shiftKey && (document.activeElement===first || document.activeElement===dialog)){event.preventDefault();last.focus();}
    else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first.focus();}
  });
  openers.forEach(function(b){b.addEventListener('click',function(){toggle(true);});});
  closers.forEach(function(b){b.addEventListener('click',function(){toggle(false);});});
  if(save) save.addEventListener('click',function(){var rows=Array.prototype.slice.call(builder.children).map(function(r){return {key:r.dataset.key,hidden:!r.querySelector('input').checked};});try{localStorage.setItem(key,JSON.stringify(rows));}catch(e){}apply(rows);toggle(false);});
  if(reset) reset.addEventListener('click',function(){try{localStorage.removeItem(key);}catch(e){}apply(defaults());build();});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&layer.classList.contains('is-open'))toggle(false);});
  apply(get());
})();
