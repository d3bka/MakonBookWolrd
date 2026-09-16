(()=>{
  const root=document.querySelector('[data-vocab-home]');
  if(!root)return;
  const dialog=root.querySelector('[data-vocab-deck-dialog]');
  const title=root.querySelector('[data-mode-title]');
  const kicker=root.querySelector('[data-mode-kicker]');
  const choices=[...root.querySelectorAll('[data-vocab-deck-choice]')];
  const config={
    memory:['Memory Layers','memoryUrl'],
    animated:['Animated Immersion','animatedUrl'],
    bounce:['Word Bounce','bounceUrl'],
    visual:['Visual Match','visualUrl'],
  };
  function openMode(mode){
    const item=config[mode]||config.memory;
    if(title) title.textContent=`Choose a deck for ${item[0]}`;
    if(kicker) kicker.textContent=item[0];
    choices.forEach(link=>{link.href=link.dataset[item[1]]||'#';});
    if(dialog?.showModal) dialog.showModal();
  }
  root.querySelectorAll('[data-vocab-mode]').forEach(btn=>btn.addEventListener('click',()=>openMode(btn.dataset.vocabMode)));
  root.querySelectorAll('[data-vocab-dialog-close]').forEach(btn=>btn.addEventListener('click',()=>dialog?.close()));
  dialog?.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
})();
