(function () {
  'use strict';

  var shell = document.querySelector('[data-student-workspace]');
  if (!shell || shell.dataset.workspaceReady === '50212') return;
  shell.dataset.workspaceReady = '50212';

  var collapseButton = shell.querySelector('[data-workspace-collapse]');
  var mobileOpenButton = shell.querySelector('[data-workspace-mobile-open]');
  var scrim = shell.querySelector('[data-workspace-scrim]');
  var profileToggles = Array.prototype.slice.call(shell.querySelectorAll('[data-workspace-profile-toggle]'));
  var profileMenu = shell.querySelector('[data-workspace-profile-menu]');
  var commandLayer = shell.querySelector('[data-workspace-command-layer]');
  var searchInput = shell.querySelector('[data-workspace-search-input]');
  var searchResults = shell.querySelector('[data-workspace-command-results]');
  var noticeLayer = shell.querySelector('[data-workspace-notice-layer]');
  var moreLayer = shell.querySelector('[data-workspace-more-layer]');
  var customizeLayer = shell.querySelector('[data-workspace-sidebar-customize-layer]');
  var sortables = Array.prototype.slice.call(shell.querySelectorAll('[data-sidebar-sortable]'));
  var sidebarBuilder = shell.querySelector('[data-sidebar-builder]');
  var searchUrl = shell.dataset.workspaceSearchUrl || '/workspace-search/';
  var storageScope = (shell.dataset.workspaceStorageScope || (shell.hasAttribute('data-staff-workspace') ? 'staff' : 'student')).replace(/[^a-z0-9_-]+/gi, '-');
  var storagePrefix = 'makonbook.workspace.sidebar.' + storageScope + '.v50212.';
  var collapseKey = storagePrefix + 'collapsed';
  var layoutKey = storagePrefix + 'layout';
  var groupsKey = storagePrefix + 'groups';
  var themeKey = 'sat-makon-theme';
  var searchTimer = null;
  var searchAbort = null;
  var searchItems = [];
  var searchIndex = -1;
  var directDraggingItem = null;
  var directDraggingGroup = null;

  function isDesktop() { return window.matchMedia('(min-width: 981px)').matches; }
  function reducedMotion() { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; }
  function safeGet(key) { try { return window.localStorage.getItem(key); } catch (error) { return null; } }
  function safeSet(key, value) { try { window.localStorage.setItem(key, value); } catch (error) { /* optional */ } }
  function safeRemove(key) { try { window.localStorage.removeItem(key); } catch (error) { /* optional */ } }

  // Keep an existing student's sidebar choices when upgrading the storage model.
  // Staff deliberately starts on fresh role-scoped keys so old student-shaped
  // layouts cannot corrupt teacher/manager/support navigation.
  if (storageScope === 'student') {
    [
      ['makonbook.studentSidebar.collapsed.v524', collapseKey],
      ['makonbook.studentSidebar.layout.v524', layoutKey],
      ['makonbook.studentSidebar.groups.v525', groupsKey]
    ].forEach(function (pair) {
      if (safeGet(pair[1]) !== null) return;
      var legacyValue = safeGet(pair[0]);
      if (legacyValue !== null) safeSet(pair[1], legacyValue);
    });
  }

  function setCollapsed(collapsed, persist) {
    if (!isDesktop()) collapsed = false;
    shell.classList.toggle('is-collapsed', !!collapsed);
    if (collapseButton) {
      collapseButton.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      collapseButton.setAttribute('aria-label', collapsed ? 'Expand navigation' : 'Collapse navigation');
    }
    if (persist) safeSet(collapseKey, collapsed ? '1' : '0');
  }
  function closeMobile() { shell.classList.remove('is-mobile-open'); if (mobileOpenButton) mobileOpenButton.setAttribute('aria-expanded','false'); document.documentElement.classList.remove('mb50-nav-open'); }
  function openMobile() { shell.classList.add('is-mobile-open'); if (mobileOpenButton) mobileOpenButton.setAttribute('aria-expanded','true'); document.documentElement.classList.add('mb50-nav-open'); }
  function setLayer(layer, open) { if (!layer) return; layer.classList.toggle('is-open',!!open); layer.setAttribute('aria-hidden',open?'false':'true'); var anyOpen=[commandLayer,noticeLayer,moreLayer,customizeLayer].some(function(item){return item&&item.classList.contains('is-open');}); document.documentElement.classList.toggle('mb50-modal-open',anyOpen); }
  function closeProfile(){if(!profileMenu)return;profileMenu.classList.remove('is-open');profileMenu.setAttribute('aria-hidden','true');profileToggles.forEach(function(toggle){toggle.setAttribute('aria-expanded','false');});}
  function closeOverlays(){setLayer(commandLayer,false);setLayer(noticeLayer,false);setLayer(moreLayer,false);setLayer(customizeLayer,false);closeProfile();}

  function navItems(){return Array.prototype.slice.call(shell.querySelectorAll('[data-sidebar-item][data-nav-key]'));}
  shell.querySelectorAll('.mb50-nav-item').forEach(function(item){var label=item.querySelector(':scope > span');if(label&&!item.dataset.navTooltip)item.dataset.navTooltip=(label.textContent||'').trim();});
  function refreshSortables(){sortables=Array.prototype.slice.call(shell.querySelectorAll('[data-sidebar-sortable]'));return sortables;}
  var initialGroupMeta=refreshSortables().map(function(group){
    var label=group.querySelector(':scope > .mb50-nav-label');
    return {key:group.dataset.sidebarGroup,label:(label?label.textContent:'Section').trim().slice(0,36)||'Section',custom:false};
  });
  var initialGroupKeys=initialGroupMeta.map(function(group){return group.key;});
  function firstDefaultGroup(){return initialGroupKeys[0]||'';}
  function defaultGroupLabel(key){var hit=initialGroupMeta.find(function(group){return group.key===key;});return hit?hit.label:'Section';}
  function defaultGroups(){return initialGroupMeta.map(function(group){return {key:group.key,label:group.label,custom:false};});}
  function readGroups(){
    var defaults=defaultGroups(), parsed=null;
    try{parsed=JSON.parse(safeGet(groupsKey)||'null');}catch(error){parsed=null;}
    if(!Array.isArray(parsed))return defaults;
    var clean=[],seen={};
    parsed.forEach(function(row){
      if(!row||!row.key||seen[row.key])return;
      var isDefault=initialGroupKeys.indexOf(row.key)>=0,isCustom=String(row.key).indexOf('custom-')===0;
      if(!isDefault&&!isCustom)return;
      seen[row.key]=true;
      var fallback=defaultGroupLabel(row.key);
      clean.push({key:row.key,label:String(row.label||fallback).trim().slice(0,36)||fallback,custom:!isDefault});
    });
    defaults.forEach(function(row){if(!seen[row.key])clean.push(row);});
    return clean;
  }
  function groupKeys(){return readGroups().map(function(group){return group.key;});}
  function hydrateGroups(){
    var nav=shell.querySelector('.mb50-nav'), marker=nav&&nav.querySelector('.mb50-nav-secondary:not([data-sidebar-sortable])'); if(!nav)return;
    var groups=readGroups(), active={};groups.forEach(function(meta){active[meta.key]=true;});
    nav.querySelectorAll('[data-sidebar-custom="1"]').forEach(function(group){if(!active[group.dataset.sidebarGroup])group.remove();});
    groups.forEach(function(meta){
      var group=nav.querySelector('[data-sidebar-group="'+meta.key+'"]');
      if(!group&&meta.custom){group=document.createElement('div');group.className='mb50-nav-group';group.dataset.sidebarSortable='';group.dataset.sidebarGroup=meta.key;group.dataset.sidebarCustom='1';group.innerHTML='<span class="mb50-nav-label"></span>';}
      if(!group)return;var label=group.querySelector(':scope > .mb50-nav-label');if(label)label.textContent=meta.label;nav.insertBefore(group,marker||null);
    });
    refreshSortables();
  }
  function defaultLayout(){var fallbackGroup=firstDefaultGroup();return navItems().map(function(item){return {key:item.dataset.navKey,hidden:item.dataset.sidebarDefaultHidden==='1',group:item.dataset.sidebarDefaultGroup||((item.closest('[data-sidebar-group]')||{}).dataset||{}).sidebarGroup||fallbackGroup};});}
  function readLayout(){
    var defaults=defaultLayout();
    try{var parsed=JSON.parse(safeGet(layoutKey)||'null');if(!Array.isArray(parsed))return defaults;var known={};defaults.forEach(function(row){known[row.key]=row;});var validGroups=groupKeys();var clean=parsed.filter(function(row){return row&&known[row.key];}).map(function(row){var fallback=known[row.key];return {key:row.key,hidden:!!row.hidden,group:validGroups.indexOf(row.group)>=0?row.group:fallback.group};});defaults.forEach(function(row){if(!clean.some(function(saved){return saved.key===row.key;}))clean.push(row);});return clean;}catch(error){return defaults;}
  }
  function currentLayoutFromDom(){var out=[];refreshSortables().forEach(function(group){Array.prototype.slice.call(group.querySelectorAll(':scope > [data-sidebar-item][data-nav-key]')).forEach(function(item){out.push({key:item.dataset.navKey,hidden:item.dataset.sidebarLocked==='1'?false:!!item.hidden,group:group.dataset.sidebarGroup});});});return out;}
  function currentGroupsFromDom(){return refreshSortables().map(function(group){var label=group.querySelector(':scope > .mb50-nav-label');return {key:group.dataset.sidebarGroup,label:(label?label.textContent:'Section').trim().slice(0,36),custom:group.dataset.sidebarCustom==='1'};});}
  function persistSidebarDom(){safeSet(layoutKey,JSON.stringify(currentLayoutFromDom()));safeSet(groupsKey,JSON.stringify(currentGroupsFromDom()));}
  function applyLayout(layout){
    hydrateGroups();var map={},groups={};refreshSortables().forEach(function(group){groups[group.dataset.sidebarGroup]=group;});navItems().forEach(function(item){map[item.dataset.navKey]=item;});
    layout.forEach(function(row){var item=map[row.key];if(!item)return;var target=groups[row.group]||groups[item.dataset.sidebarDefaultGroup]||sortables[0];target.appendChild(item);var locked=item.dataset.sidebarLocked==='1';item.hidden=locked?false:!!row.hidden;item.classList.toggle('is-sidebar-hidden',!locked&&!!row.hidden);});
    wireDirectSidebarDrag();
  }
  function labelForItem(item){var label=item.querySelector('span');return label?label.textContent.trim():item.dataset.navKey;}

  function makeSixDotHandle(className, title) {
    var handle = document.createElement('span');
    handle.className = className;
    handle.title = title || 'Drag';
    handle.setAttribute('aria-hidden', 'true');
    handle.innerHTML = '<i></i><i></i><i></i><i></i><i></i><i></i>';
    return handle;
  }

  function clearSidebarDragState(){
    shell.querySelectorAll('.is-sidebar-dragging,.is-sidebar-drag-target').forEach(function(node){node.classList.remove('is-sidebar-dragging','is-sidebar-drag-target');});
    directDraggingItem=null;directDraggingGroup=null;
  }

  function wireDirectSidebarDrag(){
    refreshSortables();
    navItems().forEach(function(item){
      item.draggable=false;
      var existing=item.querySelector(':scope > .mb526-nav-drag-handle');
      var canDrag=item.dataset.sidebarLocked!=='1' && !item.disabled;
      if(!canDrag){if(existing)existing.remove();return;}
      if(existing)return;
      var handle=makeSixDotHandle('mb526-nav-drag-handle','Drag '+labelForItem(item));
      handle.draggable=true;
      item.classList.add('mb526-nav-drag-enabled');
      item.appendChild(handle);
      ['mousedown','pointerdown','click'].forEach(function(name){handle.addEventListener(name,function(event){event.stopPropagation();if(name==='click')event.preventDefault();});});
      handle.addEventListener('dragstart',function(event){
        if(!isDesktop()||shell.classList.contains('is-collapsed')){event.preventDefault();return;}
        directDraggingItem=item;directDraggingGroup=null;item.classList.add('is-sidebar-dragging');
        if(event.dataTransfer){event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain','nav:'+item.dataset.navKey);}
      });
      handle.addEventListener('dragend',function(){persistSidebarDom();clearSidebarDragState();});
    });

    refreshSortables().forEach(function(group){
      var label=group.querySelector(':scope > .mb50-nav-label');
      if(label&&!label.querySelector('.mb526-section-drag-handle')){
        label.draggable=false;
        var groupHandle=makeSixDotHandle('mb526-section-drag-handle','Drag section');
        groupHandle.draggable=true;label.appendChild(groupHandle);
        ['mousedown','pointerdown','click'].forEach(function(name){groupHandle.addEventListener(name,function(event){event.stopPropagation();if(name==='click')event.preventDefault();});});
        groupHandle.addEventListener('dragstart',function(event){
          if(!isDesktop()||shell.classList.contains('is-collapsed')){event.preventDefault();return;}
          directDraggingGroup=group;directDraggingItem=null;group.classList.add('is-sidebar-dragging');
          if(event.dataTransfer){event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain','group:'+group.dataset.sidebarGroup);}
        });
        groupHandle.addEventListener('dragend',function(){persistSidebarDom();clearSidebarDragState();});
      }
      if(group.dataset.sidebarDropWired==='50212')return;
      group.dataset.sidebarDropWired='50212';
      group.addEventListener('dragover',function(event){
        if(!directDraggingItem&&!directDraggingGroup)return;
        event.preventDefault();
        group.classList.add('is-sidebar-drag-target');
        if(directDraggingItem){
          var candidates=Array.prototype.slice.call(group.querySelectorAll(':scope > [data-sidebar-item]:not(.is-sidebar-dragging)'));
          var before=candidates.find(function(candidate){var box=candidate.getBoundingClientRect();return event.clientY<box.top+box.height/2;});
          if(before)group.insertBefore(directDraggingItem,before);else group.appendChild(directDraggingItem);
        }else if(directDraggingGroup&&directDraggingGroup!==group){
          var nav=group.parentNode,box=group.getBoundingClientRect();
          nav.insertBefore(directDraggingGroup,event.clientY<box.top+box.height/2?group:group.nextSibling);
          refreshSortables();
        }
      });
      group.addEventListener('dragleave',function(event){if(!group.contains(event.relatedTarget))group.classList.remove('is-sidebar-drag-target');});
      group.addEventListener('drop',function(event){if(!directDraggingItem&&!directDraggingGroup)return;event.preventDefault();persistSidebarDom();clearSidebarDragState();});
    });
  }

  function buildSidebarEditor(){
    if(!sidebarBuilder)return;
    sidebarBuilder.innerHTML='';
    var groupMeta=readGroups(),layout=readLayout(),groups={},draggingRow=null,draggingSection=null;
    var add=document.createElement('div');
    add.className='mb50-builder-add-group';
    add.innerHTML='<input type="text" maxlength="36" placeholder="New section name"><button type="button"><i class="bi bi-plus-lg"></i> Add section</button>';
    sidebarBuilder.appendChild(add);
    var groupHost=document.createElement('div');groupHost.className='mb50-builder-groups';sidebarBuilder.appendChild(groupHost);

    function insertDraggedRow(list,event){
      if(!draggingRow)return;
      var rows=Array.prototype.slice.call(list.querySelectorAll(':scope > .mb50-builder-row:not(.is-dragging)'));
      var before=rows.find(function(row){var box=row.getBoundingClientRect();return event.clientY<box.top+box.height/2;});
      if(before)list.insertBefore(draggingRow,before);else list.appendChild(draggingRow);
    }
    function wireGroupList(list){
      if(!list||list.dataset.builderDropWired==='50212')return;
      list.dataset.builderDropWired='50212';
      list.addEventListener('dragover',function(event){if(!draggingRow)return;event.preventDefault();event.stopPropagation();list.classList.add('is-builder-drop-target');insertDraggedRow(list,event);});
      list.addEventListener('dragleave',function(event){if(!list.contains(event.relatedTarget))list.classList.remove('is-builder-drop-target');});
      list.addEventListener('drop',function(event){if(!draggingRow)return;event.preventDefault();event.stopPropagation();insertDraggedRow(list,event);list.classList.remove('is-builder-drop-target');});
    }
    function wireGroupSection(section){
      if(!section||section.dataset.builderGroupWired==='50212')return;
      section.dataset.builderGroupWired='50212';
      section.draggable=false;
      var grip=section.querySelector('[data-builder-group-grip]');
      if(grip){
        grip.draggable=true;
        grip.addEventListener('dragstart',function(event){draggingSection=section;draggingRow=null;section.classList.add('is-dragging-group');event.stopPropagation();if(event.dataTransfer){event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain','builder-group:'+section.dataset.builderGroupSection);}});
        grip.addEventListener('dragend',function(){section.classList.remove('is-dragging-group');draggingSection=null;});
      }
      section.addEventListener('dragover',function(event){if(!draggingSection||draggingSection===section||draggingRow)return;event.preventDefault();var box=section.getBoundingClientRect();groupHost.insertBefore(draggingSection,event.clientY<box.top+box.height/2?section:section.nextSibling);});
      var del=section.querySelector('[data-builder-group-delete]');
      if(del)del.addEventListener('click',function(){var list=section.querySelector('[data-builder-group-list]');var fallback=groupHost.querySelector('[data-builder-group-section="'+firstDefaultGroup()+'"] [data-builder-group-list]')||Array.prototype.slice.call(groupHost.querySelectorAll('[data-builder-group-list]')).find(function(candidate){return candidate!==list;});Array.prototype.slice.call(list.children).forEach(function(row){if(fallback)fallback.appendChild(row);});delete groups[list.dataset.group];section.remove();});
      wireGroupList(section.querySelector('[data-builder-group-list]'));
    }
    function addGroupSection(meta){
      var section=document.createElement('section');section.className='mb50-builder-group';section.dataset.builderGroupSection=meta.key;
      section.innerHTML='<header><input class="mb50-builder-group-title" maxlength="36"><div class="mb50-builder-group-tools"><button type="button" data-builder-group-grip title="Drag section"><i class="bi bi-grip-horizontal"></i></button>'+(meta.custom?'<button type="button" data-builder-group-delete title="Delete section"><i class="bi bi-trash3"></i></button>':'')+'</div></header><div class="mb50-builder-group-list" data-builder-group-list></div>';
      var title=section.querySelector('.mb50-builder-group-title');title.value=meta.label;
      var list=section.querySelector('[data-builder-group-list]');list.dataset.group=meta.key;
      groupHost.appendChild(section);groups[meta.key]=list;wireGroupSection(section);return section;
    }
    function wireBuilderRow(row,locked){
      if(!row||row.dataset.builderRowWired==='50212')return;row.dataset.builderRowWired='50212';row.draggable=false;
      var grip=row.querySelector('.mb50-builder-grip');
      if(grip&&!locked){
        grip.draggable=true;
        grip.title='Drag item';
        grip.addEventListener('dragstart',function(event){draggingRow=row;draggingSection=null;row.classList.add('is-dragging');event.stopPropagation();if(event.dataTransfer){event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain','builder-item:'+row.dataset.key);}});
        grip.addEventListener('dragend',function(){row.classList.remove('is-dragging');draggingRow=null;sidebarBuilder.querySelectorAll('.is-builder-drop-target').forEach(function(x){x.classList.remove('is-builder-drop-target');});});
      }else if(grip){grip.classList.add('is-locked');}
    }

    groupMeta.forEach(addGroupSection);
    layout.forEach(function(row){
      var item=shell.querySelector('[data-sidebar-item][data-nav-key="'+row.key+'"]');if(!item)return;
      var locked=item.dataset.sidebarLocked==='1',card=document.createElement('div');card.className='mb50-builder-row';card.dataset.key=row.key;
      card.innerHTML='<span class="mb50-builder-grip"><i class="bi bi-grip-vertical"></i></span><span class="mb50-builder-icon"><i class="'+((item.querySelector('i')||{}).className||'bi bi-circle')+'"></i></span><strong></strong><div class="mb50-builder-controls"><label><input type="checkbox" data-builder-visible '+((locked||!row.hidden)?'checked ':'')+(locked?'disabled':'')+'><span>'+(locked?'Pinned':'Show')+'</span></label></div>';
      card.querySelector('strong').textContent=labelForItem(item);(groups[row.group]||groups[firstDefaultGroup()]||groupHost).appendChild(card);wireBuilderRow(card,locked);
    });

    add.querySelector('button').addEventListener('click',function(){
      var input=add.querySelector('input'),label=(input.value||'').trim();if(!label)return;
      var key='custom-'+Date.now().toString(36);addGroupSection({key:key,label:label.slice(0,36),custom:true});input.value='';
    });
  }

  function saveSidebarEditor(){
    if(!sidebarBuilder)return;var layout=[],groups=[];sidebarBuilder.querySelectorAll('[data-builder-group-section]').forEach(function(section){var list=section.querySelector('[data-builder-group-list]'),title=section.querySelector('.mb50-builder-group-title'),key=list.dataset.group;groups.push({key:key,label:(title.value||'Section').trim().slice(0,36)||'Section',custom:key.indexOf('custom-')===0});Array.prototype.slice.call(list.querySelectorAll('.mb50-builder-row')).forEach(function(row){var visible=row.querySelector('[data-builder-visible]');layout.push({key:row.dataset.key,hidden:visible?!visible.checked:false,group:key});});});safeSet(groupsKey,JSON.stringify(groups));safeSet(layoutKey,JSON.stringify(layout));applyLayout(layout);setLayer(customizeLayer,false);
  }

  function renderSearch(groups) {
    if (!searchResults) return;
    searchResults.innerHTML = '';
    searchItems = [];
    searchIndex = -1;
    if (!groups || !groups.length) {
      searchResults.innerHTML = '<div class="mb50-command-empty">No matching MakonBook items.</div>';
      return;
    }
    groups.forEach(function (group) {
      var section = document.createElement('section');
      section.className = 'mb50-search-group';
      var title = document.createElement('h3');
      title.textContent = group.label;
      section.appendChild(title);
      (group.items || []).forEach(function (item) {
        var link = document.createElement('a');
        link.href = item.url;
        link.className = 'mb50-search-result';
        link.innerHTML = '<i class="bi ' + (item.icon || 'bi-search') + '"></i><span><strong></strong><small></small></span><em></em>';
        link.querySelector('strong').textContent = item.title || '';
        link.querySelector('small').textContent = item.subtitle || '';
        link.querySelector('em').textContent = item.type || '';
        section.appendChild(link);
        searchItems.push(link);
      });
      searchResults.appendChild(section);
    });
  }

  function updateSearchSelection(next) {
    if (!searchItems.length) return;
    searchIndex = Math.max(0, Math.min(searchItems.length - 1, next));
    searchItems.forEach(function (item, index) { item.classList.toggle('is-selected', index === searchIndex); });
    searchItems[searchIndex].scrollIntoView({ block: 'nearest' });
  }

  function performSearch(value) {
    var query = value.trim();
    if (query.length < 2) {
      if (searchResults) searchResults.innerHTML = '<div class="mb50-command-empty">Start typing at least 2 characters.</div>';
      searchItems = [];
      return;
    }
    if (searchAbort) searchAbort.abort();
    searchAbort = window.AbortController ? new AbortController() : null;
    if (searchResults) searchResults.innerHTML = '<div class="mb50-command-empty">Searching…</div>';
    fetch(searchUrl + '?q=' + encodeURIComponent(query), { credentials: 'same-origin', signal: searchAbort ? searchAbort.signal : undefined })
      .then(function (response) { if (!response.ok) throw new Error('Search failed'); return response.json(); })
      .then(function (payload) { renderSearch(payload.groups || []); })
      .catch(function (error) { if (error.name === 'AbortError') return; if (searchResults) searchResults.innerHTML = '<div class="mb50-command-empty">Search is temporarily unavailable.</div>'; });
  }

  function openSearch() {
    closeOverlays();
    setLayer(commandLayer, true);
    if (searchInput) {
      searchInput.value = '';
      if (searchResults) searchResults.innerHTML = '<div class="mb50-command-empty">Start typing at least 2 characters.</div>';
      searchItems = [];
      searchIndex = -1;
      window.setTimeout(function () { searchInput.focus(); }, 90);
    }
  }

  function setTheme(next) {
    shell.classList.remove('mb50-theme-shifting');
    void shell.offsetWidth;
    shell.classList.add('mb50-theme-shifting');
    safeSet(themeKey, next);
    document.documentElement.dataset.themeMode = next;
    document.documentElement.dataset.theme = next;
    document.documentElement.style.colorScheme = next;
    window.setTimeout(function () { shell.classList.remove('mb50-theme-shifting'); }, reducedMotion() ? 0 : 560);
  }

  // The shared theme picker lives outside this file. Add the same visual
  // transition when a Settings theme choice is clicked.
  shell.addEventListener('click', function (event) {
    if (!event.target.closest('[data-theme-choice]')) return;
    shell.classList.remove('mb50-theme-shifting');
    void shell.offsetWidth;
    shell.classList.add('mb50-theme-shifting');
    window.setTimeout(function () { shell.classList.remove('mb50-theme-shifting'); }, reducedMotion() ? 0 : 560);
  }, true);

  applyLayout(readLayout());

  // Cheap perceived-performance win: warm internal GET destinations when the
  // pointer or keyboard intent reaches them. This keeps normal Django
  // navigation/CSRF semantics intact instead of introducing brittle PJAX.
  var prefetched = {};
  function prefetchLink(link) {
    if (!link || !link.href || prefetched[link.href]) return;
    // Only warm explicit workspace navigation. Never prefetch account actions
    // such as /logout/ or launch/start endpoints whose GET may mutate state.
    if (!link.matches('.mb50-brand,.mb50-mobile-brand,.mb50-nav a.mb50-nav-item,.mb50-more-grid a')) return;
    if (link.hasAttribute('download') || (link.target && link.target !== '_self')) return;
    try {
      var url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || url.pathname === window.location.pathname) return;
      prefetched[link.href] = true;
      var hint = document.createElement('link');
      hint.rel = 'prefetch'; hint.href = link.href; hint.as = 'document';
      document.head.appendChild(hint);
    } catch (error) { /* ignore malformed optional links */ }
  }
  shell.addEventListener('pointerover', function (event) { prefetchLink(event.target.closest('a[href]')); }, {passive:true});
  shell.addEventListener('focusin', function (event) { prefetchLink(event.target.closest('a[href]')); });

  // Chrome can start the same safe workspace-document prefetch a little earlier
  // than the manual hover hint. This is intentionally selector-scoped: account
  // actions, logout and test launch URLs are excluded.
  try {
    if (window.HTMLScriptElement && HTMLScriptElement.supports && HTMLScriptElement.supports('speculationrules')) {
      var speculation = document.createElement('script');
      speculation.type = 'speculationrules';
      speculation.textContent = JSON.stringify({prefetch:[{source:'document',where:{selector_matches:'.mb50-brand, .mb50-mobile-brand, .mb50-nav a.mb50-nav-item, .mb50-more-grid a'},eagerness:'moderate'}]});
      document.head.appendChild(speculation);
    }
  } catch (error) { /* optional browser optimization */ }

  function showRouteProgress(link){
    if(!link||!link.matches('.mb50-brand,.mb50-mobile-brand,.mb50-nav a.mb50-nav-item,.mb50-more-grid a,.v523-row-link,.v524-admissions-card,.v523-topic-card'))return;
    if(link.target&&link.target!=='_self')return;
    var bar=document.querySelector('.mb526-route-progress');if(bar)return;
    bar=document.createElement('div');bar.className='mb526-route-progress';document.body.appendChild(bar);
  }
  shell.addEventListener('click',function(event){var link=event.target.closest('a[href]');if(link)showRouteProgress(link);},true);

  shell.querySelectorAll('[data-v524-toast]').forEach(function (toast, index) {
    var close = toast.querySelector('button');
    function dismiss() { toast.classList.add('is-leaving'); setTimeout(function(){ toast.remove(); }, 260); }
    if (close) close.addEventListener('click', dismiss);
    setTimeout(dismiss, 4200 + index * 450);
  });
  if (isDesktop()) setCollapsed(safeGet(collapseKey) === '1', false);

  if (collapseButton) collapseButton.addEventListener('click', function () { if (isDesktop()) setCollapsed(!shell.classList.contains('is-collapsed'), true); });
  if (mobileOpenButton) mobileOpenButton.addEventListener('click', function () { shell.classList.contains('is-mobile-open') ? closeMobile() : openMobile(); });
  if (scrim) scrim.addEventListener('click', closeMobile);

  shell.querySelectorAll('.mb50-nav-item').forEach(function (item) {
    var text = item.querySelector('span');
    if (text) {
      var label = text.textContent.trim();
      if (!item.title) item.title = label;
      item.dataset.sidebarLabel = label;
    }
    item.addEventListener('click', function () { if (!isDesktop()) closeMobile(); });
  });

  shell.querySelectorAll('[data-workspace-command="search"]').forEach(function (button) { button.addEventListener('click', openSearch); });
  shell.querySelectorAll('[data-workspace-command="notifications"]').forEach(function (button) {
    button.addEventListener('click', function () {
      closeOverlays();
      setLayer(noticeLayer, true);
    });
  });
  shell.querySelectorAll('[data-workspace-notice-close]').forEach(function (button) { button.addEventListener('click', function () { setLayer(noticeLayer, false); }); });
  shell.querySelectorAll('[data-workspace-command-close]').forEach(function (button) { button.addEventListener('click', function () { setLayer(commandLayer, false); }); });
  shell.querySelectorAll('[data-workspace-more-open]').forEach(function (button) { button.addEventListener('click', function () { closeOverlays(); setLayer(moreLayer, true); }); });
  shell.querySelectorAll('[data-workspace-more-close]').forEach(function (button) { button.addEventListener('click', function () { setLayer(moreLayer, false); }); });
  shell.querySelectorAll('[data-workspace-sidebar-customize-open]').forEach(function (button) {
    button.addEventListener('click', function () { setLayer(moreLayer, false); buildSidebarEditor(); setLayer(customizeLayer, true); });
  });
  shell.querySelectorAll('[data-workspace-sidebar-customize-close]').forEach(function (button) { button.addEventListener('click', function () { setLayer(customizeLayer, false); }); });
  var saveSidebar = shell.querySelector('[data-sidebar-save]');
  if (saveSidebar) saveSidebar.addEventListener('click', saveSidebarEditor);
  var resetSidebar = shell.querySelector('[data-sidebar-reset]');
  if (resetSidebar) resetSidebar.addEventListener('click', function () { safeRemove(layoutKey); safeRemove(groupsKey); shell.querySelectorAll('[data-sidebar-custom="1"]').forEach(function(group){group.remove();}); hydrateGroups(); applyLayout(defaultLayout()); buildSidebarEditor(); });

  profileToggles.forEach(function (toggle) {
    toggle.addEventListener('click', function (event) {
      event.stopPropagation();
      if (!isDesktop() && toggle.classList.contains('mb50-mobile-account')) openMobile();
      if (!profileMenu) return;
      var open = !profileMenu.classList.contains('is-open');
      profileMenu.classList.toggle('is-open', open);
      profileMenu.setAttribute('aria-hidden', open ? 'false' : 'true');
      profileToggles.forEach(function (item) { item.setAttribute('aria-expanded', open ? 'true' : 'false'); });
    });
  });

  shell.querySelectorAll('[data-workspace-theme-cycle]').forEach(function (button) {
    button.addEventListener('click', function () {
      var current = document.documentElement.dataset.theme === 'light' ? 'light' : 'dark';
      setTheme(current === 'light' ? 'dark' : 'light');
      closeProfile();
    });
  });

  if (searchInput) {
    searchInput.addEventListener('input', function () {
      window.clearTimeout(searchTimer);
      var value = searchInput.value;
      searchTimer = window.setTimeout(function () { performSearch(value); }, 180);
    });
    searchInput.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown') { event.preventDefault(); updateSearchSelection(searchIndex + 1); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); updateSearchSelection(searchIndex <= 0 ? 0 : searchIndex - 1); }
      else if (event.key === 'Enter' && searchItems.length) { event.preventDefault(); if (searchIndex < 0) searchIndex = 0; window.location.href = searchItems[searchIndex].href; }
    });
  }

  document.addEventListener('keydown', function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); openSearch(); return; }
    if (event.key === 'Escape') { closeOverlays(); closeMobile(); }
  });
  document.addEventListener('click', function (event) {
    if (profileMenu && profileMenu.classList.contains('is-open') && !profileMenu.contains(event.target) && !profileToggles.some(function (toggle) { return toggle.contains(event.target); })) closeProfile();
  });
  window.addEventListener('resize', function () {
    if (isDesktop()) { closeMobile(); setCollapsed(safeGet(collapseKey) === '1', false); }
    else shell.classList.remove('is-collapsed');
  });

  // Consistent tactile feedback for workspace controls without delaying actions.
  shell.addEventListener('pointerdown', function (event) {
    var target = event.target.closest('button, a.mb50-primary-btn, a.mb50-secondary-btn, .mb50-card a, .v523-action');
    if (!target || target.disabled) return;
    target.classList.add('mb50-is-pressed');
  });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (name) {
    shell.addEventListener(name, function () { shell.querySelectorAll('.mb50-is-pressed').forEach(function (item) { item.classList.remove('mb50-is-pressed'); }); }, true);
  });
})();
