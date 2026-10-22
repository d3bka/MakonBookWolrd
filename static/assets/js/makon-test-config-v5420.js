class MakonBookPreTestConfigV5420 {
  constructor() {
    this.modes = [
      { id:'full_test', title:'Full Test', desc:'All modules (RW + Math)', icon:'bi-bullseye' },
      { id:'rw_only', title:'English Only', desc:'Both Reading & Writing modules', icon:'bi-book' },
      { id:'math_only', title:'Math Only', desc:'Both Math modules', icon:'bi-calculator' },
      { id:'single_module', title:'Single Module', desc:'Practice exactly one module', icon:'bi-lightning-charge' }
    ];
    this.subModes = [
      { id:'single_english_m1', title:'English M1' },
      { id:'single_english_m2', title:'English M2' },
      { id:'single_math_m1', title:'Math M1' },
      { id:'single_math_m2', title:'Math M2' }
    ];
    this.integrityModes = [
      { id:'off', title:'Off', desc:'No Anti-Cheat monitoring.' },
      { id:'standard', title:'Standard', desc:'3 strikes, tab/app, inactivity and fullscreen monitoring.' },
      { id:'strict', title:'Strict', desc:'Standard + copy/paste, right-click and shortcut protection.' }
    ];
    this.state = {
      mode:'full_test', integrity:'standard',
      integrityLocked:false, integrityMax:3, integrityFullscreen:true,
      targetHref:null, targetLink:null, stats:{}
    };
    this.build();
    this.bind();
  }

  fmt(min){
    min=Number(min||0);
    if(min<=0) return 'Unavailable';
    if(min<60) return `${min} min`;
    const h=Math.floor(min/60),m=min%60;
    return m?`${h}h ${m}min`:`${h}h`;
  }

  stat(mode){ return this.state.stats[mode] || {q:0,min:0}; }

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
                <div class="ptc-badge" data-mode-badge="${m.id}">—</div>
              </div>
            </div>`).join('')}
        </div>

        <div class="ptc-submode-container" id="ptc-submodes" style="display:none;margin-top:12px;">
          <div class="ptc-submode-grid">
            ${this.subModes.map(sm=>`<div class="ptc-submode-card" data-sub="${sm.id}">${sm.title}<small data-sub-stat="${sm.id}"></small></div>`).join('')}
          </div>
        </div>

        <div class="ptc-section-title">Exam Integrity</div>
        <div class="ptc-integrity-grid">
          ${this.integrityModes.map((m,i)=>`
            <div class="ptc-integrity-card ${i===1?'is-active':''}" data-integrity="${m.id}">
              <strong>${m.title}</strong><span>${m.desc}</span>
            </div>`).join('')}
        </div>
        <div class="ptc-integrity-note" id="ptc-integrity-note"></div>

        <div class="ptc-summary">
          <div><div class="ptc-summary-label">Estimated Duration</div><div class="ptc-summary-val" id="ptc-total-time">—</div></div>
          <div style="text-align:center;"><div class="ptc-summary-label">Questions</div><div class="ptc-summary-val" id="ptc-total-questions" style="font-size:1.1rem;font-weight:600;">—</div></div>
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
    this.el.addEventListener('click',e=>{if(e.target===this.el)this.close()});
    this.el.querySelector('#ptc-btn-cancel').addEventListener('click',()=>this.close());

    this.el.querySelectorAll('.ptc-mode-card').forEach(card=>card.addEventListener('click',()=>{
      if(card.classList.contains('is-disabled')) return;
      const id=card.dataset.id;
      this.state.mode=id==='single_module'?'single_english_m1':id;
      this.repaint();
    }));

    this.el.querySelectorAll('.ptc-submode-card').forEach(card=>card.addEventListener('click',()=>{
      if(card.classList.contains('is-disabled')) return;
      if(this.state.mode.startsWith('single_')){
        this.state.mode=card.dataset.sub;
        this.repaint();
      }
    }));

    this.el.querySelectorAll('.ptc-integrity-card').forEach(card=>card.addEventListener('click',()=>{
      if(this.state.integrityLocked || card.classList.contains('is-disabled')) return;
      this.state.integrity=card.dataset.integrity||'standard';
      try{localStorage.setItem('makonbook:practice-integrity-mode',this.state.integrity)}catch(_e){}
      this.repaint();
    }));

    this.el.querySelector('#ptc-btn-start').addEventListener('click',()=>this.continue());

    document.addEventListener('click',e=>{
      const link=e.target.closest('.practice-action[data-practice-navigate]');
      if(!link) return;
      const card=link.closest('.practice-test-card');
      const fresh=!!(card&&card.querySelector('.practice-progress-note.is-ready'));
      const href=link.getAttribute('href')||'';
      if(!fresh||href.includes('/teacher/'))return;
      const isTestStart=/\/tests\/[^/?#]+\/start\/?(?:[?#]|$)/.test(href)||
                        /\/classrooms?\/\d+\/tests\/[^/?#]+\/start\/?(?:[?#]|$)/.test(href)||
                        /\/practise\/[^/?#]+/.test(href);
      if(!isTestStart)return;
      e.preventDefault();
      e.stopImmediatePropagation();
      this.open(link);
    },true);
  }

  readStats(link){
    const d=link.dataset;
    return {
      full_test:{q:+d.preconfigFullQ||0,min:+d.preconfigFullMin||0},
      rw_only:{q:+d.preconfigRwQ||0,min:+d.preconfigRwMin||0},
      math_only:{q:+d.preconfigMathQ||0,min:+d.preconfigMathMin||0},
      single_english_m1:{q:+d.preconfigEnglishM1Q||0,min:+d.preconfigEnglishM1Min||0},
      single_english_m2:{q:+d.preconfigEnglishM2Q||0,min:+d.preconfigEnglishM2Min||0},
      single_math_m1:{q:+d.preconfigMathM1Q||0,min:+d.preconfigMathM1Min||0},
      single_math_m2:{q:+d.preconfigMathM2Q||0,min:+d.preconfigMathM2Min||0}
    };
  }

  repaint(){
    const isSingle=this.state.mode.startsWith('single_');
    const parent=isSingle?'single_module':this.state.mode;

    this.el.querySelectorAll('.ptc-mode-card').forEach(c=>{
      const id=c.dataset.id;
      c.classList.toggle('is-active',id===parent);
      if(id!=='single_module'){
        c.classList.toggle('is-disabled',!this.stat(id).q);
      }
    });

    const sub=this.el.querySelector('#ptc-submodes');
    sub.style.display=isSingle?'block':'none';
    this.el.querySelectorAll('.ptc-submode-card').forEach(c=>{
      const s=this.stat(c.dataset.sub);
      c.classList.toggle('is-active',c.dataset.sub===this.state.mode);
      c.classList.toggle('is-disabled',!s.q);
      const small=c.querySelector('small');
      if(small)small.textContent=s.q?`${s.q} Q · ${this.fmt(s.min)}`:'Unavailable';
    });

    const singleAvailable=this.subModes.some(sm=>this.stat(sm.id).q>0);
    const singleCard=this.el.querySelector('.ptc-mode-card[data-id="single_module"]');
    if(singleCard)singleCard.classList.toggle('is-disabled',!singleAvailable);

    const badgeMap={
      full_test:'full_test',
      rw_only:'rw_only',
      math_only:'math_only',
      single_module:this.state.mode.startsWith('single_')?this.state.mode:'single_english_m1'
    };
    Object.keys(badgeMap).forEach(key=>{
      const node=this.el.querySelector(`[data-mode-badge="${key}"]`);
      if(!node)return;
      const s=this.stat(badgeMap[key]);
      node.textContent=s.q?this.fmt(s.min):'Unavailable';
    });

    this.el.querySelectorAll('.ptc-integrity-card').forEach(c=>{
      c.classList.toggle('is-active',c.dataset.integrity===this.state.integrity);
      c.classList.toggle('is-disabled',this.state.integrityLocked&&c.dataset.integrity!==this.state.integrity);
    });

    const current=this.stat(this.state.mode);
    this.el.querySelector('#ptc-total-time').textContent=this.fmt(current.min);
    this.el.querySelector('#ptc-total-questions').textContent=current.q?String(current.q):'—';
    this.el.querySelector('#ptc-protection').textContent=this.state.integrity.charAt(0).toUpperCase()+this.state.integrity.slice(1);

    const note=this.el.querySelector('#ptc-integrity-note');
    if(this.state.integrityLocked){
      note.textContent=`Managed by teacher. This classroom test will use ${this.state.integrity.charAt(0).toUpperCase()+this.state.integrity.slice(1)} Anti-Cheat. Other protection modes are locked for this attempt.`;
    }else if(this.state.integrity==='off'){
      note.textContent='Anti-Cheat is off. No strikes, fullscreen requirement or tab/app monitoring.';
    }else if(this.state.integrity==='strict'){
      note.textContent='Strict adds copy/paste, right-click and restricted shortcut protection.';
    }else{
      note.textContent='Standard uses the strike system and monitors tab/app switching, inactivity and fullscreen exit.';
    }
  }

  open(link){
    this.state.targetLink=link;
    this.state.targetHref=link.getAttribute('href')||'';
    this.state.stats=this.readStats(link);
    this.state.mode='full_test';

    const isClassroomStart =
      /\/classrooms?\/\d+\/tests\/[^/?#]+\/start\/?(?:[?#]|$)/.test(this.state.targetHref) ||
      /\/classroom\/\d+\/practice\/[^/?#]+\/start\/?(?:[?#]|$)/.test(this.state.targetHref);

    const declaredIntegrityMode=(link.dataset.preconfigIntegrityMode||'').trim().toLowerCase();
    const hasDeclaredClassroomPolicy=['off','standard','strict'].includes(declaredIntegrityMode);

    this.state.integrityLocked=link.dataset.preconfigIntegrityLocked==='1';
    this.state.integrityMax=+(link.dataset.preconfigIntegrityMax||3);
    this.state.integrityFullscreen=link.dataset.preconfigIntegrityFullscreen==='1';

    // Classroom tests are server-managed. If metadata is missing for any
    // reason, fail closed to the same Standard policy the backend uses instead
    // of visually allowing Off and then showing Standard on the cover.
    if(isClassroomStart && !hasDeclaredClassroomPolicy){
      this.state.integrityLocked=true;
      this.state.integrity='standard';
      this.state.integrityMax=3;
      this.state.integrityFullscreen=true;
    }else if(this.state.integrityLocked){
      this.state.integrity=declaredIntegrityMode||'standard';
    }else{
      try{
        const saved=localStorage.getItem('makonbook:practice-integrity-mode');
        this.state.integrity=['off','standard','strict'].includes(saved)?saved:'standard';
      }catch(_e){this.state.integrity='standard'}
    }

    if(!this.stat('full_test').q){
      const first=['rw_only','math_only','single_english_m1','single_english_m2','single_math_m1','single_math_m2']
        .find(mode=>this.stat(mode).q>0);
      if(first)this.state.mode=first;
    }

    this.repaint();
    this.el.classList.add('is-open');
  }

  close(){this.el.classList.remove('is-open')}

  continue(){
    if(!this.state.targetHref)return;
    const selected=this.stat(this.state.mode);
    if(!selected.q)return;

    const url=new URL(this.state.targetHref,window.location.href);
    url.searchParams.set('configured','1');
    url.searchParams.set('test_mode',this.state.mode);
    url.searchParams.set('integrity_mode',this.state.integrity);
    url.searchParams.set('integrity_max_violations',String(this.state.integrityMax||3));
    url.searchParams.set('integrity_fullscreen_required',this.state.integrityFullscreen?'1':'0');
    window.location.assign(url.toString());
  }
}
document.addEventListener('DOMContentLoaded',()=>{window.MakonBookPreTestConfigV5420=new MakonBookPreTestConfigV5420()});
