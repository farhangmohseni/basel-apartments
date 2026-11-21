/* Studio Finder · Neuchâtel – client app (no build step, vanilla JS). */
"use strict";

const LS = "ne-studio:v1:";
const store = {
  get(k, d) { try { const v = localStorage.getItem(LS + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(LS + k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
};

const TYPES = { studio: "Studio", apartment: "Apartment", attic: "Attic / penthouse", maisonette: "Duplex", loft: "Loft", room: "Room (shared)" };
const FEATURES = {
  furnished: "Furnished", balcony: "Balcony", terrace: "Terrace", garden: "Garden", lift: "Lift", parking: "Parking",
  cellar: "Cellar / attic", own_laundry: "Own washing machine", dishwasher: "Dishwasher", equipped_kitchen: "Equipped kitchen",
  bathtub: "Bathtub", view: "View", lake: "Near the lake", quiet: "Quiet", near_transport: "Near public transport",
  near_shops: "Near shops", renovated: "Renovated", new_build: "New build", accessible: "Step-free", pets: "Pets ok",
};
const WARNINGS = { reserved: "Already reserved", temporary: "Temporary / sublet", shared_flat: "Shared flat", students_only: "Students only",
  seniors_only: "Seniors only", subsidized: "Subsidised (conditions)", swap: "Flat swap" };
const CANTONS = { NE: "Neuchâtel", BE: "Bern", VD: "Vaud", FR: "Fribourg" };
const MANUAL_LINKS = [
  ["Homegate – flats to rent, canton Neuchâtel (create an e-mail alert there)", "https://www.homegate.ch/louer/appartement/canton-neuchatel/liste-annonces?ah=1000&o=dateCreated-desc"],
  ["ImmoScout24 – flats to rent, canton Neuchâtel (alerts available)", "https://www.immoscout24.ch/fr/appartement/louer/canton-neuchatel?pt=1000&o=dateCreated-desc"],
  ["anibis – flats to rent (private ads, alerts available)", "https://www.anibis.ch/fr/q/immobilier-appartements/Ak8CqcmVhbEVzdGF0ZZSRkqtsaXN0aW5nVHlwZalhcGFydG1lbnTAwMA"],
  ["tutti.ch – flats (private ads)", "https://www.tutti.ch/fr/q/immobilier-appartements/Ak8CqcmVhbEVzdGF0ZZSRkqtsaXN0aW5nVHlwZalhcGFydG1lbnTAwMA"],
  ["Naef Immobilier – rentals", "https://www.naef.ch/louer/appartements-maisons/"],
  ["Ville de Neuchâtel – municipal flats (registration)", "https://www.neuchatelville.ch/vivre-a-neuchatel/habitat/gerance-et-logement"],
  ["Gérance Bosshart & Gautschi (La Chaux-de-Fonds)", "https://www.gerancebg.ch/"],
  ["Domicim – rentals", "https://www.domicim.ch/"],
  ["Bernard Nicod – rentals", "https://www.bernard-nicod.ch/louer"],
  ["Livit – rentals", "https://www.livit.ch/fr/search/residential"],
  ["Wincasa – rentals", "https://www.wincasa.ch/fr-ch/locataires"],
  ["students.ch – studios & rooms", "https://www.students.ch/fr/logement/list/"],
  ["Newhome – canton Neuchâtel", "https://www.newhome.ch/de/mieten/suchen/wohnung/kanton_neuenburg/liste"],
];

const DEFAULT_FILTERS = {
  maxCar: 0, maxPt: 0, commuteMode: "either", exactOnly: false,
  rentMin: "", rentMax: "", withPrice: false, types: ["studio", "apartment", "attic", "maisonette", "loft"], roomsMin: "", roomsMax: "", areaMin: "", areaMax: "", ppmMax: "",
  furnished: "any", includeMissing: true, cantons: [], places: [], feats: {}, warns: {},
  q: "", qx: "", age: "", onlyDrops: false, withPhoto: false, privateOnly: false, multiSource: false,
  showInactive: false, showHidden: false, sources: [], agency: "", sort: "value",
};
const DEFAULT_COSTS = { mode: "car", perKm: 0.7, days: 20, ptPass: 0, timeValue: 10, income: "" };

let DATA = null, ALL = [], VIEW = "list", F = clone(DEFAULT_FILTERS), COSTS = { ...DEFAULT_COSTS, ...store.get("costs", {}) };
let FAVS = store.get("favs", {}), HIDDEN = store.get("hidden", {}), NOTES = store.get("notes", {}), SEEN = store.get("seen", {});
let WORK = { name: "work", short: "work", lat: 46.97905, lng: 6.89517 };
let shown = 60, map = null, mapLayer = null, tableSort = { k: "_value", d: 1 }, placesSort = { k: "car_min", d: 1 }, scatterMetric = "car";
const TODAY = new Date().toISOString().slice(0, 10);

function clone(o) { return JSON.parse(JSON.stringify(o)); }
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function safeUrl(u) { return /^https?:\/\//i.test(u || "") ? u : "#"; }
function chf(v) { return v ? "CHF " + Math.round(v).toLocaleString("de-CH").replace(/,/g, "’") : "rent on request"; }
function num(v) { if (v === "" || v === null || v === undefined) return null; const n = Number(v); return Number.isFinite(n) ? n : null; }
function daysBetween(a, b) { return Math.round((new Date(b) - new Date(a)) / 864e5); }
function median(a) { if (!a.length) return null; const s = [...a].sort((x, y) => x - y), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; }
function family(label) { return String(label || "").split(" (")[0]; }
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.hidden = false; clearTimeout(toast._t); toast._t = setTimeout(() => (t.hidden = true), 2600); }
function km(a, b, c, d) {
  const R = 6371, dLat = (c - a) * Math.PI / 180, dLng = (d - b) * Math.PI / 180;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a * Math.PI / 180) * Math.cos(c * Math.PI / 180) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}
function minutes(v) { return v === null || v === undefined ? "–" : Math.round(v) + "′"; }
function timeColor(m, limit) {
  if (m === null || m === undefined) return "#9ca3af";
  return m <= limit * 0.5 ? "var(--good)" : m <= limit * 0.8 ? "var(--mid)" : "var(--far)";
}

/* ------------------------------------------------------------------ data */

async function load() {
  try {
    const r = await fetch("data/public.json?v=" + Date.now());
    if (!r.ok) throw new Error(r.status);
    DATA = await r.json();
  } catch (e) {
    $("#banner").hidden = false;
    $("#banner").textContent = "No data yet – the daily search has not run yet (data/public.json is missing).";
    DATA = { properties: [], sources: {}, runs: [], localities: [] };
  }
  WORK = { ...WORK, ...(DATA.workplace || {}) };
  $("#workName").textContent = WORK.short || WORK.name;
  ALL = (DATA.properties || []).filter(p => p.zip || p.lat);
  for (const p of ALL) {
    p._srcs = [...new Set((p.links || []).map(l => family(l.label)))];
    p._date = (p.published && p.published.slice(0, 10) < p.first_seen) ? p.published.slice(0, 10) : p.first_seen;
    const ph = p.price_history || [];
    const maxP = ph.length ? Math.max(...ph.map(h => h[1])) : null, lastP = ph.length ? ph[ph.length - 1][1] : null;
    p._dropPct = maxP && lastP && lastP < maxP ? (maxP - lastP) / maxP : 0;
    p._oldPrice = p._dropPct ? maxP : null;
    p._isNew = !p.baseline && daysBetween(p.first_seen, TODAY) <= 1;
    if (!p.car_km && p.lat) p.car_km = Math.round(km(p.lat, p.lng, WORK.lat, WORK.lng) * 1.3 * 10) / 10;
    p._type = p.property_type || "apartment";
  }
  // median rent per m² of comparable flats per place -> "good deal" badge
  const by = {};
  for (const p of ALL) if (p.active && p.price_per_m2) (by[p.municipality] ||= []).push(p.price_per_m2);
  const med = {}; for (const [k, v] of Object.entries(by)) if (v.length >= 4) med[k] = median(v);
  for (const p of ALL) p._deal = p.price_per_m2 && med[p.municipality] ? p.price_per_m2 / med[p.municipality] - 1 : null;
  computeCosts();
  const gen = DATA.generated ? new Date(DATA.generated) : null;
  const act = ALL.filter(p => p.active).length, nw = ALL.filter(p => p._isNew && p.active).length;
  $("#stats").textContent = `${act} flats for rent · ${nw} new today · updated ${gen ? gen.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "–"}`;
  if (gen && (Date.now() - gen) / 864e5 > 2.5) {
    $("#banner").hidden = false;
    $("#banner").textContent = `Note: the data is ${Math.floor((Date.now() - gen) / 864e5)} days old – the daily run may have failed (GitHub → Actions).`;
  }
}

/* ------------------------------------------------------------------ commute costs */

function commuteMoney(p) {
  const days = num(COSTS.days) ?? 20;
  if (COSTS.mode === "pt") return num(COSTS.ptPass) || 0;
  if (!p.car_km) return null;
  return p.car_km * 2 * days * (num(COSTS.perKm) ?? 0.7);
}
function commuteTime(p) {
  const m = COSTS.mode === "pt" ? p.pt_min : p.car_min;
  return m === null || m === undefined ? null : m * 2 * (num(COSTS.days) ?? 20) / 60;  // hours per month
}
function computeCosts() {
  for (const p of ALL) {
    const money = commuteMoney(p), hours = commuteTime(p);
    p._commuteCost = money;
    p._total = p.price && money !== null ? p.price + money : null;
    p._value = p._total !== null && hours !== null ? p._total + hours * (num(COSTS.timeValue) || 0) : null;
  }
}

/* ------------------------------------------------------------------ filtering */

function commuteOk(p, f) {
  const cm = num(f.maxCar) || null, pm = num(f.maxPt) || null;
  if (!cm && !pm) return true;
  const carOk = !cm || (p.car_min != null && p.car_min <= cm), ptOk = !pm || (p.pt_min != null && p.pt_min <= pm);
  if (f.commuteMode === "car") return carOk;
  if (f.commuteMode === "pt") return ptOk;
  if (f.commuteMode === "both") return carOk && ptOk;
  return (cm && carOk) || (pm && ptOk);
}
function inRange(v, lo, hi, miss) {
  lo = num(lo); hi = num(hi);
  if (lo === null && hi === null) return true;
  if (v === null || v === undefined) return miss;
  return (lo === null || v >= lo) && (hi === null || v <= hi);
}

function filterProps(list, f = F, skip = {}) {
  const terms = f.q.toLowerCase().split(/\s+/).filter(Boolean);
  const ex = f.qx.toLowerCase().split(",").map(s => s.trim()).filter(Boolean);
  const agency = f.agency.toLowerCase(), miss = f.includeMissing;
  const out = [];
  for (const p of list) {
    if (!f.showInactive && !p.active) continue;
    if (!f.showHidden && HIDDEN[p.id]) continue;
    if (!skip.commute && !commuteOk(p, f)) continue;
    if (f.exactOnly && !p.commute_exact) continue;
    if (!inRange(p.price, f.rentMin, f.rentMax, miss && !f.withPrice)) continue;
    if (f.withPrice && !p.price) continue;
    if (f.types.length && !f.types.includes(p._type)) continue;
    if (!inRange(p.rooms, f.roomsMin, f.roomsMax, miss)) continue;
    if (!inRange(p.living_area, f.areaMin, f.areaMax, miss)) continue;
    if (!inRange(p.price_per_m2, null, f.ppmMax, miss)) continue;
    const feats = p.features || {};
    if (f.furnished === "yes" && !feats.furnished) continue;
    if (f.furnished === "no" && feats.furnished) continue;
    if (!skip.place && f.cantons.length && !f.cantons.includes(p.canton)) continue;
    if (!skip.place && f.places.length && !f.places.includes(String(p.zip))) continue;
    let ok = true;
    for (const [k, v] of Object.entries({ ...f.feats, ...f.warns })) {
      if ((v === 1 && !feats[k]) || (v === -1 && feats[k])) { ok = false; break; }
    }
    if (!ok) continue;
    if (f.age && daysBetween(p._date, TODAY) > Number(f.age)) continue;
    if (f.onlyDrops && !p._dropPct) continue;
    if (f.withPhoto && !(p.images || []).length) continue;
    if (f.privateOnly && !p.private_seller) continue;
    if (f.multiSource && p._srcs.length < 2) continue;
    if (f.sources.length && !p._srcs.some(s => f.sources.includes(s))) continue;
    if (agency && !String(p.agency || "").toLowerCase().includes(agency)) continue;
    if (terms.length || ex.length) {
      const hay = `${p.title} ${p.description} ${p.street} ${p.zip} ${p.municipality} ${p.agency}`.toLowerCase();
      if (terms.some(t => !hay.includes(t)) || ex.some(t => hay.includes(t))) continue;
    }
    out.push(p);
  }
  const big = 1e15;
  const by = {
    value: (a, b) => (a._value ?? big) - (b._value ?? big),
    new: (a, b) => (b._date || "").localeCompare(a._date || ""),
    rentAsc: (a, b) => (a.price || big) - (b.price || big),
    carAsc: (a, b) => (a.car_min ?? big) - (b.car_min ?? big),
    ptAsc: (a, b) => (a.pt_min ?? big) - (b.pt_min ?? big),
    totalAsc: (a, b) => (a._total ?? big) - (b._total ?? big),
    ppmAsc: (a, b) => (a.price_per_m2 || big) - (b.price_per_m2 || big),
    areaDesc: (a, b) => (b.living_area || 0) - (a.living_area || 0),
    dropDesc: (a, b) => b._dropPct - a._dropPct,
  };
  return out.sort(by[f.sort] || by.value);
}

/* ------------------------------------------------------------------ rendering helpers */

function commuteHtml(p) {
  const approx = p.commute_exact ? "" : "≈";
  const cls = p.commute_exact ? "" : "approx";
  const tip = p.commute_exact ? "door to door from the flat's address" : "from the centre of " + (p.municipality || "the place");
  const parts = [];
  if (p.car_min != null) parts.push(`<span class="${cls}" title="${esc(tip)}"><i class="dot" style="background:${timeColor(p.car_min, 25)}"></i>🚗 ${approx}${Math.round(p.car_min)} min${p.car_km ? ` · ${p.car_km} km` : ""}</span>`);
  const ptApprox = p.pt_exact ? "" : "≈", ptCls = p.pt_exact ? "" : "approx";
  const ptTip = p.pt_exact ? "door to door from the flat's address, arriving ~08:00" : "from the centre of " + (p.municipality || "the place") + " (exact time follows in the next runs)";
  if (p.pt_min != null) parts.push(`<span class="${ptCls}" title="${esc(ptTip)}"><i class="dot" style="background:${timeColor(p.pt_min, 60)}"></i>🚆 ${ptApprox}${p.pt_min} min${p.pt_changes ? ` · ${p.pt_changes} change${p.pt_changes > 1 ? "s" : ""}` : " · direct"}</span>`);
  return parts.length ? `<div class="commute">${parts.join("")}</div>` : "";
}
function rentHtml(p) {
  let h = `<div class="price">${p.price ? `${chf(p.price)}<span class="per"> / month</span>` : "rent on request"}`;
  if (p._oldPrice) h += `<span class="old">${chf(p._oldPrice)}</span>`;
  h += "</div>";
  const bits = [];
  if (p.rent_net && p.charges) bits.push(`${chf(p.rent_net)} + ${Math.round(p.charges)} charges`);
  if (p._commuteCost != null && p.price) bits.push(`≈ ${chf(p.price + p._commuteCost)} incl. ${COSTS.mode === "pt" ? "travel pass" : "car commute"}`);
  if (bits.length) h += `<div class="rentdetail">${esc(bits.join(" · "))}</div>`;
  return h;
}
function factsHtml(p) {
  const f = [];
  f.push(`<b>${esc(TYPES[p._type] || "Flat")}</b>`);
  if (p.rooms && p._type !== "room") f.push(`${p.rooms} room${p.rooms === 1 ? "" : "s"}`);
  if (p.living_area) f.push(`${p.living_area} m²`);
  if (p.price_per_m2) f.push(`CHF ${p.price_per_m2}/m²`);
  if (p.floor !== null && p.floor !== undefined) f.push(p.floor === 0 ? "ground floor" : `floor ${p.floor}`);
  if (p.available_from) f.push(`available ${esc(p.available_from)}`);
  return f.join("<span class='muted'> · </span>");
}
function featHtml(p) {
  const fs = p.features || {};
  return Object.entries(FEATURES).filter(([k]) => fs[k]).map(([, v]) => `<span>${esc(v)}</span>`).join("")
    + Object.entries(WARNINGS).filter(([k]) => fs[k]).map(([, v]) => `<span class="w">⚠ ${esc(v)}</span>`).join("");
}

function cardHtml(p) {
  const img = (p.images || [])[0];
  const badges = [];
  if (p._isNew) badges.push(`<span class="badge new">NEW</span>`);
  if (p._dropPct) badges.push(`<span class="badge drop">−${Math.round(p._dropPct * 100)}%</span>`);
  if (p._deal !== null && p._deal <= -0.15) badges.push(`<span class="badge deal" title="rent per m² ${Math.round(-p._deal * 100)}% below the median of ${esc(p.municipality)}">good deal</span>`);
  if (!p.active) badges.push(`<span class="badge gone">taken / removed</span>`);
  const loc = [p.street, [p.zip, p.municipality].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  const links = (p.links || []).map(l => `<a href="${esc(safeUrl(l.url))}" target="_blank" rel="noopener" class="${l.active ? "" : "dead"}">${esc(family(l.label))}</a>`).join("");
  const note = NOTES[p.id] ? `<div class="note">📝 ${esc(NOTES[p.id])}</div>` : "";
  const age = daysBetween(p._date, TODAY);
  return `<article class="card ${p.active ? "" : "inactive"}" data-id="${esc(p.id)}">
    <div class="ph" data-act="open">${img ? `<img loading="lazy" src="${esc(safeUrl(img))}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'noimg',textContent:'🏠'}))">` : `<div class="noimg">🏠</div>`}
      <div class="badges">${badges.join("")}</div>${(p.images || []).length > 1 ? `<span class="imgcount">${p.images.length} photos</span>` : ""}</div>
    <div class="body">
      ${rentHtml(p)}
      ${commuteHtml(p)}
      <h3 data-act="open">${esc(p.title || "Flat")}</h3>
      <div class="facts">${factsHtml(p)}</div>
      <div class="loc">📍 ${esc(loc || "location unknown")}${p.canton ? ` <span class="muted">(${esc(p.canton)})</span>` : ""}</div>
      <div class="feat">${featHtml(p)}</div>${note}
      <div class="links">🔗 ${links}</div>
    </div>
    <div class="actions">
      <button data-act="fav" class="${FAVS[p.id] ? "on" : ""}" title="Favorite">★</button>
      <button data-act="note" title="Note">📝</button>
      <button data-act="hide" title="${HIDDEN[p.id] ? "unhide" : "hide"}">${HIDDEN[p.id] ? "↺" : "✕"}</button>
      <div class="meta">${age <= 0 ? "today" : age === 1 ? "yesterday" : `${age} days ago`}<br>${esc(p.agency || "")}</div>
    </div>
  </article>`;
}

function quickbar(list) {
  const prices = list.map(p => p.price).filter(Boolean);
  const studios = list.filter(p => p._type === "studio");
  const cheap = list.filter(p => p.price && p.price <= 900).length;
  const near = list.filter(p => p.car_min != null && p.car_min <= 15).length;
  const todays = list.filter(p => p._isNew).length;
  $("#quickbar").innerHTML = `
    <span class="kpi-mini"><b>${list.length}</b> flats</span>
    <span class="kpi-mini"><b>${studios.length}</b> studios</span>
    <span class="kpi-mini">cheapest <b>${prices.length ? chf(Math.min(...prices)) : "–"}</b></span>
    <span class="kpi-mini">median <b>${prices.length ? chf(median(prices)) : "–"}</b></span>
    <span class="kpi-mini"><b>${cheap}</b> at ≤ CHF 900</span>
    <span class="kpi-mini"><b>${near}</b> within 15 min by car</span>
    <span class="kpi-mini"><b>${todays}</b> new today</span>`;
}

function renderList(list) {
  quickbar(list);
  $("#cards").innerHTML = list.slice(0, shown).map(cardHtml).join("") || `<p class="muted">No flats match the filters.</p>`;
  $("#more").hidden = list.length <= shown;
}

function renderTable(list) {
  const cols = [["_date", "Listed"], ["title", "Title"], ["price", "Rent", 1], ["_type", "Type"], ["rooms", "Rooms", 1],
    ["living_area", "m²", 1], ["car_min", "🚗 min", 1], ["pt_min", "🚆 min", 1], ["_total", "Rent + commute", 1],
    ["municipality", "Place"], ["zip", "ZIP"], ["agency", "Agency"], ["_srcs", "Sources"]];
  const k = tableSort.k, d = tableSort.d;
  const rows = [...list].sort((a, b) => {
    const x = a[k], y = b[k];
    if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
    return (typeof x === "number" ? x - y : String(x).localeCompare(String(y))) * d;
  });
  const fmt = (p, c) => {
    const v = p[c];
    if (v == null) return "";
    if (c === "price" || c === "_total") return Math.round(v).toLocaleString("de-CH");
    if (c === "car_min" || c === "pt_min") return Math.round(v) + ((c === "car_min" ? p.commute_exact : p.pt_exact) ? "" : "≈");
    if (c === "_type") return esc(TYPES[v] || v);
    if (c === "_srcs") return esc(v.join(", "));
    if (c === "title") return `<a href="#" data-open="${esc(p.id)}">${esc(String(v).slice(0, 60))}</a>`;
    return esc(v);
  };
  $("#table").innerHTML = `<thead><tr>${cols.map(([c, l, n]) => `<th data-k="${c}" class="${n ? "num" : ""}">${l}${k === c ? (d > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead>
    <tbody>${rows.slice(0, 2000).map(p => `<tr>${cols.map(([c, , n]) => `<td class="${n ? "num" : ""}">${fmt(p, c)}</td>`).join("")}</tr>`).join("")}</tbody>`;
}

/* ------------------------------------------------------------------ map */

function ensureMap() {
  if (map || typeof L === "undefined") return;
  map = L.map("map").setView([WORK.lat, WORK.lng], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
  mapLayer = L.layerGroup().addTo(map);
  L.marker([WORK.lat, WORK.lng], { icon: L.divIcon({ className: "work-icon", html: "🏢", iconSize: [28, 28], iconAnchor: [14, 14] }), zIndexOffset: 1000 })
    .addTo(map).bindTooltip(WORK.name, { permanent: false });
}
function markerColor(p, metric) {
  const css = getComputedStyle(document.documentElement);
  const c = name => css.getPropertyValue(name).trim();
  if (metric === "rent") {
    if (!p.price) return "#9ca3af";
    return p.price <= 800 ? c("--good") : p.price <= 1000 ? c("--mid") : c("--far");
  }
  const m = metric === "pt" ? p.pt_min : p.car_min, lim = metric === "pt" ? 60 : 25;
  if (m == null) return "#9ca3af";
  return m <= lim * 0.5 ? c("--good") : m <= lim * 0.8 ? c("--mid") : c("--far");
}
function renderMap(list) {
  ensureMap(); if (!map) { $("#mapNote").textContent = "Map could not be loaded."; return; }
  setTimeout(() => map.invalidateSize(), 50);
  mapLayer.clearLayers();
  const metric = $("#mapColor").value;
  const leg = metric === "rent" ? ["≤ CHF 800", "≤ CHF 1000", "more"] : metric === "pt" ? ["≤ 30 min", "≤ 48 min", "longer"] : ["≤ 12 min", "≤ 20 min", "longer"];
  $("#legend").innerHTML = ["--good", "--mid", "--far"].map((c, i) => `<span><i class="dot" style="background:var(${c})"></i>${leg[i]}</span>`).join("") + `<span>🏢 ${esc(WORK.short || "work")}</span>`;
  const cent = {}; for (const l of DATA.localities || []) cent[l.zip] ||= [l.lat, l.lng];
  let n = 0, approx = 0;
  for (const p of list) {
    let ll = p.lat ? [p.lat, p.lng] : cent[p.zip];
    if (!ll) continue;
    if (!p.lat) { approx++; ll = [ll[0] + (Math.random() - .5) * .006, ll[1] + (Math.random() - .5) * .009]; }
    n++;
    const m = L.circleMarker(ll, { radius: p._type === "studio" ? 8 : 6, color: "#fff", weight: 1.5, fillColor: markerColor(p, metric), fillOpacity: p.lat ? .95 : .55 });
    const img = (p.images || [])[0];
    m.bindPopup(`<div class="map-pop">${img ? `<img src="${esc(safeUrl(img))}" alt="">` : ""}<b>${p.price ? chf(p.price) + " / month" : "rent on request"}</b><br>${esc(p.title || "")}<br>
      <span class="muted">${esc(TYPES[p._type] || "")}${p.living_area ? " · " + p.living_area + " m²" : ""} · ${esc(p.municipality || "")}</span><br>
      🚗 ${minutes(p.car_min)} · 🚆 ${minutes(p.pt_min)}${p.commute_exact ? "" : " (approx.)"}<br>
      <a href="#" data-open="${esc(p.id)}">Details</a> · <a href="${esc(safeUrl(p.url))}" target="_blank" rel="noopener">Open ad</a></div>`);
    m.addTo(mapLayer);
  }
  $("#mapNote").textContent = `${n} of ${list.length} flats on the map (${approx} placed at the centre of their village/town – exact address unknown). Bigger dots = studios.`;
}

/* ------------------------------------------------------------------ places & prices */

function renderPlaces(list) {
  const base = filterProps(ALL, F, { place: true, commute: true });  // show the whole trade-off
  const by = {};
  for (const p of base) (by[p.zip] ||= []).push(p);
  const rows = (DATA.localities || []).map(l => {
    const ps = by[l.zip] || [], prices = ps.map(p => p.price).filter(Boolean);
    const studios = ps.filter(p => p._type === "studio").map(p => p.price).filter(Boolean);
    const ppm = ps.map(p => p.price_per_m2).filter(Boolean);
    return { ...l, n: ps.length, cheapest: prices.length ? Math.min(...prices) : null, median: median(prices),
      studio: studios.length ? Math.min(...studios) : null, ppm: median(ppm), sel: F.places.includes(l.zip) };
  });
  const seen = new Set(), dedup = rows.filter(r => !seen.has(r.zip + r.name) && seen.add(r.zip + r.name));
  const k = placesSort.k, d = placesSort.d;
  dedup.sort((a, b) => (a[k] == null) - (b[k] == null) || (typeof a[k] === "number" ? (a[k] - b[k]) : String(a[k]).localeCompare(String(b[k]))) * d);
  const maxN = Math.max(1, ...dedup.map(r => r.n));
  const cols = [["name", "Place"], ["canton", "Canton"], ["car_min", "🚗 min", 1], ["pt_min", "🚆 min", 1], ["n", "Flats", 1],
    ["studio", "Cheapest studio", 1], ["cheapest", "Cheapest flat", 1], ["median", "Median rent", 1], ["ppm", "CHF/m²", 1]];
  const metricLabel = scatterMetric === "pt" ? "public transport" : "car";
  $("#places").innerHTML = `
  <div class="panel"><h2>Rent vs. commute</h2>
    <p class="muted small">Every dot is a flat matching your current filters (except commute). The green box is the sweet spot:
    ≤ ${num(F.maxCar) || 20} min by ${metricLabel} and ≤ ${chf(num(F.rentMax) || 900)}. Click a dot to open it.</p>
    <div class="chips" id="scatterMetric"><span class="chip ${scatterMetric === "car" ? "on" : ""}" data-m="car">🚗 car time</span><span class="chip ${scatterMetric === "pt" ? "on" : ""}" data-m="pt">🚆 public transport time</span></div>
    <div class="scatter-wrap">${scatterSvg(base)}</div></div>
  <div class="panel"><h2>Places within reach</h2>
    <p class="muted small">Drive / public-transport time from the centre of each place to ${esc(WORK.name)} (arrival ~08:00 on a working day).
    Rents reflect your current filters. Click a place to show only its flats.</p>
    <div class="table-wrap"><table><thead><tr>${cols.map(([c, l, n]) => `<th data-pk="${c}" class="${n ? "num" : ""}">${l}${placesSort.k === c ? (placesSort.d > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead>
    <tbody>${dedup.map(r => `<tr>
      <td><a href="#" data-place="${esc(r.zip)}">${r.sel ? "✔ " : ""}${esc(r.zip)} ${esc(r.name)}</a></td><td>${esc(r.canton)}</td>
      <td class="num"><i class="dot" style="background:${timeColor(r.car_min, 25)}"></i>${Math.round(r.car_min)}</td>
      <td class="num"><i class="dot" style="background:${timeColor(r.pt_min, 60)}"></i>${r.pt_min ?? "–"}</td>
      <td class="num"><span class="bar" style="width:${Math.round(40 * r.n / maxN)}px"></span>${r.n}</td>
      <td class="num">${r.studio ? Math.round(r.studio).toLocaleString("de-CH") : ""}</td>
      <td class="num">${r.cheapest ? Math.round(r.cheapest).toLocaleString("de-CH") : ""}</td>
      <td class="num">${r.median ? Math.round(r.median).toLocaleString("de-CH") : ""}</td>
      <td class="num">${r.ppm ? r.ppm.toFixed(1) : ""}</td></tr>`).join("")}</tbody></table></div></div>`;
}

function scatterSvg(list) {
  const W = 760, H = 360, pad = { l: 56, r: 14, t: 12, b: 36 };
  const pts = list.filter(p => p.price && (scatterMetric === "pt" ? p.pt_min != null : p.car_min != null));
  if (!pts.length) return `<p class="muted">No flats with rent and commute time.</p>`;
  const xs = pts.map(p => scatterMetric === "pt" ? p.pt_min : p.car_min);
  const xMax = Math.max(scatterMetric === "pt" ? 60 : 25, ...xs), yMax = Math.min(Math.max(...pts.map(p => p.price)), 3000), yMin = Math.min(...pts.map(p => p.price), 400);
  const X = v => pad.l + (v / xMax) * (W - pad.l - pad.r), Y = v => H - pad.b - ((Math.min(v, yMax) - yMin) / (yMax - yMin || 1)) * (H - pad.t - pad.b);
  const sx = num(F.maxCar) && scatterMetric === "car" ? num(F.maxCar) : num(F.maxPt) && scatterMetric === "pt" ? num(F.maxPt) : (scatterMetric === "pt" ? 35 : 20);
  const sy = num(F.rentMax) || 900;
  const css = getComputedStyle(document.documentElement);
  const colors = { studio: css.getPropertyValue("--accent").trim(), room: css.getPropertyValue("--warn").trim() };
  let g = `<rect class="sweet" x="${X(0)}" y="${Y(Math.max(sy, yMin))}" width="${X(Math.min(sx, xMax)) - X(0)}" height="${Y(yMin) - Y(Math.max(sy, yMin))}"/>`;
  for (let t = 0; t <= xMax; t += scatterMetric === "pt" ? 10 : 5) g += `<line class="axis" x1="${X(t)}" x2="${X(t)}" y1="${pad.t}" y2="${H - pad.b}"/><text x="${X(t)}" y="${H - pad.b + 14}" text-anchor="middle">${t}′</text>`;
  const step = yMax - yMin > 1500 ? 500 : 250;
  for (let v = Math.ceil(yMin / step) * step; v <= yMax; v += step) g += `<line class="axis" x1="${pad.l}" x2="${W - pad.r}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${pad.l - 6}" y="${Y(v) + 4}" text-anchor="end">${v.toLocaleString("de-CH")}</text>`;
  g += `<text x="${(W + pad.l) / 2}" y="${H - 4}" text-anchor="middle">${scatterMetric === "pt" ? "public transport" : "car"} minutes to ${esc(WORK.short || "work")}</text>`;
  g += `<text x="12" y="${H / 2}" transform="rotate(-90 12 ${H / 2})" text-anchor="middle">rent CHF / month</text>`;
  for (const p of pts) {
    const x = scatterMetric === "pt" ? p.pt_min : p.car_min;
    g += `<circle class="pt" data-open="${esc(p.id)}" cx="${X(x).toFixed(1)}" cy="${Y(p.price).toFixed(1)}" r="${p._type === "studio" ? 5 : 3.5}" fill="${colors[p._type] || "#94a3b8"}" opacity="${p.commute_exact ? .9 : .5}"><title>${esc(p.title)} – ${chf(p.price)} – ${esc(p.municipality || "")} – ${Math.round(x)} min</title></circle>`;
  }
  return `<svg class="scatter" viewBox="0 0 ${W} ${H}" role="img" aria-label="rent versus commute">${g}</svg>
    <p class="muted small"><i class="dot" style="background:var(--accent)"></i>studio <i class="dot" style="background:#94a3b8"></i>other flat <i class="dot" style="background:var(--warn)"></i>room · faded = approximate commute (no exact address)</p>`;
}

/* ------------------------------------------------------------------ costs, favorites, sources */

function renderCosts() {
  const field = (k, l, step, hint) => `<label><span class="lbl">${l}</span><input data-cost="${k}" type="number" step="${step}" value="${esc(COSTS[k])}" placeholder="${hint || ""}"></label>`;
  const inc = num(COSTS.income);
  const list = filterProps(ALL);
  const withTotal = list.filter(p => p._total != null).sort((a, b) => a._total - b._total);
  $("#costs").innerHTML = `
  <div class="panel"><h2>What does the commute cost?</h2>
    <p class="muted small">Used for "Best value" and "Total monthly cost" sorting and shown on every card. A cheap flat far away can cost more in the end.</p>
    <div class="grid2">
      <label><span class="lbl">I mostly commute by</span><select data-cost="mode"><option value="car" ${COSTS.mode === "car" ? "selected" : ""}>car</option><option value="pt" ${COSTS.mode === "pt" ? "selected" : ""}>public transport</option></select></label>
      ${field("days", "Commuting days per month", 1)}
      ${field("perKm", "Car cost per km (CHF) – TCS full cost ≈ 0.70, fuel only ≈ 0.12", 0.05)}
      ${field("ptPass", "Monthly travel pass (CHF), e.g. Onde Verte zones", 5, "0")}
      ${field("timeValue", "Value of 1 hour of commuting (CHF) – for 'Best value'", 1)}
      ${field("income", "Optional: net monthly income (CHF) for the ⅓ rent rule", 100, "e.g. 6000")}
    </div>
    <div class="kpis">
      <div class="kpi"><span class="muted small">Cheapest rent + commute in your results</span><b>${withTotal.length ? chf(withTotal[0]._total) : "–"}</b><span class="small">${withTotal.length ? esc(withTotal[0].municipality || "") : ""}</span></div>
      <div class="kpi"><span class="muted small">Commute cost for 10 km by car</span><b>${chf(10 * 2 * (num(COSTS.days) || 20) * (num(COSTS.perKm) || 0))}</b><span class="small">per month</span></div>
      <div class="kpi"><span class="muted small">Max rent by the ⅓ rule</span><b>${inc ? chf(inc / 3) : "–"}</b><span class="small">landlords usually ask income ≥ 3× rent</span></div>
    </div>
  </div>`;
}

function renderFavs() {
  const favs = ALL.filter(p => FAVS[p.id]).sort((a, b) => (FAVS[b.id] || 0) - (FAVS[a.id] || 0));
  $("#favCards").innerHTML = favs.map(cardHtml).join("") || `<p class="muted">No favorites yet – click ★ on a flat.</p>`;
}

function renderSources() {
  const S = DATA.sources || {};
  const ent = Object.entries(S).sort((a, b) => (a[1].kind !== "portal") - (b[1].kind !== "portal") || a[1].label.localeCompare(b[1].label));
  const runs = (DATA.runs || []).slice(-14).reverse();
  $("#sources").innerHTML = `
  <div class="panel"><h2>Searched automatically every morning (${ent.length})</h2>
    <p class="muted small">Portals (Flatfox, immobilier.ch, Newhome, petitesannonces.ch), aggregators (Comparis and RealAdvisor also carry Homegate,
    ImmoScout24 and many agency feeds) and the websites of local property managers. The same flat on several sites is merged into one card.
    Sites that refuse automated access are respected – see below.</p>
    <div class="table-wrap"><table><thead><tr><th>Source</th><th>Type</th><th>Status</th><th class="num">Flats</th><th>Last OK</th></tr></thead><tbody>
    ${ent.map(([k, s]) => `<tr><td>${s.url ? `<a href="${esc(safeUrl(s.url))}" target="_blank" rel="noopener">${esc(s.label)}</a>` : esc(s.label)}</td><td>${esc(s.kind)}</td>
      <td class="${s.status === "ok" ? "status-ok" : "status-bad"}">${esc(s.status)}</td><td class="num">${s.count ?? ""}</td><td>${esc(s.last_ok || "–")}</td></tr>`).join("")}
    </tbody></table></div></div>
  <div class="panel"><h2>Check manually / create their own alerts</h2>
    <p class="muted small">These sites block automated searches or only work in a browser. Most of their ads still reach this app through
    Comparis and RealAdvisor – for complete coverage, create a free e-mail alert on Homegate, ImmoScout24 and anibis with your criteria.</p>
    <ul>${MANUAL_LINKS.map(([l, u]) => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(l)}</a></li>`).join("")}</ul></div>
  <div class="panel"><h2>Recent runs</h2>
    <table><thead><tr><th>Day</th><th class="num">New</th><th class="num">Rent changes</th><th class="num">Active</th></tr></thead>
    <tbody>${runs.map(r => `<tr><td>${esc(r.day)}</td><td class="num">${r.new}</td><td class="num">${r.price_changes}</td><td class="num">${r.active}</td></tr>`).join("")}</tbody></table></div>`;
}

function openDetail(id) {
  const p = ALL.find(x => x.id === id); if (!p) return;
  SEEN[id] = 1; store.set("seen", SEEN);
  const hist = (p.price_history || []).map(h => `<span>${esc(h[0])}: ${chf(h[1])}</span>`).join("");
  const origin = p.lat ? `${p.lat},${p.lng}` : [p.street, p.zip, p.municipality].filter(Boolean).join(" ");
  const dest = `${WORK.lat},${WORK.lng}`;
  const gm = mode => `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origin)}&destination=${dest}&travelmode=${mode}`;
  const sbb = `https://www.sbb.ch/en?stops=${encodeURIComponent(JSON.stringify([{ value: "", type: "COORDINATES", label: origin }]))}`;
  const rows = [
    ["Rent", p.price ? chf(p.price) + " / month" : "on request"], ["Net rent + charges", p.rent_net && p.charges ? `${chf(p.rent_net)} + ${Math.round(p.charges)}` : null],
    ["Rent + commute", p._total ? `${chf(p._total)} / month (${COSTS.mode === "pt" ? "travel pass" : "car, " + (num(COSTS.perKm) || 0) + " CHF/km"})` : null],
    ["Type", TYPES[p._type]], ["Rooms", p.rooms], ["Living area", p.living_area && p.living_area + " m²"],
    ["Rent per m²", p.price_per_m2 && `CHF ${p.price_per_m2} / month`], ["Floor", p.floor === 0 ? "ground floor" : p.floor],
    ["Available", p.available_from], ["Built / renovated", [p.year_built, p.year_renovated].filter(Boolean).join(" / ")],
    ["Address", [p.street, p.zip, p.municipality].filter(Boolean).join(" ")], ["Canton", CANTONS[p.canton] || p.canton],
    ["Agency / landlord", p.agency], ["First seen", p.first_seen], ["Published", p.published && p.published.slice(0, 10)], ["Last seen", p.last_seen],
  ].filter(r => r[1] !== null && r[1] !== undefined && r[1] !== "");
  $("#detailBody").innerHTML = `<div class="detail">
    <div class="gallery">${(p.images || []).map(i => `<img src="${esc(safeUrl(i))}" alt="" loading="lazy">`).join("")}</div>
    <button class="btn close" data-close>✕</button>
    ${rentHtml(p)}${commuteHtml(p)}<h2 style="margin:6px 0 8px">${esc(p.title)}</h2>
    <div class="route-btns">
      <a class="btn" href="${esc(gm("driving"))}" target="_blank" rel="noopener">🚗 Car route to ${esc(WORK.short || "work")}</a>
      <a class="btn" href="${esc(gm("transit"))}" target="_blank" rel="noopener">🚆 Public transport route</a>
      <a class="btn" href="${esc(sbb)}" target="_blank" rel="noopener">SBB timetable</a>
    </div>
    ${p.commute_exact ? "" : `<p class="muted small">Commute times are from the centre of ${esc(p.municipality || "the place")} – the exact address isn't published.</p>`}
    <div class="feat" style="margin-bottom:10px">${featHtml(p)}</div>
    <dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
    ${hist ? `<div class="lbl">Rent history</div><div class="hist">${hist}</div>` : ""}
    <div class="lbl">Ads</div><div class="links">${(p.links || []).map(l => `<a href="${esc(safeUrl(l.url))}" target="_blank" rel="noopener" class="${l.active ? "" : "dead"}">${esc(l.label)} ↗</a>`).join("")}</div>
    ${p.parsed_from_text ? `<p class="muted small">Numbers were read automatically from the ad text – please verify in the ad.</p>` : ""}
    ${p.description ? `<div class="lbl">Description</div><div class="desc">${esc(p.description)}</div>` : ""}
    <div class="lbl">Your note</div><textarea id="noteText" rows="3" placeholder="e.g. visit on …, called the agency on …">${esc(NOTES[p.id] || "")}</textarea>
    <div style="display:flex;gap:8px;margin-top:8px"><button class="btn primary" data-savenote="${esc(p.id)}">Save note</button>
    <button class="btn" data-favd="${esc(p.id)}">${FAVS[p.id] ? "★ Remove favorite" : "☆ Add to favorites"}</button></div>
  </div>`;
  $("#detail").showModal();
}

/* ------------------------------------------------------------------ filter UI */

function chipGroup(el, entries, getState, onClick) {
  el.innerHTML = entries.map(([k, l, c]) => `<span class="chip ${getState(k)}" data-k="${esc(k)}">${esc(l)}${c != null ? ` <span class="muted">${c}</span>` : ""}</span>`).join("");
  el.onclick = e => { const c = e.target.closest(".chip"); if (c) onClick(c.dataset.k); };
}
function toggleIn(arr, k) { const i = arr.indexOf(k); i >= 0 ? arr.splice(i, 1) : arr.push(k); }

function buildFilterUI() {
  const act = ALL.filter(p => p.active);
  const cnt = fn => act.reduce((m, p) => { const k = fn(p); m[k] = (m[k] || 0) + 1; return m; }, {});
  chipGroup($("#carChips"), [["10", "≤ 10′"], ["15", "≤ 15′"], ["20", "≤ 20′"], ["25", "≤ 25′"]], k => String(F.maxCar) === k ? "on" : "", k => { F.maxCar = String(F.maxCar) === k ? 0 : Number(k); apply(); });
  chipGroup($("#ptChips"), [["20", "≤ 20′"], ["30", "≤ 30′"], ["45", "≤ 45′"], ["60", "≤ 60′"]], k => String(F.maxPt) === k ? "on" : "", k => { F.maxPt = String(F.maxPt) === k ? 0 : Number(k); apply(); });
  chipGroup($("#rentChips"), [["700", "≤ 700"], ["800", "≤ 800"], ["900", "≤ 900"], ["1000", "≤ 1000"], ["1200", "≤ 1200"]], k => String(F.rentMax) === k ? "on" : "", k => { F.rentMax = String(F.rentMax) === k ? "" : k; apply(); });
  const tc = cnt(p => p._type);
  chipGroup($("#typeChips"), Object.entries(TYPES).map(([k, l]) => [k, l, tc[k] || 0]), k => F.types.includes(k) ? "on" : "", k => { toggleIn(F.types, k); apply(); });
  const cc = cnt(p => p.canton);
  chipGroup($("#cantonChips"), Object.entries(CANTONS).map(([k, l]) => [k, l, cc[k] || 0]), k => F.cantons.includes(k) ? "on" : "", k => { toggleIn(F.cantons, k); apply(); });
  const tri = (obj, k) => { obj[k] = obj[k] === 1 ? -1 : obj[k] === -1 ? 0 : 1; if (!obj[k]) delete obj[k]; apply(); };
  const triState = obj => k => obj[k] === 1 ? "on" : obj[k] === -1 ? "off" : "";
  const fc = {}; for (const p of act) for (const k in (p.features || {})) fc[k] = (fc[k] || 0) + 1;
  chipGroup($("#featureChips"), Object.entries(FEATURES).map(([k, l]) => [k, l, fc[k] || 0]), triState(F.feats), k => tri(F.feats, k));
  chipGroup($("#warnChips"), Object.entries(WARNINGS).map(([k, l]) => [k, l, fc[k] || 0]), triState(F.warns), k => tri(F.warns, k));
  const pc = cnt(p => String(p.zip));
  const places = [], seen = new Set();
  for (const l of [...(DATA.localities || [])].sort((a, b) => a.car_min - b.car_min)) {
    if (seen.has(l.zip)) continue; seen.add(l.zip); places.push(l);
  }
  const renderPlaces = () => {
    const q = $("#placeSearch").value.toLowerCase();
    $("#placeList").innerHTML = places.filter(l => (l.zip + " " + l.name).toLowerCase().includes(q)).map(l =>
      `<label><input type="checkbox" value="${esc(l.zip)}" ${F.places.includes(l.zip) ? "checked" : ""}> ${esc(l.zip)} ${esc(l.name)} <span class="cnt">🚗${Math.round(l.car_min)}′ 🚆${l.pt_min ?? "–"}′ · ${pc[l.zip] || 0}</span></label>`).join("");
  };
  renderPlaces(); $("#placeSearch").oninput = renderPlaces;
  $("#placeList").onchange = e => { toggleIn(F.places, e.target.value); apply(false); };
  $("#placeClear").onclick = () => { F.places = []; apply(); };
  const sc = {}; for (const p of act) for (const s of p._srcs) sc[s] = (sc[s] || 0) + 1;
  $("#sourceList").innerHTML = Object.keys(sc).sort((a, b) => sc[b] - sc[a]).map(s =>
    `<label><input type="checkbox" value="${esc(s)}" ${F.sources.includes(s) ? "checked" : ""}> ${esc(s)} <span class="cnt">${sc[s]}</span></label>`).join("");
  $("#sourceList").onchange = e => { toggleIn(F.sources, e.target.value); apply(false); };
}

const SIMPLE = ["q", "qx", "rentMin", "rentMax", "roomsMin", "roomsMax", "areaMin", "areaMax", "ppmMax", "age", "agency", "sort", "commuteMode", "furnished"];
const BOOLS = ["exactOnly", "withPrice", "includeMissing", "onlyDrops", "withPhoto", "privateOnly", "multiSource", "showInactive", "showHidden"];

function syncInputs() {
  for (const k of SIMPLE) { const el = $("#" + k); if (el) el.value = F[k] ?? ""; }
  for (const k of BOOLS) { const el = $("#" + k); if (el) el.checked = !!F[k]; }
  $("#maxCar").value = F.maxCar || 0; $("#maxPt").value = F.maxPt || 0;
  $("#carOut").textContent = F.maxCar ? `≤ ${F.maxCar} min` : "any";
  $("#ptOut").textContent = F.maxPt ? `≤ ${F.maxPt} min` : "any";
  buildFilterUI();
}

function bindInputs() {
  let t;
  for (const k of SIMPLE) {
    const el = $("#" + k); if (!el) continue;
    el.addEventListener("input", () => { F[k] = el.value; clearTimeout(t); t = setTimeout(() => apply(k === "sort"), 250); });
  }
  for (const k of BOOLS) { const el = $("#" + k); if (el) el.addEventListener("change", () => { F[k] = el.checked; apply(false); }); }
  for (const [id, key, out] of [["#maxCar", "maxCar", "#carOut"], ["#maxPt", "maxPt", "#ptOut"]]) {
    $(id).addEventListener("input", e => { F[key] = Number(e.target.value); $(out).textContent = F[key] ? `≤ ${F[key]} min` : "any"; clearTimeout(t); t = setTimeout(() => apply(), 200); });
  }
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
  if (VIEW === "places") renderPlaces(list);
  if (VIEW === "table") renderTable(list);
  if (VIEW === "favs") renderFavs();
  if (VIEW === "costs") renderCosts();
  if (VIEW === "sources") renderSources();
  render._list = list;
}

function setView(v) {
  VIEW = v;
  $$(".tabs button").forEach(b => b.classList.toggle("active", b.dataset.view === v));
  $$(".view").forEach(s => s.classList.toggle("active", s.id === "view-" + v));
  render();
}

/* ------------------------------------------------------------------ presets / share / e-mail filter */

function encodeFilters(f) { return btoa(unescape(encodeURIComponent(JSON.stringify(f)))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); }
function decodeFilters(s) { try { return JSON.parse(decodeURIComponent(escape(atob(s.replace(/-/g, "+").replace(/_/g, "/"))))); } catch (e) { return null; } }

function renderPresets() {
  const P = store.get("presets", {});
  $("#presetList").innerHTML = Object.keys(P).map(n => `<div class="preset"><a href="#" data-preset="${esc(n)}">${esc(n)}</a><button class="link-btn small" data-delpreset="${esc(n)}">delete</button></div>`).join("");
}

function emailFilterJson() {
  const n = v => num(v);
  const all = { ...F.feats, ...F.warns };
  return JSON.stringify({
    rent_min: n(F.rentMin), rent_max: n(F.rentMax), rooms_min: n(F.roomsMin), rooms_max: n(F.roomsMax),
    area_min: n(F.areaMin), area_max: n(F.areaMax), rent_per_m2_max: n(F.ppmMax),
    max_car_min: n(F.maxCar) || null, max_pt_min: n(F.maxPt) || null, commute_mode: F.commuteMode,
    cantons: F.cantons, localities: F.places, types: F.types, exclude_types: [], furnished: F.furnished,
    require_features: Object.keys(all).filter(k => all[k] === 1), exclude_features: Object.keys(all).filter(k => all[k] === -1),
    exclude_keywords: F.qx.split(",").map(s => s.trim()).filter(Boolean), include_keywords_any: [],
    include_keywords_all: F.q.toLowerCase().split(/\s+/).filter(Boolean),
    require_rent: !!F.withPrice, exact_address_only: !!F.exactOnly, private_only: !!F.privateOnly,
    include_missing_values: !!F.includeMissing,
  }, null, 2);
}

async function copy(text, msg) {
  try { await navigator.clipboard.writeText(text); toast(msg); } catch (e) { ioDialog("Copy", text, null); }
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
  $("#mapColor").addEventListener("change", () => render());
  document.addEventListener("click", e => {
    const t = e.target;
    const open = t.closest("[data-open]"); if (open) { e.preventDefault(); openDetail(open.dataset.open); return; }
    if (t.closest("[data-close]")) { $("#detail").close(); return; }
    const pl = t.closest("[data-place]"); if (pl) { e.preventDefault(); toggleIn(F.places, pl.dataset.place); apply(); toast(F.places.length ? "Place filter set – see List" : "Place filter cleared"); return; }
    const pk = t.closest("[data-pk]"); if (pk) { const k = pk.dataset.pk; placesSort = { k, d: placesSort.k === k ? -placesSort.d : 1 }; render(); return; }
    const sm = t.closest("#scatterMetric .chip"); if (sm) { scatterMetric = sm.dataset.m; render(); return; }
    const sn = t.closest("[data-savenote]");
    if (sn) { const v = $("#noteText").value.trim(); v ? NOTES[sn.dataset.savenote] = v : delete NOTES[sn.dataset.savenote]; store.set("notes", NOTES); toast("Note saved"); render(); return; }
    const fd = t.closest("[data-favd]");
    if (fd) { const id = fd.dataset.favd; FAVS[id] ? delete FAVS[id] : FAVS[id] = Date.now(); store.set("favs", FAVS); $("#detail").close(); render(); return; }
    const pr = t.closest("[data-preset]");
    if (pr) { e.preventDefault(); const P = store.get("presets", {}); F = { ...clone(DEFAULT_FILTERS), ...P[pr.dataset.preset] }; apply(); toast("Search loaded"); return; }
    const dp = t.closest("[data-delpreset]");
    if (dp) { const P = store.get("presets", {}); delete P[dp.dataset.delpreset]; store.set("presets", P); renderPresets(); return; }
    const card = t.closest(".card"), act = t.closest("[data-act]");
    if (card && act) {
      const id = card.dataset.id, a = act.dataset.act;
      if (a === "open" || a === "note") openDetail(id);
      if (a === "fav") { FAVS[id] ? delete FAVS[id] : FAVS[id] = Date.now(); store.set("favs", FAVS); render(); }
      if (a === "hide") { HIDDEN[id] ? delete HIDDEN[id] : HIDDEN[id] = 1; store.set("hidden", HIDDEN); render(); toast(HIDDEN[id] ? "Hidden (tick “show hidden” to see it again)" : "Unhidden"); }
    }
  });
  $("#table").addEventListener("click", e => { const th = e.target.closest("th"); if (!th) return; const k = th.dataset.k; tableSort = { k, d: tableSort.k === k ? -tableSort.d : (["title", "municipality", "agency", "zip", "_type"].includes(k) ? 1 : (k === "_date" ? -1 : 1)) }; render(); });
  $("#costs").addEventListener("change", e => { const k = e.target.dataset.cost; if (!k) return; COSTS[k] = e.target.value; store.set("costs", COSTS); computeCosts(); renderCosts(); });
  $("#savePreset").addEventListener("click", () => { const n = $("#presetName").value.trim(); if (!n) return toast("Please enter a name"); const P = store.get("presets", {}); P[n] = clone(F); store.set("presets", P); $("#presetName").value = ""; renderPresets(); toast("Search saved"); });
  $("#shareLink").addEventListener("click", () => copy(location.href.split("#")[0] + "#f=" + encodeFilters(F), "Link copied"));
  $("#emailFilter").addEventListener("click", () => copy(emailFilterJson(), "E-mail filter copied – paste it into config/email_filters.json"));
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
  const fromHash = location.hash.startsWith("#f=") ? decodeFilters(location.hash.slice(3).split("&")[0]) : null;
  F = { ...clone(DEFAULT_FILTERS), ...(fromHash || store.get("filters", {})) };
  if (location.hash === "#new") { F = clone(DEFAULT_FILTERS); F.age = "1"; F.sort = "new"; }
  bindInputs(); bindEvents(); syncInputs(); renderPresets();
  const v = (location.hash.match(/view=(\w+)/) || [])[1];
  if (v && document.getElementById("view-" + v)) setView(v); else render();
  const d = (location.hash.match(/detail=([^&]+)/) || [])[1];
  if (d) openDetail(decodeURIComponent(d));
})();
