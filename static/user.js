/* Outfit-Dashboard-MK1 – Nutzermodus */
"use strict";

const state = {
  meta: null,
  weather: null,
  clothes: [],
  activity: store("outfit.activity") || "alle",
  typeFilter: "alle",
};

const colorById = id => (state.meta.colors.find(c => c.id === id) || null);
const typeName = id => ((state.meta.types.find(t => t.id === id) || {}).name || id);
const actName = id => ((state.meta.activities.find(a => a.id === id) || {}).name || id);
const subName = it => {
  const subs = (state.meta.subtypes || {})[it.type] || [];
  return (subs.find(x => x.id === it.subtype) || {}).name || "";
};
const itemTypeName = it => subName(it) || typeName(it.type);
const L = () => ({ t: state.meta.temp_levels, r: state.meta.rain_levels });

/* ---------------- Wetter ---------------- */
function renderWeather() {
  const el = $("#weather");
  const w = state.weather;
  const loc = state.meta.location || {};
  if (!w || !w.ok) {
    const msg = (w && w.message) || "Wetterdaten nicht verfügbar.";
    el.innerHTML = `
      ${weatherIcon("cloud")}
      <div><div class="wx-desc">${esc(msg)}</div>
      ${w && w.error === "no_location" ? `<a class="small" href="/einstellungen">→ Standort festlegen</a>` : ""}</div>
      <div class="wx-note dim">Die Zusammenstellung berücksichtigt ohne Wetterdaten nur Farbe und Aktivität.</div>`;
    return;
  }
  const c = w.current, t = w.today;
  const prob = t.precip_prob != null ? `<div class="p">${fmtNum(t.precip_prob)} % Wahrsch.</div>` : "";
  el.innerHTML = `
    ${weatherIcon(c.icon)}
    <div class="wx-now">
      <span class="wx-temp">${fmtNum(c.temp, 1)}°</span>
      <span class="wx-desc">${esc(c.text)}${c.apparent != null ? ` · gefühlt ${fmtNum(c.apparent)}°` : ""}</span>
    </div>
    <div class="wx-loc">${esc(loc.name || "")} · Stand ${esc(w.fetched_at || "")}
      ${w.stale ? `<span class="badge badge-warn">veraltet</span>` : ""}</div>
    <div class="wx-stats">
      <div class="wx-stat"><div class="k">Höchst</div><div class="v v-max">${fmtNum(t.temp_max, 1)}°</div></div>
      <div class="wx-stat"><div class="k">Tiefst</div><div class="v v-min">${fmtNum(t.temp_min, 1)}°</div></div>
      <div class="wx-stat"><div class="k">Niederschlag</div><div class="v v-rain">${fmtNum(t.precip_sum, 1)}<small> mm</small></div>${prob}</div>
    </div>
    <div class="wx-note dim">Tagesvorhersage: ${esc(t.text)}</div>`;
}

async function loadWeather() {
  try { state.weather = await api("/api/weather"); }
  catch (e) { state.weather = { ok: false, message: e.message }; }
  renderWeather();
}

/* ---------------- Aktivitäten-Leiste ---------------- */
function renderRail() {
  const acts = [{ id: "alle", name: "Alle" }, ...state.meta.activities];
  if (!acts.some(a => a.id === state.activity)) state.activity = "alle";
  $("#activityRail").innerHTML = acts.map(a =>
    `<button class="act-btn ${a.id === state.activity ? "active" : ""}" data-act="${esc(a.id)}">${esc(a.name)}</button>`
  ).join("");
}

$("#activityRail").addEventListener("click", e => {
  const btn = e.target.closest(".act-btn");
  if (!btn) return;
  state.activity = btn.dataset.act;
  store("outfit.activity", state.activity);
  renderRail();
  loadOutfit();
});

/* ---------------- Outfit ---------------- */
function scoreBadge(label, v) {
  if (v === null || v === undefined) return "";
  const pct = Math.round(v * 100);
  const cls = pct >= 75 ? "badge-ok" : pct >= 50 ? "" : "badge-warn";
  return `<span class="badge ${cls}">${label} ${pct} %</span>`;
}

function renderOutfit(o) {
  $("#outfitScores").innerHTML =
    scoreBadge("Farbharmonie", o.harmony) + scoreBadge("Wetter", o.weather_score);
  const target = o.target;
  renderRuleInfo(o);
  $("#outfitStack").innerHTML = o.pieces.map(p => {
    if (!p.item) {
      return `<div class="piece empty"><div class="piece-body">
        <div class="piece-slot">${esc(p.slot_name)}</div>
        <div class="piece-msg">${esc(p.reason || "Nichts Passendes gefunden.")}</div>
      </div></div>`;
    }
    const it = p.item, col = colorById(it.color);
    const bars =
      levelBar("temp", it.temp_level_min, it.temp_level_max, L().t, target ? target.temp_level : null) +
      levelBar("rain", it.rain_level_min, it.rain_level_max, L().r, target ? target.rain_level : null);
    return `<article class="piece">
      <div class="piece-img"><img src="/bilder/${encodeURIComponent(it.image)}" alt="${esc(it.name)}" loading="lazy"></div>
      <div class="piece-body">
        <div class="piece-top">
          <div><div class="piece-slot">${esc(p.slot_name)}</div><div class="piece-name">${esc(it.name)}</div></div>
          <span class="w-meta"><span class="swatch-dot" style="background:${colorBg(col)}"></span>${esc(col ? col.name : "")}</span>
        </div>
        ${bars}
      </div>
    </article>`;
  }).join("");
}

function renderRuleInfo(o) {
  const el = $("#outfitRules");
  const ly = o.layers || {};
  if (!o.target) { el.innerHTML = ly.note ? esc(ly.note) : ""; return; }
  const r = ly.rules || {};
  const t = o.target;
  const jacke = ly.jacket
    ? (ly.jacket_reason === "regen" ? "Jacke wegen Niederschlag" : "Jacke")
    : "keine Jacke";
  el.innerHTML = `Heute <b>${fmtNum(t.temp, 1)} °C · ${esc(levelName(L().t, t.temp_level))}</b>,
    <b>${fmtNum(t.rain, 1)} mm · ${esc(levelName(L().r, t.rain_level))}</b> →
    ${ly.pullover ? "Pullover" : "kein Pullover"} (unter ${fmtNum(r.pullover_max_temp)} °C),
    ${jacke} (unter ${fmtNum(r.jacket_max_temp)} °C oder ab „${esc(levelName(L().r, r.jacket_rain_level))}“)`;
}

async function loadOutfit() {
  try {
    const o = await api(`/api/outfit?activity=${encodeURIComponent(state.activity)}&_=${Date.now()}`);
    renderOutfit(o);
  } catch (e) {
    $("#outfitStack").innerHTML = `<div class="dim center pad">Fehler: ${esc(e.message)}</div>`;
  }
}

$("#btnShuffle").addEventListener("click", loadOutfit);

/* ---------------- Kleiderschrank ---------------- */
function filterKey(it) { return it.subtype ? `${it.type}:${it.subtype}` : it.type; }

function filterOptions() {
  const opts = [];
  for (const t of state.meta.types) {
    const subs = (state.meta.subtypes || {})[t.id];
    if (subs) subs.forEach(x => opts.push({ id: `${t.id}:${x.id}`, name: x.name }));
    else opts.push(t);
  }
  return opts;
}

function renderTypeFilter() {
  const present = new Set(state.clothes.map(filterKey));
  const types = [{ id: "alle", name: "Alle" }, ...filterOptions().filter(t => present.has(t.id))];
  $("#typeFilter").innerHTML = types.map(t =>
    `<span class="chip ${t.id === state.typeFilter ? "on" : ""}" data-type="${esc(t.id)}">${esc(t.name)}</span>`
  ).join("");
}

$("#typeFilter").addEventListener("click", e => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  state.typeFilter = chip.dataset.type;
  renderTypeFilter();
  renderWardrobe();
});

function renderWardrobe() {
  const grid = $("#wardrobeGrid");
  const target = state.weather && state.weather.ok ? state.weather.target : null;
  const list = state.clothes.filter(c => state.typeFilter === "alle" || filterKey(c) === state.typeFilter);
  if (!state.clothes.length) {
    grid.innerHTML = `<div class="dim center pad" style="grid-column:1/-1">Noch keine Kleidungsstücke angelegt.<br>
      <a href="/einstellungen">→ In den Einstellungen anlegen</a></div>`;
    return;
  }
  const order = filterOptions().map(t => t.id);
  list.sort((a, b) => order.indexOf(filterKey(a)) - order.indexOf(filterKey(b)) || a.name.localeCompare(b.name, "de"));
  grid.innerHTML = list.map(it => {
    const col = colorById(it.color);
    const tags = (it.activities || []).length
      ? it.activities.map(a => `<span class="tag">${esc(actName(a))}</span>`).join("")
      : `<span class="tag tag-empty">keine Aktivität</span>`;
    return `<article class="w-card">
      <div class="w-img"><img src="/bilder/${encodeURIComponent(it.image)}" alt="${esc(it.name)}" loading="lazy"></div>
      <div class="w-body">
        <div class="w-name">${esc(it.name)}</div>
        <div class="w-meta"><span class="swatch-dot" style="background:${colorBg(col)}"></span>${esc(itemTypeName(it))} · ${esc(col ? col.name : "")}</div>
        ${levelBar("temp", it.temp_level_min, it.temp_level_max, L().t, target ? levelOf(target.temp, L().t) : null)}
        ${levelBar("rain", it.rain_level_min, it.rain_level_max, L().r, target ? levelOf(target.rain, L().r) : null)}
        <div class="w-tags">${tags}</div>
      </div>
    </article>`;
  }).join("") || `<div class="dim center pad" style="grid-column:1/-1">Keine Stücke dieses Typs.</div>`;
}

async function loadWardrobe() {
  try {
    state.clothes = await api("/api/clothes");
    renderTypeFilter();
    renderWardrobe();
  } catch (e) {
    $("#wardrobeGrid").innerHTML = `<div class="dim center pad">Fehler: ${esc(e.message)}</div>`;
  }
}

/* ---------------- Tabs ---------------- */
function showTab(name) {
  $$(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  $("#panel-outfit").classList.toggle("hidden", name !== "outfit");
  $("#panel-schrank").classList.toggle("hidden", name !== "schrank");
  if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
}
$$(".tab").forEach(t => t.addEventListener("click", () => showTab(t.dataset.tab)));

/* Safari stellt Seiten beim Zurück-Wischen aus dem Cache wieder her –
   dann trotzdem neu zusammenstellen. */
window.addEventListener("pageshow", e => {
  if (e.persisted && state.meta) { loadWeather(); loadOutfit(); loadWardrobe(); }
});

/* ---------------- Start ---------------- */
(async function init() {
  showTab(location.hash === "#schrank" ? "schrank" : "outfit");
  try {
    state.meta = await api("/api/meta");
  } catch (e) {
    toast("Server nicht erreichbar: " + e.message, true);
    return;
  }
  renderRail();
  // Wetter und Outfit parallel laden – das Outfit nutzt serverseitig dasselbe Wetter
  await Promise.all([loadWeather(), loadOutfit(), loadWardrobe()]);
  renderWardrobe(); // Tagesmarker in den Balken nachziehen
})();
