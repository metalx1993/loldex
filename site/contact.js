(function(){
  const form = document.getElementById('cf');
  const btn = document.getElementById('send');
  const result = document.getElementById('result');
  const bytes = v => new TextEncoder().encode(v).length;
  const fields = {
    name: v => v.trim().length > 0 && bytes(v) <= 120,
    email: v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()) && bytes(v) <= 254,
    message: v => bytes(v.trim()) >= 2 && bytes(v) <= 8000,
  };
  function showErr(name, on){
    const el = form.querySelector('.field-err[data-for="'+name+'"]');
    if(el) el.classList.toggle('show', on);
  }
  Object.keys(fields).forEach(name=>{
    form[name].addEventListener('input', ()=> showErr(name, false));
  });
  function setResult(kind, msg){
    result.className = 'result show ' + kind;
    result.textContent = msg;
  }
  form.addEventListener('submit', async (e)=>{
    e.preventDefault();
    result.className = 'result';
    let ok = true;
    for(const [name, test] of Object.entries(fields)){
      const valid = test(form[name].value);
      showErr(name, !valid);
      if(!valid) ok = false;
    }
    if(!ok) return;

    btn.disabled = true; btn.textContent = 'Sending…';
    try{
      const res = await fetch('./contact.php', {
        method:'POST',
        headers:{'Content-Type':'application/json', Accept:'application/json'},
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      const data = await res.json();
      if(data.success){
        setResult('ok', data.message || 'Message sent. Thanks — we\'ll get back to you.');
        form.reset();
      } else {
        setResult('err', data.message || 'Something went wrong. Please try again.');
      }
    }catch(err){
      setResult('err', 'Network error — please try again.');
    }finally{
      btn.disabled = false; btn.textContent = 'Send message';
    }
  });
})();
