(()=>{
  const root=document.querySelector('[data-vocab-home]');
  if(!root)return;

  const reduceMotion=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const dialog=root.querySelector('[data-vocab-deck-dialog]');
  const title=root.querySelector('[data-mode-title]');
  const kicker=root.querySelector('[data-mode-kicker]');
  const choices=[...root.querySelectorAll('[data-vocab-deck-choice]')];
  const config={
    memory:['Memory Layers','memoryUrl'],
    animated:['Animated Immersion','animatedUrl'],
    bounce:['Word Bounce','bounceUrl'],
    meaning:['Meaning Match','meaningUrl'],
  };

  function restartClass(el,className,duration=220){
    if(!el)return;
    el.classList.remove(className);
    void el.offsetWidth;
    el.classList.add(className);
    window.setTimeout(()=>el.classList.remove(className),duration);
  }

  function tap(el){
    restartClass(el,'is-pressed',190);
  }

  function closeDialog(animated=true){
    if(!dialog?.open)return;
    const card=dialog.querySelector('.vh506-dialog-card');
    if(!animated||reduceMotion){dialog.close();return;}
    card?.classList.remove('is-opening');
    card?.classList.add('is-closing');
    window.setTimeout(()=>{
      card?.classList.remove('is-closing');
      if(dialog.open)dialog.close();
    },150);
  }

  function openMode(mode,trigger){
    tap(trigger);
    restartClass(trigger,'is-launching',300);
    const item=config[mode]||config.memory;
    if(title)title.textContent=`Choose a deck for ${item[0]}`;
    if(kicker)kicker.textContent=item[0];
    choices.forEach(link=>{
      link.href=link.dataset[item[1]]||'#';
      link.classList.remove('is-cascading');
    });
    if(!dialog?.showModal)return;

    const card=dialog.querySelector('.vh506-dialog-card');
    card?.classList.remove('is-opening','is-closing');
    dialog.showModal();
    requestAnimationFrame(()=>{
      card?.classList.add('is-opening');
      choices.forEach(link=>link.classList.add('is-cascading'));
      window.setTimeout(()=>{
        card?.classList.remove('is-opening');
        choices.forEach(link=>link.classList.remove('is-cascading'));
      },430);
    });
  }

  root.querySelectorAll('[data-vocab-mode]').forEach(btn=>{
    btn.addEventListener('click',()=>openMode(btn.dataset.vocabMode,btn));
  });
  root.querySelectorAll('[data-vocab-dialog-close]').forEach(btn=>{
    btn.addEventListener('click',()=>{tap(btn);closeDialog(true);});
  });
  dialog?.addEventListener('click',event=>{if(event.target===dialog)closeDialog(true);});
  dialog?.addEventListener('cancel',event=>{event.preventDefault();closeDialog(true);});

  // V50.1.11 — personal deck carousel. The DOM is already fully rendered, so
  // switching decks is instant and does not involve a network request.
  const carousel=root.querySelector('[data-deck-carousel]');
  if(carousel){
    const slides=[...carousel.querySelectorAll('[data-deck-slide]')];
    const dots=[...carousel.querySelectorAll('[data-deck-dot]')];
    const prev=carousel.querySelector('[data-deck-prev]');
    const next=carousel.querySelector('[data-deck-next]');
    let active=Math.max(0,slides.findIndex(slide=>slide.classList.contains('is-active')));
    let timer=null;

    function setSlide(index,direction='next',manual=false){
      if(slides.length<2)return;
      const normalized=(index+slides.length)%slides.length;
      if(normalized===active)return;
      const old=slides[active];
      const incoming=slides[normalized];
      old?.classList.remove('is-active','from-next','from-prev');
      old?.setAttribute('aria-hidden','true');
      incoming?.classList.remove('from-next','from-prev');
      incoming?.classList.add('is-active',direction==='prev'?'from-prev':'from-next');
      incoming?.setAttribute('aria-hidden','false');
      dots.forEach((dot,i)=>{
        const on=i===normalized;
        dot.classList.toggle('is-active',on);
        dot.setAttribute('aria-current',on?'true':'false');
      });
      active=normalized;
      if(manual)restartAuto();
      window.setTimeout(()=>incoming?.classList.remove('from-next','from-prev'),360);
    }

    function stopAuto(){
      if(timer){window.clearInterval(timer);timer=null;}
    }
    function startAuto(){
      if(reduceMotion||slides.length<2||timer)return;
      timer=window.setInterval(()=>setSlide(active+1,'next',false),7000);
    }
    function restartAuto(){stopAuto();startAuto();}

    prev?.addEventListener('click',()=>{tap(prev);setSlide(active-1,'prev',true);});
    next?.addEventListener('click',()=>{tap(next);setSlide(active+1,'next',true);});
    dots.forEach((dot,index)=>dot.addEventListener('click',()=>{
      tap(dot);
      setSlide(index,index<active?'prev':'next',true);
    }));
    carousel.addEventListener('mouseenter',stopAuto);
    carousel.addEventListener('mouseleave',startAuto);
    carousel.addEventListener('focusin',stopAuto);
    carousel.addEventListener('focusout',event=>{
      if(!carousel.contains(event.relatedTarget))startAuto();
    });
    document.addEventListener('visibilitychange',()=>document.hidden?stopAuto():startAuto());
    startAuto();
  }
})();
