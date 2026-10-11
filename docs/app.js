/* Wohnungssuche Basel – client app (no build step, vanilla JS). */
"use strict";

const LS = "basel-apt:v1:";
const store = {
  get(k, d) { try { const v = localStorage.getItem(LS + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(LS + k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
};

const FEATURES = {
  balcony: "Balcony", terrace: "Terrace", garden: "Garden", lift: "Elevator", parking: "Parking/garage",
  cellar: "Cellar/attic storage", new_build: "New build", renovated: "Renovated", view: "View",
  quiet: "Quiet", fireplace: "Fireplace", minergie: "Minergie/heat pump", own_laundry: "Own washing machine",
  accessible: "Step-free", two_bathrooms: "2+ bathrooms", storage: "Storage room", ground_floor: "Ground floor",
  near_transport: "Near public transport", family: "Family friendly", pets: "Pets ok",
};
const WARNINGS = { leasehold: "Leasehold (Baurecht)", investment_rented: "Rented out / investment", auction: "Auction", reserved: "Reserved / sold" };
const TYPES = { apartment: "Apartment", attic: "Attic/penthouse", maisonette: "Maisonette", loft: "Loft", garden_apartment: "Garden apartment", studio: "Studio" };
const CANTONS = { BS: "Basel-Stadt", BL: "Basel-Landschaft", "?": "Location unknown" };
const REF_POINTS = {
  "": ["– none –"],
  sbb: ["Basel SBB", 47.5476, 7.5897], bad: ["Badischer Bahnhof", 47.5672, 7.6075],
  markt: ["Marktplatz (old town)", 47.5582, 7.5878], messe: ["Messeplatz", 47.5634, 7.6008],
  roche: ["Roche (Grenzacherstrasse)", 47.5590, 7.6060], novartis: ["Novartis Campus", 47.5713, 7.5776],
  usb: ["University Hospital", 47.5617, 7.5833], uni: ["University (Petersplatz)", 47.5585, 7.5826],
  dreispitz: ["Dreispitz", 47.5378, 7.6082], liestal: ["Liestal station", 47.4844, 7.7313],
  custom: ["Custom point (click on map)"],
};
const MANUAL_LINKS = [
  ["Homegate – buy apartment, Basel-Stadt", "https://www.homegate.ch/kaufen/wohnung/kanton-baselstadt/trefferliste?o=dateCreated-desc"],
  ["Homegate – buy apartment, Basel-Landschaft", "https://www.homegate.ch/kaufen/wohnung/kanton-basellandschaft/trefferliste?o=dateCreated-desc"],
  ["ImmoScout24 – Basel-Stadt", "https://www.immoscout24.ch/de/wohnung/kaufen/kanton-basel-stadt?o=dateCreated-desc"],
  ["ImmoScout24 – Basel-Landschaft", "https://www.immoscout24.ch/de/wohnung/kaufen/kanton-basel-landschaft?o=dateCreated-desc"],
  ["Newhome (Kantonalbanken) – Basel-Stadt", "https://www.newhome.ch/de/kaufen/suchen/wohnung/kanton_basel-stadt/liste"],
  ["Newhome – Basel-Landschaft", "https://www.newhome.ch/de/kaufen/suchen/wohnung/kanton_basel-landschaft/liste"],
  ["Comparis – Basel", "https://www.comparis.ch/immobilien/marktplatz/basel/wohnung/kaufen"],
  ["RealAdvisor – Basel-Stadt", "https://realadvisor.ch/de/kaufen/kanton-basel-stadt/wohnung"],
  ["RealAdvisor – Basel-Landschaft", "https://realadvisor.ch/de/kaufen/kanton-basel-landschaft/wohnung"],
  ["Anibis – real estate", "https://www.anibis.ch/de/q/immobilien-wohnungen"],
  ["BLKB bank – properties & new builds", "https://www.blkb.ch/privatpersonen/finanzieren/finden-kaufen/liegenschaft-finden"],
  ["Team Lindenberger (Therwil)", "https://www.team-lindenberger.ch/de/kaufen/"],
  ["Kovacs Experience (Basel)", "https://www.kovacs-experience.ch/de/immobilie-kaufen"],
  ["Von Grafenstein Immobilien (Basel)", "https://vongrafenstein-immobilien.ch/portfolio/"],
  ["Albert & Partner (Basel)", "https://www.albertpartner.ch/angebote-immobilien-basel.html"],
  ["Litzius Immobilien (Arlesheim)", "https://litzius.ch/kaufobjekte/"],
  ["Swiss Life Immopulse", "https://www.swisslife.ch/de/private/immobilien-hypotheken/immobilien/objektangebot.html"],
  ["Engel & Völkers Basel-City", "https://www.engelvoelkers.com/ch/de/immobilien/res/kaufen/wohnung/basel-stadt"],
  ["Mobimo – current offers", "https://www.mobimo.ch/de/immobilien/aktuelle-angebote"],
  ["Implenia – apartments", "https://implenia.com/wohnungsangebot/"],
  ["Losinger Marazzi – Miete & Kauf", "https://losinger-marazzi.ch/de/misc/miete-und-kauf/"],
  ["Neho – Basel-Stadt", "https://neho.ch/de/zum-verkauf/wohnungen/kanton/basel-stadt"],
  ["RE/MAX – offices", "https://www.remax.ch/de/immobilienbueros"],
  ["Betterhomes – search", "https://www.betterhomes.ch/de/immobilien-kaufen"],
];

const DEFAULT_FILTERS = {
  q: "", qx: "", priceMin: "", priceMax: "", roomsMin: "", roomsMax: "", areaMin: "", areaMax: "",
  ppmMin: "", ppmMax: "", yearMin: "", yearMax: "", floorMin: "", floorMax: "", bathMin: "", includeMissing: true,
  cantons: [], districts: [], munis: [], zips: "", refPoint: "", maxKm: "", types: [], feats: {}, warns: {},
  age: "", minDays: "", onlyDrops: false, withPrice: false, withPhoto: false, withCoords: false, privateOnly: false,
  multiSource: false, showInactive: false, showHidden: false, affordableOnly: false, sources: [], agency: "", sort: "new",
};
const DEFAULT_FINANCE = { equity: "", income: "", rate: 1.6, imputed: 5, maintenance: 1, extra: 2.5 };

let DATA = null, ALL = [], VIEW = "list", F = clone(DEFAULT_FILTERS), FIN = store.get("finance", clone(DEFAULT_FINANCE));
let FAVS = store.get("favs", {}), HIDDEN = store.get("hidden", {}), NOTES = store.get("notes", {}), SEEN = store.get("seen", {});
let CUSTOM_PT = store.get("customPoint", null);
let shown = 60, map = null, mapLayer = null, refLayer = null, tableSort = { k: "first_seen", d: -1 };
const TODAY = new Date().toISOString().slice(0, 10);

function clone(o) { return JSON.parse(JSON.stringify(o)); }
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function safeUrl(u) { return /^https?:\/\//i.test(u || "") ? u : "#"; }
function chf(v) { return v ? "CHF " + Math.round(v).toLocaleString("de-CH").replace(/,/g, "’") : "Price on request"; }
function num(v) { if (v === "" || v === null || v === undefined) return null; const n = Number(v); return Number.isFinite(n) ? n : null; }
function daysBetween(a, b) { return Math.round((new Date(b) - new Date(a)) / 864e5); }
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.hidden = false; clearTimeout(toast._t); toast._t = setTimeout(() => (t.hidden = true), 2600); }
function km(lat1, lng1, lat2, lng2) {
  const R = 6371, dLat = (lat2 - lat1) * Math.PI / 180, dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
function median(a) { if (!a.length) return null; const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
function quality(p) { return ((p.images || []).length ? 2 : 0) + (p.price && !p.numbers_hidden ? 1 : 0) + (p._srcs || []).length * 0.1; }
function family(label) { return String(label || "").split(" (")[0]; }

/* ------------------------------------------------------------------ data */

async function load() {
  try {
    const r = await fetch("data/public.json?v=" + Date.now());
    if (!r.ok) throw new Error(r.status);
    DATA = await r.json();
  } catch (e) {
    $("#banner").hidden = false;
    $("#banner").textContent = "No data yet – the daily search has not run yet (data/public.json is missing).";
    DATA = { properties: [], sources: {}, runs: [] };
  }
  ALL = DATA.properties || [];
  // municipality centroids (for listings without coordinates) and median price/m²
  const cent = {}, ppm = {};
  for (const p of ALL) {
    p._srcs = [...new Set((p.links || []).map(l => family(l.label)))];
    p._date = (p.published && p.published.slice(0, 10) < p.first_seen) ? p.published.slice(0, 10) : p.first_seen;
    if (p.lat && p.lng && p.municipality) (cent[p.municipality] ||= []).push([p.lat, p.lng]);
    if (p.active && p.price_per_m2 && !p.numbers_hidden && p.municipality) (ppm[p.municipality] ||= []).push(p.price_per_m2);
  }
  const C = {}; for (const [m, pts] of Object.entries(cent)) C[m] = [median(pts.map(x => x[0])), median(pts.map(x => x[1]))];
  const M = {}; for (const [m, v] of Object.entries(ppm)) if (v.length >= 3) M[m] = median(v);
  DATA._ppmMedian = M;
  for (const p of ALL) {
    p._approx = !(p.lat && p.lng) && !!C[p.municipality];
    p._lat = p.lat || (C[p.municipality] || [])[0]; p._lng = p.lng || (C[p.municipality] || [])[1];
    p._score = p.price_per_m2 && M[p.municipality] ? p.price_per_m2 / M[p.municipality] - 1 : null;
    const ph = p.price_history || [];
    const maxP = ph.length ? Math.max(...ph.map(h => h[1])) : null;
    p._dropPct = maxP && p.price && p.price < maxP ? (maxP - p.price) / maxP : 0;
    p._oldPrice = p._dropPct ? maxP : null;
    p._isNew = !p.baseline && daysBetween(p.first_seen, TODAY) <= 1;
  }
  const gen = DATA.generated ? new Date(DATA.generated) : null;
  const act = ALL.filter(p => p.active).length, nw = ALL.filter(p => p._isNew && p.active).length;
  $("#stats").textContent = `${act} active ads · ${nw} new · updated ${gen ? gen.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "–"}`;
  if (gen && (Date.now() - gen) / 864e5 > 2.5) {
    $("#banner").hidden = false;
    $("#banner").textContent = `Note: the data is ${Math.floor((Date.now() - gen) / 864e5)} days old – the daily run may have failed (see GitHub → Actions).`;
  }
}

/* ------------------------------------------------------------------ filtering */

function finance() {
  const eq = num(FIN.equity), inc = num(FIN.income);
  const nk = (num(FIN.extra) || 0) / 100, imp = (num(FIN.imputed) || 5) / 100, mnt = (num(FIN.maintenance) || 1) / 100;
  const amort = (0.8 - 2 / 3) / 15; // 2nd mortgage down to 2/3 of value within 15 years
  const byEq = eq ? eq / (0.2 + nk) : null;
  const byInc = inc ? (inc / 3) / (0.8 * imp + mnt + amort) : null;
  const maxPrice = byEq && byInc ? Math.min(byEq, byInc) : (byEq || byInc);
  return { eq, inc, nk, imp, mnt, amort, byEq, byInc, maxPrice };
}
function monthlyCost(price) {
  if (!price) return null;
  const r = (num(FIN.rate) || 1.6) / 100, f = finance();
  const eq = f.eq ? Math.min(f.eq - price * f.nk, price) : price * 0.2;
  const mort = Math.max(price - Math.max(eq, price * 0.2), 0);
  return (mort * r + price * f.amort * (mort > price * 2 / 3 ? 1 : 0) + price * f.mnt) / 12;
}

function refCoords() {
  if (!F.refPoint) return null;
  if (F.refPoint === "custom") return CUSTOM_PT;
  const r = REF_POINTS[F.refPoint]; return r ? [r[1], r[2]] : null;
}

function inRange(v, lo, hi, miss) {
  lo = num(lo); hi = num(hi);
  if (lo === null && hi === null) return true;
  if (v === null || v === undefined) return miss;
  return (lo === null || v >= lo) && (hi === null || v <= hi);
}

function filterProps(list, f = F) {
  const terms = f.q.toLowerCase().split(/\s+/).filter(Boolean);
  const ex = f.qx.toLowerCase().split(",").map(s => s.trim()).filter(Boolean);
  const zips = f.zips.split(/[,\s]+/).map(s => s.trim()).filter(Boolean);
  const ref = refCoords(), maxKm = num(f.maxKm), fin = finance(), agency = f.agency.toLowerCase();
  const out = [];
  for (const p of list) {
    p._dist = ref && p._lat ? km(ref[0], ref[1], p._lat, p._lng) : null;
    if (!f.showInactive && !p.active) continue;
    if (!f.showHidden && HIDDEN[p.id]) continue;
    const miss = f.includeMissing;
    const nums = !p.numbers_hidden;
    if (!inRange(nums ? p.price : null, f.priceMin, f.priceMax, miss)) continue;
    if (!inRange(nums ? p.rooms : null, f.roomsMin, f.roomsMax, miss)) continue;
    if (!inRange(nums ? p.living_area : null, f.areaMin, f.areaMax, miss)) continue;
    if (!inRange(nums ? p.price_per_m2 : null, f.ppmMin, f.ppmMax, miss)) continue;
    if (!inRange(p.year_built, f.yearMin, f.yearMax, miss)) continue;
    if (!inRange(p.floor, f.floorMin, f.floorMax, miss)) continue;
    if (num(f.bathMin) && !((p.bathrooms || (p.features?.two_bathrooms ? 2 : null)) >= num(f.bathMin) || (miss && !p.bathrooms))) continue;
    if (f.cantons.length && !f.cantons.includes(p.canton || "?")) continue;
    if (f.districts.length && !f.districts.includes(p.district) && p.canton !== "?") continue;
    if (f.munis.length && !f.munis.includes(p.municipality) && p.canton !== "?") continue;
    if (zips.length && !zips.includes(String(p.zip || ""))) continue;
    if (maxKm !== null && ref && (p._dist === null || p._dist > maxKm)) continue;
    if (f.types.length && !f.types.includes(p.property_type || "apartment")) continue;
    const feats = p.features || {};
    let ok = true;
    for (const [k, v] of Object.entries({ ...f.feats, ...f.warns })) {
      if (v === 1 && !feats[k]) { ok = false; break; }
      if (v === -1 && feats[k]) { ok = false; break; }
    }
    if (!ok) continue;
    if (f.age && daysBetween(p._date, TODAY) > Number(f.age)) continue;
    if (num(f.minDays) && daysBetween(p._date, TODAY) < num(f.minDays)) continue;
    if (f.onlyDrops && !p._dropPct) continue;
    if (f.withPrice && (!p.price || p.numbers_hidden)) continue;
    if (f.withPhoto && !(p.images || []).length) continue;
    if (f.withCoords && !(p.lat && p.lng)) continue;
    if (f.privateOnly && !p.private_seller) continue;
    if (f.multiSource && (p._srcs || []).length < 2) continue;
    if (f.affordableOnly && fin.maxPrice && (!p.price || p.price > fin.maxPrice)) continue;
    if (f.sources.length && !p._srcs.some(s => f.sources.includes(s))) continue;
    if (agency && !String(p.agency || "").toLowerCase().includes(agency)) continue;
    if (terms.length || ex.length) {
      const hay = `${p.title} ${p.description} ${p.street} ${p.zip} ${p.municipality} ${p.agency}`.toLowerCase();
      if (terms.some(t => !hay.includes(t))) continue;
      if (ex.some(t => hay.includes(t))) continue;
    }
    out.push(p);
  }
  const s = f.sort, big = 1e15;
  const by = {
    new: (a, b) => (b._date || "").localeCompare(a._date || "") || quality(b) - quality(a),
    priceAsc: (a, b) => (a.price || big) - (b.price || big), priceDesc: (a, b) => (b.price || 0) - (a.price || 0),
    ppmAsc: (a, b) => (a.price_per_m2 || big) - (b.price_per_m2 || big), areaDesc: (a, b) => (b.living_area || 0) - (a.living_area || 0),
    roomsDesc: (a, b) => (b.rooms || 0) - (a.rooms || 0), distAsc: (a, b) => (a._dist ?? big) - (b._dist ?? big),
    dropDesc: (a, b) => b._dropPct - a._dropPct, daysDesc: (a, b) => (a._date || "").localeCompare(b._date || ""),
    score: (a, b) => (a._score ?? big) - (b._score ?? big),
  };
  return out.sort(by[s] || by.new);
}

/* ------------------------------------------------------------------ rendering */

function factsHtml(p) {
  const f = [];
  if (p.numbers_hidden) f.push("<span class='muted'>details in the ad</span>");
  else {
    if (p.rooms) f.push(`<b>${p.rooms}</b> rooms`);
    if (p.living_area) f.push(`<b>${p.living_area}</b> m²`);
    if (p.price_per_m2) f.push(`${chf(p.price_per_m2)}/m²`);
  }
  if (p.floor !== null && p.floor !== undefined) f.push(p.floor === 0 ? "ground floor" : `floor ${p.floor}`);
  if (p.year_built) f.push(`built ${p.year_built}${p.year_renovated ? " / ren. " + p.year_renovated : ""}`);
  if (p._dist !== null && p._dist !== undefined) f.push(`${p._dist.toFixed(1)} km${p._approx ? "≈" : ""}`);
  return f.join("<span class='muted'> · </span>");
}
function featHtml(p) {
  const fs = p.features || {};
  return Object.entries(FEATURES).filter(([k]) => fs[k]).map(([, v]) => `<span>${esc(v)}</span>`).join("")
    + Object.entries(WARNINGS).filter(([k]) => fs[k]).map(([, v]) => `<span class="w">⚠ ${esc(v)}</span>`).join("");
}
function priceHtml(p) {
  if (p.numbers_hidden) return `<div class="price">see ad</div>`;
  let h = `<div class="price">${chf(p.price)}`;
  if (p._oldPrice) h += `<span class="old">${chf(p._oldPrice)}</span>`;
  h += `</div>`;
  const extras = [];
  if (p._score !== null && p._score !== undefined && Math.abs(p._score) >= 0.05) extras.push(`${p._score < 0 ? "▼" : "▲"} ${Math.abs(Math.round(p._score * 100))}% vs. median ${esc(p.municipality)}`);
  if (finance().eq || finance().inc) { const m = monthlyCost(p.price); if (m) extras.push(`≈ ${chf(m)}/month`); }
  if (extras.length) h += `<div class="muted small">${extras.join(" · ")}</div>`;
  return h;
}

function cardHtml(p) {
  const img = (p.images || [])[0];
  const badges = [];
  if (p._isNew) badges.push(`<span class="badge new">NEW</span>`);
  if (p._dropPct) badges.push(`<span class="badge drop">−${Math.round(p._dropPct * 100)}%</span>`);
  if (!p.active) badges.push(`<span class="badge gone">removed</span>`);
  if (!SEEN[p.id] && !p._isNew && p.active && daysBetween(p.first_seen, TODAY) <= 3 && !p.baseline) badges.push(`<span class="badge">unseen</span>`);
  const loc = [p.street, [p.zip, p.municipality].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  const links = (p.links || []).map(l => `<a href="${esc(safeUrl(l.url))}" target="_blank" rel="noopener" class="${l.active ? "" : "dead"}">${esc(family(l.label))}</a>`).join("");
  const note = NOTES[p.id] ? `<div class="note">📝 ${esc(NOTES[p.id])}</div>` : "";
  const age = daysBetween(p._date, TODAY);
  return `<article class="card ${p.active ? "" : "inactive"}" data-id="${esc(p.id)}">
    <div class="ph" data-act="open">${img ? `<img loading="lazy" src="${esc(safeUrl(img))}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'noimg',textContent:'🏠'}))">` : `<div class="noimg">🏠</div>`}
      <div class="badges">${badges.join("")}</div>${(p.images || []).length > 1 ? `<span class="imgcount">${p.images.length} Fotos</span>` : ""}</div>
    <div class="body">
      ${priceHtml(p)}
      <h3 data-act="open">${esc(p.title || "Apartment")}</h3>
      <div class="facts">${factsHtml(p)}</div>
      <div class="loc">📍 ${esc(loc || "location unknown")}${p.canton && p.canton !== "?" ? ` <span class="muted">(${esc(p.canton)})</span>` : ""}</div>
      <div class="feat">${featHtml(p)}</div>${note}
      <div class="links">🔗 ${links}</div>
    </div>
    <div class="actions">
      <button data-act="fav" class="${FAVS[p.id] ? "on" : ""}" title="Favorite">★</button>
      <button data-act="note" title="Note">📝</button>
      <button data-act="hide" title="${HIDDEN[p.id] ? "unhide" : "hide"}">${HIDDEN[p.id] ? "↺" : "✕"}</button>
      <div class="meta">${age === 0 ? "today" : age === 1 ? "yesterday" : `${age} days ago`}<br>${esc(p.agency || "")}</div>
    </div>
  </article>`;
}

function renderList(list) {
  $("#cards").innerHTML = list.slice(0, shown).map(cardHtml).join("") || `<p class="muted">No ads match the filters.</p>`;
  $("#more").hidden = list.length <= shown;
}

function renderTable(list) {
  const cols = [
    ["first_seen", "Found"], ["title", "Title"], ["price", "Price", 1], ["rooms", "Rooms", 1], ["living_area", "m²", 1],
    ["price_per_m2", "CHF/m²", 1], ["municipality", "Municipality"], ["zip", "ZIP"], ["floor", "Floor", 1], ["year_built", "Built", 1],
    ["_dist", "km", 1], ["_score", "vs. median", 1], ["agency", "Agency"], ["_srcs", "Sources"],
  ];
  const k = tableSort.k, d = tableSort.d;
  const rows = [...list].sort((a, b) => {
    const x = a[k], y = b[k];
    if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
    return (typeof x === "number" ? x - y : String(x).localeCompare(String(y))) * d;
  });
  const fmt = (p, c) => {
    const v = p[c];
    if (v == null) return "";
    if (c === "price" || c === "price_per_m2") return p.numbers_hidden ? "–" : Math.round(v).toLocaleString("de-CH");
    if (c === "_dist") return v.toFixed(1);
    if (c === "_score") return (v > 0 ? "+" : "") + Math.round(v * 100) + "%";
    if (c === "_srcs") return v.join(", ");
    if (c === "title") return `<a href="#" data-open="${esc(p.id)}">${esc(String(v).slice(0, 60))}</a>`;
    return esc(v);
  };
  $("#table").innerHTML = `<thead><tr>${cols.map(([c, l, n]) => `<th data-k="${c}" class="${n ? "num" : ""}">${l}${k === c ? (d > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead>
    <tbody>${rows.slice(0, 1500).map(p => `<tr>${cols.map(([c, , n]) => `<td class="${n ? "num" : ""}">${fmt(p, c)}</td>`).join("")}</tr>`).join("")}</tbody>`;
}

function ensureMap() {
  if (map || typeof L === "undefined") return;
  map = L.map("map").setView([47.53, 7.65], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
  mapLayer = L.layerGroup().addTo(map); refLayer = L.layerGroup().addTo(map);
  map.on("click", e => {
    if (F.refPoint !== "custom") return;
    CUSTOM_PT = [e.latlng.lat, e.latlng.lng]; store.set("customPoint", CUSTOM_PT); apply();
  });
}
function renderMap(list) {
  ensureMap(); if (!map) { $("#mapNote").textContent = "Map could not be loaded."; return; }
  setTimeout(() => map.invalidateSize(), 50);
  mapLayer.clearLayers(); refLayer.clearLayers();
  let n = 0, approx = 0;
  for (const p of list) {
    if (!p._lat) continue;
    n++; if (p._approx) approx++;
    const color = p._isNew ? "#1d4ed8" : p._dropPct ? "#b91c1c" : FAVS[p.id] ? "#eab308" : "#0f766e";
    const m = L.circleMarker([p._lat + (p._approx ? (Math.random() - .5) * .004 : 0), p._lng + (p._approx ? (Math.random() - .5) * .006 : 0)],
      { radius: 7, color: "#fff", weight: 1.5, fillColor: color, fillOpacity: p._approx ? .55 : .95 });
    const img = (p.images || [])[0];
    m.bindPopup(`<div class="map-pop">${img ? `<img src="${esc(safeUrl(img))}" alt="">` : ""}<b>${p.numbers_hidden ? "see ad" : chf(p.price)}</b><br>${esc(p.title || "")}<br>
      <span class="muted">${p.rooms ? p.rooms + " rooms · " : ""}${p.living_area ? p.living_area + " m² · " : ""}${esc(p.municipality || "")}${p._approx ? " (approx. location)" : ""}</span><br>
      <a href="#" data-open="${esc(p.id)}">Details</a> · <a href="${esc(safeUrl(p.url))}" target="_blank" rel="noopener">Open ad</a></div>`);
    m.addTo(mapLayer);
  }
  const ref = refCoords();
  if (ref) {
    L.marker(ref).addTo(refLayer).bindTooltip(REF_POINTS[F.refPoint]?.[0] || "Reference");
    if (num(F.maxKm)) L.circle(ref, { radius: num(F.maxKm) * 1000, color: "#0f766e", weight: 1, fillOpacity: .05 }).addTo(refLayer);
  }
  $("#mapNote").textContent = `${n} of ${list.length} results on the map (${approx} with approximate position = municipality centre). ${F.refPoint === "custom" ? "Click on the map to set your reference point." : ""}`;
}

function renderFavs() {
  const favs = ALL.filter(p => FAVS[p.id]).sort((a, b) => (FAVS[b.id] || 0) - (FAVS[a.id] || 0));
  $("#favCards").innerHTML = favs.map(cardHtml).join("") || `<p class="muted">No favorites yet – click ★ on an ad.</p>`;
}

function renderFinance() {
  const f = finance();
  const field = (k, l, step, hint) => `<label><span class="lbl">${l}</span><input data-fin="${k}" type="number" step="${step}" value="${esc(FIN[k])}" placeholder="${hint || ""}"></label>`;
  const act = ALL.filter(p => p.active && !p.numbers_hidden);
  const byMuni = {};
  for (const p of act) (byMuni[p.municipality || "?"] ||= []).push(p);
  const rows = Object.entries(byMuni).filter(([, l]) => l.length >= 2).map(([m, l]) => {
    const pr = l.map(p => p.price).filter(Boolean), pp = l.map(p => p.price_per_m2).filter(Boolean);
    return { m, n: l.length, mp: median(pr), mppm: median(pp), canton: l[0].canton };
  }).sort((a, b) => b.n - a.n);
  $("#finance").innerHTML = `
  <div class="panel"><h2>Affordability & budget</h2>
    <div class="grid2">
      ${field("equity", "Own funds (CHF, incl. pillar 3a / pension fund)", 10000, "e.g. 250000")}
      ${field("income", "Gross household income / year", 5000, "e.g. 200000")}
      ${field("rate", "Actual mortgage rate %", 0.05)}
      ${field("imputed", "Imputed rate % for affordability (banks: 5%)", 0.1)}
      ${field("maintenance", "Maintenance & running costs % p.a.", 0.1)}
      ${field("extra", "Purchase costs % (notary, land registry, transfer tax)", 0.1)}
    </div>
    <div class="kpis">
      <div class="kpi"><span class="muted small">Max. price by own funds (20% + purchase costs)</span><b>${f.byEq ? chf(f.byEq) : "–"}</b></div>
      <div class="kpi"><span class="muted small">Max. price by income (≤ ⅓ rule)</span><b>${f.byInc ? chf(f.byInc) : "–"}</b></div>
      <div class="kpi"><span class="muted small">Your budget</span><b>${f.maxPrice ? chf(f.maxPrice) : "–"}</b></div>
      <div class="kpi"><span class="muted small">Monthly cost at budget (actual rate)</span><b>${f.maxPrice ? chf(monthlyCost(f.maxPrice)) : "–"}</b></div>
    </div>
    <p class="muted small">Swiss bank rules of thumb: at least 20% own funds (10% must be “hard” equity, not from the pension fund); housing costs at a 5% imputed rate + 1% maintenance + amortising the 2nd mortgage to ⅔ within 15 years must stay ≤ ⅓ of gross income. Rough estimate only. Tick “only affordable” in the filters to see ads up to your budget; every card then shows an estimated monthly cost.</p>
  </div>
  <div class="panel"><h2>Market overview (active ads)</h2>
    <div class="table-wrap"><table><thead><tr><th>Municipality</th><th>Canton</th><th class="num">Ads</th><th class="num">Median price</th><th class="num">Median CHF/m²</th></tr></thead>
    <tbody>${rows.map(r => `<tr><td><a href="#" data-muni="${esc(r.m)}">${esc(r.m)}</a></td><td>${esc(r.canton || "")}</td><td class="num">${r.n}</td><td class="num">${r.mp ? Math.round(r.mp).toLocaleString("de-CH") : ""}</td><td class="num">${r.mppm ? Math.round(r.mppm).toLocaleString("de-CH") : ""}</td></tr>`).join("")}</tbody></table></div>
  </div>`;
}

function renderSources() {
  const S = DATA.sources || {};
  const ent = Object.entries(S).sort((a, b) => (a[1].kind !== "portal") - (b[1].kind !== "portal") || a[1].label.localeCompare(b[1].label));
  const runs = (DATA.runs || []).slice(-14).reverse();
  $("#sources").innerHTML = `
  <div class="panel"><h2>Automatically searched sources (${ent.length})</h2>
    <p class="muted small">Portals and aggregators (Comparis and RealAdvisor bundle Homegate, ImmoScout24, Newhome, Flatfox, Properstar and many broker feeds), classifieds (tutti/anibis/ricardo) and the websites of local brokers, banks and developers. Duplicate ads are merged into one.</p>
    <div class="table-wrap"><table><thead><tr><th>Source</th><th>Type</th><th>Status</th><th class="num">Ads</th><th>Last OK</th></tr></thead><tbody>
    ${ent.map(([k, s]) => `<tr><td>${s.url ? `<a href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener">${esc(s.label)}</a>` : esc(s.label)}</td><td>${esc(s.kind)}</td>
      <td class="${s.status === "ok" ? "status-ok" : "status-bad"}">${esc(s.status)}</td><td class="num">${s.count ?? ""}</td><td>${esc(s.last_ok || "–")}</td></tr>`).join("")}
    </tbody></table></div></div>
  <div class="panel"><h2>Check manually</h2>
    <p class="muted small">These sites block automated requests or load their ads with JavaScript. Their ads usually still reach this app through the aggregators – to be safe, here are the direct searches (newest first):</p>
    <ul>${MANUAL_LINKS.map(([l, u]) => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(l)}</a></li>`).join("")}</ul></div>
  <div class="panel"><h2>Recent runs</h2>
    <table><thead><tr><th>Day</th><th class="num">New</th><th class="num">Price changes</th><th class="num">Active</th></tr></thead>
    <tbody>${runs.map(r => `<tr><td>${esc(r.day)}</td><td class="num">${r.new}</td><td class="num">${r.price_changes}</td><td class="num">${r.active}</td></tr>`).join("")}</tbody></table></div>`;
}

function openDetail(id) {
  const p = ALL.find(x => x.id === id); if (!p) return;
  SEEN[id] = 1; store.set("seen", SEEN);
  const hist = (p.price_history || []).map(h => `<span>${esc(h[0])}: ${chf(h[1])}</span>`).join("");
  const rows = [
    ["Price", p.numbers_hidden ? "see ad" : chf(p.price)], ["Rooms", p.rooms], ["Living area", p.living_area && p.living_area + " m²"],
    ["Usable area", p.usable_area && p.usable_area + " m²"], ["CHF/m²", p.price_per_m2 && chf(p.price_per_m2)],
    ["vs. municipality median", p._score != null ? (p._score > 0 ? "+" : "") + Math.round(p._score * 100) + "%" : null],
    ["Floor", p.floor === 0 ? "ground floor" : p.floor], ["Bathrooms", p.bathrooms], ["Year built", p.year_built], ["Renovated", p.year_renovated],
    ["Address", [p.street, p.zip, p.municipality].filter(Boolean).join(" ")], ["District / canton", [p.district, CANTONS[p.canton]].filter(Boolean).join(", ")],
    ["Agency / seller", [p.agency, p.agency_phone].filter(Boolean).join(" · ")], ["Type", p.type_label || TYPES[p.property_type]],
    ["First seen", p.first_seen], ["Published", p.published && p.published.slice(0, 10)], ["Last seen", p.last_seen],
    ["Estimated monthly cost", (finance().eq || finance().inc) && p.price ? chf(monthlyCost(p.price)) : null],
    ["Distance", p._dist != null ? p._dist.toFixed(1) + " km straight line" : null],
  ].filter(r => r[1] !== null && r[1] !== undefined && r[1] !== "");
  const gmaps = p.lat ? `https://www.google.com/maps/search/?api=1&query=${p.lat},${p.lng}` : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent([p.street, p.zip, p.municipality].filter(Boolean).join(" "))}`;
  $("#detailBody").innerHTML = `<div class="detail">
    <div class="gallery">${(p.images || []).map(i => `<img src="${esc(safeUrl(i))}" alt="" loading="lazy">`).join("")}</div>
    <button class="btn close" data-close>✕</button>
    ${priceHtml(p)}<h2 style="margin:4px 0 8px">${esc(p.title)}</h2>
    <div class="feat" style="margin-bottom:10px">${featHtml(p)}</div>
    <dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd style="margin:0">${esc(v)}</dd>`).join("")}</dl>
    ${hist ? `<div class="lbl">Price history</div><div class="hist">${hist}</div>` : ""}
    <div class="lbl">Ads</div><div class="links">${(p.links || []).map(l => `<a href="${esc(safeUrl(l.url))}" target="_blank" rel="noopener" class="${l.active ? "" : "dead"}">${esc(l.label)} ↗</a>`).join("")}
      <a href="${esc(gmaps)}" target="_blank" rel="noopener">Google Maps ↗</a></div>
    ${p.parsed_from_text ? `<p class="muted small">Numbers were read automatically from the ad text – please verify in the ad.</p>` : ""}
    <div class="lbl">Description</div><div class="desc">${esc(p.description || "–")}</div>
    <div class="lbl">Your note</div><textarea id="noteText" rows="3" placeholder="e.g. viewing on …">${esc(NOTES[p.id] || "")}</textarea>
    <div style="display:flex;gap:8px;margin-top:8px"><button class="btn primary" data-savenote="${esc(p.id)}">Save note</button>
    <button class="btn" data-favd="${esc(p.id)}">${FAVS[p.id] ? "★ Remove favorite" : "☆ Add to favorites"}</button></div>
  </div>`;
  $("#detail").showModal();
}

/* ------------------------------------------------------------------ filter UI */

function chipGroup(el, entries, getState, onClick) {
  el.innerHTML = entries.map(([k, l, c]) => `<span class="chip ${getState(k)}" data-k="${esc(k)}">${esc(l)}${c != null ? ` <span class="muted">${c}</span>` : ""}</span>`).join("");
  el.onclick = e => { const c = e.target.closest(".chip"); if (c) { onClick(c.dataset.k); } };
}
function toggleIn(arr, k) { const i = arr.indexOf(k); i >= 0 ? arr.splice(i, 1) : arr.push(k); }

function buildFilterUI() {
  const act = ALL.filter(p => p.active);
  const count = key => act.reduce((m, p) => (m[p[key] || "?"] = (m[p[key] || "?"] || 0) + 1, m), {});
  const cc = count("canton"), dc = count("district"), mc = count("municipality");
  chipGroup($("#cantonChips"), Object.entries(CANTONS).map(([k, l]) => [k, l, cc[k] || 0]), k => F.cantons.includes(k) ? "on" : "", k => { toggleIn(F.cantons, k); apply(); });
  const districts = ["Basel", "Arlesheim", "Laufen", "Liestal", "Sissach", "Waldenburg"];
  chipGroup($("#districtChips"), districts.map(d => [d, d, dc[d] || 0]), k => F.districts.includes(k) ? "on" : "", k => { toggleIn(F.districts, k); apply(); });
  const munis = Object.keys(mc).filter(m => m !== "?" && m).sort((a, b) => mc[b] - mc[a] || a.localeCompare(b));
  const renderMunis = () => {
    const q = $("#muniSearch").value.toLowerCase();
    $("#muniList").innerHTML = munis.filter(m => m.toLowerCase().includes(q)).map(m =>
      `<label><input type="checkbox" value="${esc(m)}" ${F.munis.includes(m) ? "checked" : ""}> ${esc(m)} <span class="cnt">${mc[m]}</span></label>`).join("") || `<span class="muted small">–</span>`;
  };
  renderMunis(); $("#muniSearch").oninput = renderMunis;
  $("#muniList").onchange = e => { toggleIn(F.munis, e.target.value); apply(false); };
  $("#muniClear").onclick = () => { F.munis = []; renderMunis(); apply(); };

  chipGroup($("#typeChips"), Object.entries(TYPES), k => F.types.includes(k) ? "on" : "", k => { toggleIn(F.types, k); apply(); });
  const tri = (obj, k) => { obj[k] = obj[k] === 1 ? -1 : obj[k] === -1 ? 0 : 1; if (!obj[k]) delete obj[k]; apply(); };
  const triState = obj => k => obj[k] === 1 ? "on" : obj[k] === -1 ? "off" : "";
  const fc = {}; for (const p of act) for (const k in (p.features || {})) fc[k] = (fc[k] || 0) + 1;
  chipGroup($("#featureChips"), Object.entries(FEATURES).map(([k, l]) => [k, l, fc[k] || 0]), triState(F.feats), k => tri(F.feats, k));
  chipGroup($("#warnChips"), Object.entries(WARNINGS).map(([k, l]) => [k, l, fc[k] || 0]), triState(F.warns), k => tri(F.warns, k));

  const sc = {}; for (const p of act) for (const s of p._srcs) sc[s] = (sc[s] || 0) + 1;
  $("#sourceList").innerHTML = Object.keys(sc).sort((a, b) => sc[b] - sc[a]).map(s =>
    `<label><input type="checkbox" value="${esc(s)}" ${F.sources.includes(s) ? "checked" : ""}> ${esc(s)} <span class="cnt">${sc[s]}</span></label>`).join("");
  $("#sourceList").onchange = e => { toggleIn(F.sources, e.target.value); apply(false); };

  $("#refPoint").innerHTML = Object.entries(REF_POINTS).map(([k, v]) => `<option value="${k}">${esc(v[0])}</option>`).join("");
}

const SIMPLE = ["q", "qx", "priceMin", "priceMax", "roomsMin", "roomsMax", "areaMin", "areaMax", "ppmMin", "ppmMax", "yearMin", "yearMax",
  "floorMin", "floorMax", "bathMin", "zips", "refPoint", "maxKm", "age", "minDays", "agency", "sort"];
const BOOLS = ["includeMissing", "onlyDrops", "withPrice", "withPhoto", "withCoords", "privateOnly", "multiSource", "showInactive", "showHidden", "affordableOnly"];

function syncInputs() {
  for (const k of SIMPLE) { const el = $("#" + k); if (el) el.value = F[k] ?? ""; }
  for (const k of BOOLS) { const el = $("#" + k); if (el) el.checked = !!F[k]; }
  buildFilterUI();
  $("#refPoint").value = F.refPoint || "";
  $("#refHint").textContent = F.refPoint === "custom" ? (CUSTOM_PT ? "point set" : "click on map") : "";
}

function bindInputs() {
  let t;
  for (const k of SIMPLE) {
    const el = $("#" + k); if (!el) continue;
    el.addEventListener("input", () => { F[k] = el.value; clearTimeout(t); t = setTimeout(() => apply(false), 250); });
  }
  for (const k of BOOLS) { const el = $("#" + k); if (el) el.addEventListener("change", () => { F[k] = el.checked; apply(false); }); }
  $("#refPoint").addEventListener("change", () => { $("#refHint").textContent = F.refPoint === "custom" ? "click on map" : ""; if (F.refPoint === "custom") setView("map"); });
}

function apply(rebuild = true) {
  shown = 60;
  if (rebuild) syncInputs();
  store.set("filters", F);
  render();
}

function render() {
  const list = filterProps(ALL);
  $("#resultCount").textContent = list.length;
  $("#favCount").textContent = Object.keys(FAVS).length || "";
  if (VIEW === "list") renderList(list);
  if (VIEW === "map") renderMap(list);
  if (VIEW === "table") renderTable(list);
  if (VIEW === "favs") renderFavs();
  if (VIEW === "finance") renderFinance();
  if (VIEW === "sources") renderSources();
  render._list = list;
}

function setView(v) {
  VIEW = v;
  $$(".tabs button").forEach(b => b.classList.toggle("active", b.dataset.view === v));
  $$(".view").forEach(s => s.classList.toggle("active", s.id === "view-" + v));
  render();
}

/* ------------------------------------------------------------------ presets / share / email filter */

function encodeFilters(f) { return btoa(unescape(encodeURIComponent(JSON.stringify(f)))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); }
function decodeFilters(s) { try { return JSON.parse(decodeURIComponent(escape(atob(s.replace(/-/g, "+").replace(/_/g, "/"))))); } catch (e) { return null; } }

function renderPresets() {
  const P = store.get("presets", {});
  $("#presetList").innerHTML = Object.keys(P).map(n => `<div class="preset"><a href="#" data-preset="${esc(n)}">${esc(n)}</a><span><button class="link-btn small" data-delpreset="${esc(n)}">delete</button></span></div>`).join("");
}

function emailFilterJson() {
  const n = v => num(v);
  const req = Object.entries({ ...F.feats, ...F.warns }).filter(([, v]) => v === 1).map(([k]) => k);
  const exc = Object.entries({ ...F.feats, ...F.warns }).filter(([, v]) => v === -1).map(([k]) => k);
  return JSON.stringify({
    price_min: n(F.priceMin), price_max: n(F.priceMax), rooms_min: n(F.roomsMin), rooms_max: n(F.roomsMax),
    area_min: n(F.areaMin), area_max: n(F.areaMax), price_per_m2_max: n(F.ppmMax), year_built_min: n(F.yearMin),
    cantons: F.cantons.filter(c => c !== "?"), districts: F.districts, municipalities: F.munis,
    require_features: req, exclude_features: exc,
    exclude_keywords: F.qx.split(",").map(s => s.trim()).filter(Boolean),
    include_keywords_any: [], exclude_types: [],
    include_missing_values: !!F.includeMissing, include_unknown_location: !F.cantons.length || F.cantons.includes("?"),
  }, null, 2);
}

async function copy(text, msg) {
  try { await navigator.clipboard.writeText(text); toast(msg); }
  catch (e) { ioDialog("Copy", text, null); }
}
function ioDialog(title, text, onOk) {
  $("#ioTitle").textContent = title; $("#ioText").value = text || ""; $("#ioOk").hidden = !onOk;
  const d = $("#ioDialog"); d.showModal();
  d.onclose = () => { if (d.returnValue === "ok" && onOk) onOk($("#ioText").value); };
}

/* ------------------------------------------------------------------ events */

function bindEvents() {
  $$(".tabs button").forEach(b => b.addEventListener("click", () => setView(b.dataset.view)));
  $("#toggleFilters").addEventListener("click", () => $("#filters").classList.toggle("open"));
  $("#closeFilters").addEventListener("click", () => $("#filters").classList.remove("open"));
  $("#resetFilters").addEventListener("click", () => { F = clone(DEFAULT_FILTERS); apply(); });
  $("#more").addEventListener("click", () => { shown += 60; renderList(render._list); });
  document.addEventListener("click", e => {
    const t = e.target;
    const open = t.closest("[data-open]"); if (open) { e.preventDefault(); openDetail(open.dataset.open); return; }
    if (t.closest("[data-close]")) { $("#detail").close(); return; }
    const muni = t.closest("[data-muni]"); if (muni) { e.preventDefault(); F.munis = [muni.dataset.muni]; apply(); setView("list"); return; }
    const sn = t.closest("[data-savenote]");
    if (sn) { const v = $("#noteText").value.trim(); v ? NOTES[sn.dataset.savenote] = v : delete NOTES[sn.dataset.savenote]; store.set("notes", NOTES); toast("Note saved"); render(); return; }
    const fd = t.closest("[data-favd]");
    if (fd) { const id = fd.dataset.favd; FAVS[id] ? delete FAVS[id] : FAVS[id] = Date.now(); store.set("favs", FAVS); $("#detail").close(); render(); return; }
    const pr = t.closest("[data-preset]");
    if (pr) { e.preventDefault(); const P = store.get("presets", {}); F = { ...clone(DEFAULT_FILTERS), ...P[pr.dataset.preset] }; apply(); toast("Search loaded"); return; }
    const dp = t.closest("[data-delpreset]");
    if (dp) { const P = store.get("presets", {}); delete P[dp.dataset.delpreset]; store.set("presets", P); renderPresets(); return; }
    const card = t.closest(".card"); const act = t.closest("[data-act]");
    if (card && act) {
      const id = card.dataset.id, a = act.dataset.act;
      if (a === "open") openDetail(id);
      if (a === "fav") { FAVS[id] ? delete FAVS[id] : FAVS[id] = Date.now(); store.set("favs", FAVS); render(); }
      if (a === "hide") { HIDDEN[id] ? delete HIDDEN[id] : HIDDEN[id] = 1; store.set("hidden", HIDDEN); render(); toast(HIDDEN[id] ? "Hidden (tick “show hidden ads” to see it)" : "Unhidden"); }
      if (a === "note") openDetail(id);
    }
  });
  $("#table").addEventListener("click", e => { const th = e.target.closest("th"); if (!th) return; const k = th.dataset.k; tableSort = { k, d: tableSort.k === k ? -tableSort.d : (["title", "municipality", "agency", "zip"].includes(k) ? 1 : -1) }; render(); });
  $("#finance").addEventListener("change", e => { const k = e.target.dataset.fin; if (!k) return; FIN[k] = e.target.value; store.set("finance", FIN); renderFinance(); });
  $("#savePreset").addEventListener("click", () => { const n = $("#presetName").value.trim(); if (!n) return toast("Please enter a name"); const P = store.get("presets", {}); P[n] = clone(F); store.set("presets", P); $("#presetName").value = ""; renderPresets(); toast("Search saved"); });
  $("#shareLink").addEventListener("click", () => copy(location.href.split("#")[0] + "#f=" + encodeFilters(F), "Link copied – e.g. send it to your partner"));
  $("#emailFilter").addEventListener("click", () => copy(emailFilterJson(), "E-mail filter copied"));
  $("#exportFavs").addEventListener("click", () => ioDialog("Export – copy this code", btoa(unescape(encodeURIComponent(JSON.stringify({ favs: FAVS, notes: NOTES, hidden: HIDDEN })))), null));
  $("#importFavs").addEventListener("click", () => ioDialog("Import – paste the code", "", v => {
    try {
      const d = JSON.parse(decodeURIComponent(escape(atob(v.trim()))));
      Object.assign(FAVS, d.favs || {}); Object.assign(HIDDEN, d.hidden || {});
      for (const [k, n] of Object.entries(d.notes || {})) NOTES[k] = NOTES[k] && NOTES[k] !== n ? NOTES[k] + " | " + n : n;
      store.set("favs", FAVS); store.set("notes", NOTES); store.set("hidden", HIDDEN); render(); toast("Imported");
    } catch (e) { toast("Invalid code"); }
  }));
  $("#detail").addEventListener("click", e => { if (e.target === $("#detail")) $("#detail").close(); });
}

/* ------------------------------------------------------------------ boot */

(async function init() {
  await load();
  const fromHash = location.hash.startsWith("#f=") ? decodeFilters(location.hash.slice(3)) : null;
  F = { ...clone(DEFAULT_FILTERS), ...(fromHash || store.get("filters", {})) };
  if (location.hash === "#new") { F = clone(DEFAULT_FILTERS); F.age = "1"; }
  bindInputs(); bindEvents(); syncInputs(); renderPresets();
  const v = (location.hash.match(/view=(\w+)/) || [])[1];
  if (v && document.getElementById("view-" + v)) setView(v); else render();
  const d = (location.hash.match(/detail=([^&]+)/) || [])[1];
  if (d) openDetail(decodeURIComponent(d));
})();
