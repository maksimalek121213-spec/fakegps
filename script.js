const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];

// Mobile navigation
const burger = $('#burger');
const nav = $('#nav');
burger?.addEventListener('click', () => {
  const open = nav.classList.toggle('open');
  burger.setAttribute('aria-expanded', String(open));
});
$$('#nav a').forEach(a => a.addEventListener('click', () => {
  nav.classList.remove('open');
  burger?.setAttribute('aria-expanded', 'false');
}));

// Scroll reveal
const revealNodes = $$('.reveal');
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add('visible'); obs.unobserve(entry.target); }
    });
  }, { threshold: 0.12 });
  revealNodes.forEach(node => observer.observe(node));
} else revealNodes.forEach(node => node.classList.add('visible'));

// Mouse-driven 3D phone tilt on desktop
const art = $('#heroArt'), phone = $('#phoneWrap');
if (art && phone && matchMedia('(pointer:fine)').matches) {
  art.addEventListener('pointermove', e => {
    const r = art.getBoundingClientRect(), x = (e.clientX-r.left)/r.width-.5, y = (e.clientY-r.top)/r.height-.5;
    phone.style.animation = 'none';
    phone.style.transform = `rotateY(${-17+x*18}deg) rotateX(${7-y*12}deg) rotateZ(${3+x*3}deg) translateY(${-y*8}px)`;
  });
  art.addEventListener('pointerleave', () => { phone.style.animation = ''; phone.style.transform = ''; });
}

// Interactive location preview. It is only a visual demo: no device location APIs are used.
const locations = {
  odesa: { name:'Одесса, Украина', lat:'46.4825° N', lon:'30.7233° E', x:51, y:46 },
  kyiv:  { name:'Киев, Украина', lat:'50.4501° N', lon:'30.5234° E', x:63, y:34 },
  lviv:  { name:'Львов, Украина', lat:'49.8397° N', lon:'24.0297° E', x:38, y:58 }
};
function chooseCity(key) {
  const p = locations[key]; if (!p) return;
  $('#cityName').textContent = p.name; $('#lat').textContent = p.lat; $('#lon').textContent = p.lon;
  $('#demoPin').style.left = p.x+'%'; $('#demoPin').style.top = p.y+'%';
  $$('.city').forEach(b => b.classList.toggle('active', b.dataset.city === key));
}
$$('.city').forEach(b => b.addEventListener('click', () => chooseCity(b.dataset.city)));
$('#newPoint')?.addEventListener('click', () => {
  const pin = $('#demoPin'); pin.style.left = (23+Math.random()*54)+'%'; pin.style.top = (23+Math.random()*54)+'%';
  pin.animate([{filter:'brightness(1)'},{filter:'brightness(1.8)'},{filter:'brightness(1)'}], {duration:650});
});
let zoom = 1;
$('#zoomIn')?.addEventListener('click', () => { zoom = Math.min(1.28, zoom+.08); $('#demoMap').style.filter = `saturate(${zoom}) brightness(${1+(zoom-1)*.28})`; });
$('#zoomOut')?.addEventListener('click', () => { zoom = Math.max(.8, zoom-.08); $('#demoMap').style.filter = `saturate(${zoom}) brightness(${1+(zoom-1)*.28})`; });

// Accessible FAQ accordion
$$('.faq-question').forEach(button => button.addEventListener('click', () => {
  const item = button.closest('.faq-item'), wasOpen = item.classList.contains('open');
  $$('.faq-item').forEach(other => { other.classList.remove('open'); $('.faq-question', other).setAttribute('aria-expanded','false'); $('.faq-question b', other).textContent='＋'; });
  if (!wasOpen) { item.classList.add('open'); button.setAttribute('aria-expanded','true'); $('b',button).textContent='−'; }
}));
