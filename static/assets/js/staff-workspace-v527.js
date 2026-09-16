(function(){
  'use strict';
  var shell=document.querySelector('[data-staff-workspace]'); if(!shell)return;
  var collapse=document.querySelector('[data-staff-collapse]');
  var sidebar=document.querySelector('[data-staff-sidebar]');
  var mobileOpen=document.querySelector('[data-staff-mobile-open]');
  var scrim=document.querySelector('[data-staff-scrim]');
  var profileToggles=document.querySelectorAll('[data-staff-profile-toggle]');
  var profileMenu=document.querySelector('[data-staff-profile-menu]');
  var storageKey='makonbook.staff.sidebar.collapsed';
  try{if(localStorage.getItem(storageKey)==='1')shell.classList.add('is-collapsed')}catch(e){}
  function syncCollapse(){if(collapse)collapse.setAttribute('aria-expanded',shell.classList.contains('is-collapsed')?'false':'true')}
  syncCollapse();
  if(collapse)collapse.addEventListener('click',function(){shell.classList.toggle('is-collapsed');try{localStorage.setItem(storageKey,shell.classList.contains('is-collapsed')?'1':'0')}catch(e){}syncCollapse()});
  function closeMobile(){shell.classList.remove('is-mobile-open')}
  if(mobileOpen)mobileOpen.addEventListener('click',function(){shell.classList.add('is-mobile-open')});
  if(scrim)scrim.addEventListener('click',closeMobile);
  if(sidebar)sidebar.addEventListener('click',function(e){if(window.innerWidth<=980&&e.target.closest('a'))closeMobile()});
  function setProfile(open){if(!profileMenu)return;profileMenu.classList.toggle('is-open',open);profileMenu.setAttribute('aria-hidden',open?'false':'true');profileToggles.forEach(function(b){b.setAttribute('aria-expanded',open?'true':'false')})}
  profileToggles.forEach(function(btn){btn.addEventListener('click',function(e){e.stopPropagation();setProfile(!(profileMenu&&profileMenu.classList.contains('is-open')))})});
  document.addEventListener('click',function(e){if(profileMenu&&!profileMenu.contains(e.target)&&!e.target.closest('[data-staff-profile-toggle]'))setProfile(false)});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'){setProfile(false);closeMobile()}});
  document.querySelectorAll('[data-staff-theme-cycle]').forEach(function(btn){btn.addEventListener('click',function(){var themeBtn=document.querySelector('[data-theme-toggle]');if(themeBtn){themeBtn.click();return}var root=document.documentElement;var next=root.dataset.theme==='dark'?'light':'dark';try{localStorage.setItem('sat-makon-theme',next)}catch(e){}root.dataset.theme=next;root.dataset.themeMode=next;root.style.colorScheme=next})});
  document.querySelectorAll('[data-sf27-toast]').forEach(function(toast){var close=toast.querySelector('button');if(close)close.addEventListener('click',function(){toast.remove()});setTimeout(function(){if(toast.isConnected){toast.style.opacity='0';toast.style.transform='translateY(-6px)';setTimeout(function(){toast.remove()},180)}},5000)});
  // Safe perceived-navigation optimization for read-only staff pages.
  var prefetched=new Set();
  document.addEventListener('pointerenter',function(e){var a=e.target.closest&&e.target.closest('.sf27-nav-item[href], .sf27-role-switcher a[href]');if(!a)return;var u=new URL(a.href,location.href);if(u.origin!==location.origin||u.pathname.includes('/logout/'))return;if(prefetched.has(u.href))return;prefetched.add(u.href);var link=document.createElement('link');link.rel='prefetch';link.href=u.href;document.head.appendChild(link)},true);
})();
