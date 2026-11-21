(function(){
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const csrf=()=>(document.cookie.match(/csrftoken=([^;]+)/)||[])[1]||($('input[name=csrfmiddlewaretoken]')||{}).value;
const inr=n=>'₹'+Number(n).toLocaleString('en-IN',{maximumFractionDigits:0});
window.FTinr=inr;
function toast(msg,type='info'){const t=document.createElement('div');t.className='toast '+type;t.textContent=msg;$('#toasts').appendChild(t);setTimeout(()=>t.remove(),4000)}
$$('[data-toast]').forEach(e=>toast(e.textContent.trim(),e.dataset.toast));
// sheets
const open=id=>{const s=document.getElementById(id);if(s){s.classList.add('open');document.body.style.overflow='hidden'}};
const closeAll=()=>{$$('.sheet.open').forEach(s=>s.classList.remove('open'));document.body.style.overflow=''};
document.addEventListener('click',e=>{
 const o=e.target.closest('[data-open]');if(o){closeAll();open(o.dataset.open);if(o.dataset.open==='chat')startChat();return}
 if(e.target.closest('[data-open-tx]')){openTx();return}
 if(e.target.closest('[data-close]'))closeAll();
 const ed=e.target.closest('[data-edit]');if(ed)openTx(ed.dataset);
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeAll()});
function filterChips(){const k=($('#tx-form [name=kind]:checked')||{}).value;$$('#tx-form .chip').forEach(c=>{c.style.display=c.dataset.kind===k?'':'none';const i=$('input',c);if(c.style.display==='none'&&i.checked)i.checked=false})}
function openTx(d){const f=$('#tx-form');if(!f)return;f.reset();
 const today=new Date(Date.now()-new Date().getTimezoneOffset()*6e4).toISOString().slice(0,10);
 f.action=d&&d.url?d.url:f.dataset.createUrl||f.getAttribute('action');if(!f.dataset.createUrl)f.dataset.createUrl=f.getAttribute('action');
 $('#tx-title').textContent=d&&d.url?'Edit transaction':'Add transaction';f.date.value=(d&&d.date)||today;
 if(d&&d.url){f.kind.value=d.kind;f.amount.value=d.amount;f.note.value=d.note||'';filterChips();const r=$(`[name=category][value="${d.cat}"]`,f);if(r)r.checked=true}else{filterChips()}
 closeAll();open('sheet-tx');setTimeout(()=>f.amount.focus(),100)}
$$('#tx-form [name=kind]').forEach(r=>r.addEventListener('change',filterChips));
// double-submit protection
$$('form[data-loading]').forEach(f=>f.addEventListener('submit',()=>{const b=$('button:not([type=button])',f);if(b){setTimeout(()=>{b.disabled=true;b.textContent='Please wait…'},0)}}));
document.addEventListener('submit',e=>{const f=e.target;if(f.dataset.confirm&&!confirm(f.dataset.confirm))e.preventDefault()});
// theme + privacy
const root=document.documentElement;
$('#theme-btn')&&$('#theme-btn').addEventListener('click',()=>{const t=root.dataset.theme==='dark'?'light':'dark';root.dataset.theme=t;localStorage.setItem('theme',t)});
$('#privacy-btn')&&$('#privacy-btn').addEventListener('click',()=>{const on=root.classList.toggle('privacy');localStorage.setItem('privacy',on?'1':'0')});
// greeting
$$('[data-greeting]').forEach(e=>{const h=new Date().getHours();e.textContent=(h<12?'Good morning':h<17?'Good afternoon':'Good evening')+', '+e.dataset.greeting+' 👋'});
// banner dismiss
$$('[data-dismiss]').forEach(b=>{const k='dismiss-'+b.dataset.dismiss;const box=b.closest('.banner');if(localStorage.getItem(k))box.remove();b.addEventListener('click',()=>{localStorage.setItem(k,'1');box.remove()})});
// password toggle + strength
$$('[data-pw-toggle]').forEach(b=>b.addEventListener('click',()=>{const i=b.parentNode.querySelector('input');i.type=i.type==='password'?'text':'password'}));
const pwi=$('[data-strength]');if(pwi){const bar=$('.strength i');pwi.addEventListener('input',()=>{const v=pwi.value;let s=0;if(v.length>=8)s++;if(/[A-Z]/.test(v)&&/[a-z]/.test(v))s++;if(/\d/.test(v))s++;if(/[^A-Za-z0-9]/.test(v)||v.length>=12)s++;bar.style.width=(s*25)+'%';bar.style.background=['#F43F5E','#F43F5E','#F59E0B','#10B981','#10B981'][s]})}
// auto-submit filters
$$('[data-autosubmit]').forEach(e=>e.addEventListener('change',()=>e.form.submit()));
// count-up
$$('[data-count]').forEach(el=>{const to=parseFloat(el.dataset.count);if(!isFinite(to)||matchMedia('(prefers-reduced-motion:reduce)').matches)return;const t0=performance.now();(function f(t){const p=Math.min((t-t0)/700,1);el.textContent=inr(to*(1-Math.pow(1-p,3)));if(p<1)requestAnimationFrame(f)})(t0)});
// charts
function chartDefaults(){if(!window.Chart)return;const dark=root.dataset.theme==='dark';Chart.defaults.font.family='"DM Sans",system-ui,sans-serif';Chart.defaults.color=dark?'#9C99B5':'#6B7280';Chart.defaults.borderColor=dark?'#2B2940':'#EEEDF6'}
window.FTchart=function(id,cfg){const el=document.getElementById(id);if(!el||!window.Chart)return;chartDefaults();
 cfg.options=Object.assign({responsive:true,maintainAspectRatio:false},cfg.options||{});return new Chart(el,cfg)};
window.FTcommon={tooltip:{callbacks:{label:c=>' '+(c.dataset.label?c.dataset.label+': ':c.label+': ')+inr(c.parsed.y!==undefined?c.parsed.y:c.parsed)}}};
// chat
let started=false;const msgs=$('#msgs');
function esc(s){return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function fmt(s){return esc(s).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\n/g,'<br>')}
function time(){return new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}
function bubble(html,me){const d=document.createElement('div');d.className='msg'+(me?' me':'');d.innerHTML=html+'<time>'+time()+'</time>';msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight;return d}
function startChat(){if(!msgs||started)return;started=true;bubble('Hi '+esc(FT.first)+'! Ask me about your expenses, savings or budgets, or add one by typing <b>Spent 250 on lunch</b>.')}
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(body)});return r.json()}
async function send(text){text=(text||'').trim();if(!text)return;bubble(esc(text),true);$('#chat-input').value='';
 const t=document.createElement('div');t.className='msg typing';t.innerHTML='<i></i><i></i><i></i>';msgs.appendChild(t);msgs.scrollTop=msgs.scrollHeight;
 try{const d=await post(FT.chatUrl,{message:text});t.remove();bubble(fmt(d.reply));if(d.type==='confirm')confirmCard(d.draft)}catch(e){t.remove();bubble('Something went wrong. Please try again.')}}
function confirmCard(d){const c=document.createElement('div');c.className='confirm';
 c.innerHTML=`<b style="font-size:20px" class="${d.kind==='income'?'plus':'minus'}">${d.kind==='income'?'+':'-'}${inr(d.amount)}</b><br><span>${esc(d.category_name)} · ${esc(d.date)}</span>${d.note?'<br><small>'+esc(d.note)+'</small>':''}<div class="btns"><button class="btn btn-primary" data-y>Confirm</button><button class="btn" data-n>Cancel</button></div>`;
 msgs.appendChild(c);msgs.scrollTop=msgs.scrollHeight;
 $('[data-n]',c).onclick=()=>{c.remove();bubble('Cancelled.')};
 $('[data-y]',c).onclick=async()=>{c.querySelector('[data-y]').disabled=true;const r=await post(FT.confirmUrl,d);c.remove();bubble(esc(r.reply));if(r.ok)toast('Transaction added ✓','success')}}
if($('#chat-send')){$('#chat-send').onclick=()=>send($('#chat-input').value);$('#chat-input').addEventListener('keydown',e=>{if(e.key==='Enter')send(e.target.value)});
 $$('#chat-chips [data-q]').forEach(b=>b.onclick=()=>send(b.dataset.q));
 $('#chat-clear').onclick=()=>{msgs.innerHTML='';started=false;startChat()};
 const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(SR){const m=$('#mic-btn');m.hidden=false;const rec=new SR();rec.lang='en-IN';rec.onresult=e=>{$('#chat-input').value=e.results[0][0].transcript;send($('#chat-input').value)};rec.onend=()=>m.style.color='';m.onclick=()=>{m.style.color='var(--expense)';rec.start()}}}
if('serviceWorker'in navigator&&location.protocol==='https:')navigator.serviceWorker.register('/sw.js').catch(()=>{});
})();
