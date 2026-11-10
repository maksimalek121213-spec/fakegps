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

// Scroll progress + cinematic 3D phone movement while scrolling.
const progressBar = $('#scrollProgress');
const heroArt = $('#heroArt');
const phone = $('#phoneWrap');
let pointerTilt = { x: 0, y: 0 };
let scrollTicking = false;
function updateScrollScene() {
  const maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
  if (progressBar) progressBar.style.transform = `scaleX(${window.scrollY / maxScroll})`;
  if (phone && heroArt) {
    const rect = heroArt.getBoundingClientRect();
    const heroTop = rect.top + window.scrollY;
    const travelled = Math.max(0, Math.min(1, (window.scrollY - (heroTop - window.innerHeight * 0.15)) / (window.innerHeight * 0.9)));
    const rotateY = -17 + travelled * 37 + pointerTilt.x * (1 - travelled) * 10;
    const rotateX = 7 - travelled * 14 - pointerTilt.y * (1 - travelled) * 7;
    const rotateZ = 3 - travelled * 10 + pointerTilt.x * (1 - travelled) * 2;
    const moveY = -travelled * 58 - pointerTilt.y * (1 - travelled) * 7;
    const scale = 1 - travelled * 0.13;
    phone.style.transform = `translate3d(0,${moveY}px,0) rotateY(${rotateY}deg) rotateX(${rotateX}deg) rotateZ(${rotateZ}deg) scale(${scale})`;
    phone.style.opacity = String(1 - travelled * 0.23);
  }
  scrollTicking = false;
}
window.addEventListener('scroll', () => {
  if (!scrollTicking) { requestAnimationFrame(updateScrollScene); scrollTicking = true; }
}, { passive: true });
window.addEventListener('resize', updateScrollScene, { passive: true });
if (heroArt && phone && window.matchMedia('(pointer:fine)').matches) {
  heroArt.addEventListener('pointermove', e => {
    const r = heroArt.getBoundingClientRect();
    pointerTilt.x = (e.clientX - r.left) / r.width - .5;
    pointerTilt.y = (e.clientY - r.top) / r.height - .5;
    updateScrollScene();
  });
  heroArt.addEventListener('pointerleave', () => { pointerTilt = {x:0,y:0}; updateScrollScene(); });
}
updateScrollScene();

// Real interactive OpenStreetMap of Ukraine. The page demo does not alter device GPS.
const places = {
  odesa:   { name: 'Одесса, Украина',    coords: [46.4825, 30.7233], zoom: 13 },
  kyiv:    { name: 'Киев, Украина',      coords: [50.4501, 30.5234], zoom: 12 },
  lviv:    { name: 'Львов, Украина',      coords: [49.8397, 24.0297], zoom: 13 },
  kharkiv: { name: 'Харьков, Украина',   coords: [49.9935, 36.2304], zoom: 13 },
  dnipro:  { name: 'Днепр, Украина',     coords: [48.4647, 35.0462], zoom: 13 }
};
let map = null;
let marker = null;
let selectedPlaceKey = 'odesa';
let selectedPoint = places.odesa.coords;
const ukraineBounds = typeof L !== 'undefined' ? L.latLngBounds([[44.0, 21.0], [53.0, 40.5]]) : null;

function formatCoord(value, positive, negative) {
  return `${Math.abs(value).toFixed(5)}° ${value >= 0 ? positive : negative}`;
}
function updateSelectedPoint(latlng, placeName = 'Выбранная точка') {
  selectedPoint = [latlng.lat, latlng.lng];
  const cityName = $('#cityName');
  const lat = $('#lat');
  const lon = $('#lon');
  if (cityName) cityName.textContent = placeName;
  if (lat) lat.textContent = formatCoord(latlng.lat, 'N', 'S');
  if (lon) lon.textContent = formatCoord(latlng.lng, 'E', 'W');
  const state = $('#mapState');
  if (state) state.textContent = `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`;
  $$('.city').forEach(button => button.classList.toggle('active', button.dataset.city === selectedPlaceKey && placeName === places[selectedPlaceKey]?.name));
}
function moveMarker(latlng, placeName) {
  if (!map || !marker) return;
  marker.setLatLng(latlng);
  updateSelectedPoint(latlng, placeName);
}
function chooseCity(key) {
  const place = places[key];
  if (!place || !map || !marker) return;
  selectedPlaceKey = key;
  const target = L.latLng(place.coords[0], place.coords[1]);
  map.flyTo(target, place.zoom, { animate: true, duration: 1.15, easeLinearity: 0.22 });
  moveMarker(target, place.name);
  $$('.city').forEach(button => button.classList.toggle('active', button.dataset.city === key));
}
function initUkraineMap() {
  const mapNode = $('#ukraineMap');
  if (!mapNode) return;
  if (typeof L === 'undefined') {
    mapNode.innerHTML = '<div class="map-error"><b>Не удалось загрузить карту</b><span>Проверь интернет и обнови страницу. Карта использует OpenStreetMap.</span></div>';
    return;
  }
  map = L.map(mapNode, {
    zoomControl: false,
    scrollWheelZoom: false,
    tap: true,
    zoomAnimation: true,
    markerZoomAnimation: true,
    preferCanvas: true
  });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'
  }).addTo(map);
  L.control.zoom({ position: 'bottomright' }).addTo(map);
  const markerIcon = L.divIcon({
    className: 'fakegps-marker-wrap',
    html: '<div class="fakegps-marker"><span></span><i></i></div>',
    iconSize: [34, 44],
    iconAnchor: [17, 38]
  });
  marker = L.marker(places.odesa.coords, { icon: markerIcon, draggable: true, autoPan: true }).addTo(map);
  marker.on('dragend', () => {
    const point = marker.getLatLng();
    selectedPlaceKey = null;
    moveMarker(point, 'Выбранная точка');
    $$('.city').forEach(button => button.classList.remove('active'));
  });
  map.on('click', event => {
    selectedPlaceKey = null;
    moveMarker(event.latlng, 'Выбранная точка');
    $$('.city').forEach(button => button.classList.remove('active'));
  });
  map.fitBounds(ukraineBounds, { padding: [16, 16], animate: false });
  // Start with the whole country visible; city buttons zoom into their exact coordinates.
  updateSelectedPoint(L.latLng(places.odesa.coords[0], places.odesa.coords[1]), places.odesa.name);
  setTimeout(() => map.invalidateSize(), 120);
  window.addEventListener('resize', () => map?.invalidateSize(), { passive: true });
}
$$('.city').forEach(button => button.addEventListener('click', () => chooseCity(button.dataset.city)));
$('#resetMap')?.addEventListener('click', () => {
  if (!map) return;
  selectedPlaceKey = null;
  map.flyToBounds(ukraineBounds, { padding: [16, 16], duration: 1.1 });
  $$('.city').forEach(button => button.classList.remove('active'));
});
initUkraineMap();

// Accessible, smoothly animated FAQ accordion.
$$('.faq-question').forEach(button => button.addEventListener('click', () => {
  const item = button.closest('.faq-item');
  const wasOpen = item.classList.contains('open');
  $$('.faq-item').forEach(other => {
    other.classList.remove('open');
    $('.faq-question', other).setAttribute('aria-expanded', 'false');
    $('.faq-question b', other).textContent = '＋';
  });
  if (!wasOpen) {
    item.classList.add('open');
    button.setAttribute('aria-expanded', 'true');
    $('b', button).textContent = '−';
  }
}));

// Small tactile response for all buttons and in-page links.
$$('button, .btn, .link-btn, .nav a').forEach(control => {
  control.addEventListener('pointerdown', () => control.classList.add('is-pressed'));
  ['pointerup', 'pointerleave', 'pointercancel'].forEach(type => control.addEventListener(type, () => control.classList.remove('is-pressed')));
});
