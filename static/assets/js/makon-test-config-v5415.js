class MakonBookPreTestConfigV5415 {
  constructor() {
    this.modes = [
      { id:'full_test', title:'Full Test', desc:'All modules (RW + Math)', baseMin:134, icon:'bi-bullseye' },
      { id:'rw_only', title:'English Only', desc:'Both Reading & Writing modules', baseMin:64, icon:'bi-book' },
      { id:'math_only', title:'Math Only', desc:'Both Math modules', baseMin:70, icon:'bi-calculator' },
      { id:'single_module', title:'Single Module', desc:'Practice exactly one module', baseMin:32, icon:'bi-lightning-charge' }
    ];
    this.subModes = [
      { id:'single_english_m1', title:'English M1', baseMin:32 },
      { id:'single_english_m2', title:'English M2', baseMin:32 },
      { id:'single_math_m1', title:'Math M1', baseMin:35 },
      { id:'single_math_m2', title:'Math M2', baseMin:35 }
    ];
    this.integrityModes = [
      { id:'off', title:'Off', desc:'No Anti-Cheat monitoring.' },
      { id:'standard', title:'Standard', desc:'3 strikes, tab/app, inactivity and fullscreen monitoring.' },
      { id:'strict', title:'Strict', desc:'Standard + copy/paste, right-click and shortcut protection.' }
    ];
    this.state = { mode:'full_test', integrity:'standard', targetHref:null };
    this.build();
    this.bind();
  }

  fmt(min){
    if(min < 60) return `${min} min`;
    const h=Math.floor(min/60), m=min%60;
    return m ? `${h}h ${m}min` : `${h}h`;
  }

  build(){
    if(document.getElementById('ptc-overlay')) return;
    const overlay=document.createElement('div');
    overlay.id='ptc-overlay';
    overlay.className='ptc-overlay';
    overlay.innerHTML=`
      <div class="ptc-dialog" role="dialog" aria-modal="true" aria-label="Configure practice test">
        <div class="ptc-section-title">Choose module</div>
        <div class="ptc-mode-grid">
          ${this.modes.map((m,i)=>`
            <div class="ptc-mode-card ${i===0?'is-active':''}" data-id="${m.id}">
              <div class="ptc-radio-wrapper"><div class="ptc-radio"></div></div>
              <div class="ptc-mode-info">
                <div class="ptc-mode-title-wrapper"><i class="bi ${m.icon} ptc-mode-icon"></i><div class="ptc-mode-title">${m.title}</div></div>
                <div class="ptc-mode-desc">${m.desc}</div>
                <div class="ptc-badge">${this.fmt(m.baseMin)}</div>
              </div>
            </div>`).join('')}
        </div>

        <div class="ptc-submode-container" id="ptc-submodes" style="display:none;margin-top:12px;">
          <div class="ptc-submode-grid">
            ${this.subModes.map(sm=>`<div class="ptc-submode-card" data-sub="${sm.id}">${sm.title}</div>`).join('')}
          </div>
        </div>

        <div class="ptc-section-title">Exam Integrity</div>
        <div class="ptc-integrity-grid">
          ${this.integrityModes.map((m,i)=>`
            <div class="ptc-integrity-card ${i===1?'is-active':''}" data-integrity="${m.id}">
              <strong>${m.title}</strong><span>${m.desc}</span>
            </div>`).join('')}
        </div>
        <div class="ptc-integrity-note" id="ptc-integrity-note">Standard uses the 3-strike Anti-Cheat system.</div>

        <div class="ptc-summary">
          <div><div class="ptc-summary-label">Estimated Duration</div><div class="ptc-summary-val" id="ptc-total-time">2h 14min</div></div>
          <div style="text-align:right;"><div class="ptc-summary-label">Protection</div><div class="ptc-summary-val" id="ptc-protection" style="font-size:1.1rem;font-weight:500;">Standard</div></div>
        </div>

        <div class="ptc-footer">
          <button class="ptc-btn ptc-btn-cancel" id="ptc-btn-cancel" type="button">Cancel</button>
          <button class="ptc-btn ptc-btn-start" id="ptc-btn-start" type="button"><span>Continue</span><i class="bi bi-arrow-right"></i></button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    this.el=overlay;
  }

  bind(){
    this.el.addEventListener('click',e=>{ if(e.target===this.el) this.close(); });
    this.el.querySelector('#ptc-btn-cancel').addEventListener('click',()=>this.close());
    this.el.querySelectorAll('.ptc-mode-card').forEach(card=>card.addEventListener('click',()=>{
      const id=card.dataset.id;
      this.state.mode=id==='single_module'?'single_english_m1':id;
      this.repaint();
    }));
    this.el.querySelectorAll('.ptc-submode-card').forEach(card=>card.addEventListener('click',()=>{
      if(this.state.mode.startsWith('single_')){
        this.state.mode=card.dataset.sub;
        this.repaint();
      }
    }));
    this.el.querySelectorAll('.ptc-integrity-card').forEach(card=>card.addEventListener('click',()=>{
      this.state.integrity=card.dataset.integrity||'standard';
      try{localStorage.setItem('makonbook:practice-integrity-mode',this.state.integrity)}catch(_e){}
      this.repaint();
    }));
    this.el.querySelector('#ptc-btn-start').addEventListener('click',()=>this.continue());

    // Capture phase: prevent the existing Practice Tests JS from replacing the button text with "Opening...".
    document.addEventListener('click',e=>{
      const link=e.target.closest('.practice-action[data-practice-navigate]');
      if(!link) return;

      const card=link.closest('.practice-test-card');
      const fresh=!!(card && card.querySelector('.practice-progress-note.is-ready'));
      const href=link.getAttribute('href')||'';
      if(!fresh || href.includes('/teacher/')) return;

      const isTestStart = /\/tests\/[^/?#]+\/start\/?(?:[?#]|$)/.test(href) ||
                          /\/classrooms?\/\d+\/tests\/[^/?#]+\/start\/?(?:[?#]|$)/.test(href) ||
                          /\/practise\/[^/?#]+/.test(href);
      if(!isTestStart) return;

      e.preventDefault();
      e.stopImmediatePropagation();
      this.open(href);
    },true);
  }

  currentMode(){
    return this.modes.find(m=>m.id===this.state.mode) || this.subModes.find(m=>m.id===this.state.mode) || this.modes[0];
  }

  repaint(){
    const isSingle=this.state.mode.startsWith('single_');
    const parent=isSingle?'single_module':this.state.mode;
    this.el.querySelectorAll('.ptc-mode-card').forEach(c=>c.classList.toggle('is-active',c.dataset.id===parent));
    const sub=this.el.querySelector('#ptc-submodes');
    sub.style.display=isSingle?'block':'none';
    this.el.querySelectorAll('.ptc-submode-card').forEach(c=>c.classList.toggle('is-active',c.dataset.sub===this.state.mode));
    this.el.querySelectorAll('.ptc-integrity-card').forEach(c=>c.classList.toggle('is-active',c.dataset.integrity===this.state.integrity));
    this.el.querySelector('#ptc-total-time').textContent=this.fmt(this.currentMode().baseMin);
    this.el.querySelector('#ptc-protection').textContent=this.state.integrity.charAt(0).toUpperCase()+this.state.integrity.slice(1);
    const note=this.el.querySelector('#ptc-integrity-note');
    note.textContent=this.state.integrity==='off'
      ? 'Anti-Cheat is off. No strikes, fullscreen requirement or tab/app monitoring.'
      : this.state.integrity==='strict'
        ? 'Strict adds copy/paste, right-click and restricted shortcut protection.'
        : 'Standard uses the 3-strike system and monitors tab/app switching, inactivity and fullscreen exit.';
  }

  open(href){
    this.state.targetHref=href;
    this.state.mode='full_test';
    try{
      const saved=localStorage.getItem('makonbook:practice-integrity-mode');
      this.state.integrity=['off','standard','strict'].includes(saved)?saved:'standard';
    }catch(_e){this.state.integrity='standard';}
    this.repaint();
    this.el.classList.add('is-open');
  }

  close(){ this.el.classList.remove('is-open'); }

  continue(){
    if(!this.state.targetHref) return;
    const url=new URL(this.state.targetHref,window.location.href);
    url.searchParams.set('configured','1');
    url.searchParams.set('test_mode',this.state.mode);
    url.searchParams.set('integrity_mode',this.state.integrity);
    url.searchParams.set('integrity_max_violations','3');
    url.searchParams.set('integrity_fullscreen_required',this.state.integrity==='off'?'0':'1');
    window.location.href=url.toString();
  }
}

document.addEventListener('DOMContentLoaded',()=>{ window.MakonBookPreTestConfigV5415=new MakonBookPreTestConfigV5415(); });
