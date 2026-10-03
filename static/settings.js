/* Outfit-Dashboard-MK1 – Einstellungen */
"use strict";

const S = {
  meta: null,
  activities: [],
  clothes: [],
  editId: null,
  color: null,
  selActs: new Set(),
  photoBlob: null,
  subtype: null,
  rules: null,
};

const colorById = id => (S.meta.colors.find(c => c.id === id) || null);
const typeName = id => ((S.meta.types.find(t => t.id === id) || {}).name || id);
const subsOf = type => (S.meta.subtypes || {})[type] || [];
const itemTypeName = it => {
  const sub = subsOf(it.type).find(x => x.id === it.subtype);
  return sub ? `${typeName(it.type)} · ${sub.name}` : typeName(it.type);
};
const TL = () => S.meta.temp_levels;
const RL = () => S.meta.rain_levels;

/* ================= Regeln für Oberteile ================= */
let rulesTimer = null;
function renderRules() {
  const r = S.rules;
  $("#rulePullover").value = r.pullover_max_temp;
  $("#ruleJacket").value = r.jacket_max_temp;
  $("#pulloverVal").textContent = `${fmtNum(r.pullover_max_temp)} °C`;
  $("#jacketVal").textContent = `${fmtNum(r.jacket_max_temp)} °C`;
  $("#ruleRainBar").innerHTML = levelBar("rain", r.jacket_rain_level, 6, RL(), null, {
    labels: true, select: true, title: "Niederschlag",
    rightText: `ab „${levelName(RL(), r.jacket_rain_level)}“`,
  });
}

function saveRules(msg) {
  clearTimeout(rulesTimer);
  rulesTimer = setTimeout(async () => {
    try {
      const res = await postJSON("/api/settings/rules", S.rules);
      S.rules = res.rules;
      renderRules();
      if (msg) toast(msg);
    } catch (e) { toast(e.message, true); }
  }, 350);
}

for (const [id, key] of [["rulePullover", "pullover_max_temp"], ["ruleJacket", "jacket_max_temp"]]) {
  $("#" + id).addEventListener("input", e => {
    S.rules[key] = +e.target.value;
    $(key === "pullover_max_temp" ? "#pulloverVal" : "#jacketVal").textContent = `${e.target.value} °C`;
  });
  $("#" + id).addEventListener("change", () => saveRules("Regel gespeichert"));
}
$("#ruleRainBar").addEventListener("click", e => {
  const seg = e.target.closest("[data-level]");
  if (!seg) return;
  S.rules.jacket_rain_level = +seg.dataset.level;
  renderRules();
  saveRules("Regel gespeichert");
});

/* ================= Standort ================= */
function renderLocation() {
  const loc = S.meta.location || {};
  const badge = $("#locBadge");
  if (loc.lat != null) {
    badge.textContent = loc.name || `${loc.lat}, ${loc.lon}`;
    badge.className = "badge badge-ok";
  } else {
    badge.textContent = "nicht festgelegt";
    badge.className = "badge badge-warn";
  }
}

async function saveLocation(name, lat, lon) {
  try {
    const r = await postJSON("/api/settings/location", { name, lat, lon });
    S.meta.location = r.location;
    renderLocation();
    $("#locResults").innerHTML = "";
    toast("Standort gespeichert: " + r.location.name);
  } catch (e) { toast(e.message, true); }
}

async function searchLocation() {
  const q = $("#locQuery").value.trim();
  if (q.length < 2) return toast("Bitte mindestens 2 Zeichen eingeben.", true);
  const list = $("#locResults");
  list.innerHTML = `<li class="dim">Suche …</li>`;
  try {
    const r = await api("/api/geocode?q=" + encodeURIComponent(q));
    if (!r.results.length) { list.innerHTML = `<li class="dim">Kein Ort gefunden.</li>`; return; }
    list.innerHTML = r.results.map((x, i) =>
      `<li data-i="${i}">${esc(x.label)} <span class="dim small">(${fmtNum(x.lat, 2)}, ${fmtNum(x.lon, 2)})</span></li>`).join("");
    list.onclick = e => {
      const li = e.target.closest("li[data-i]");
      if (!li) return;
      const x = r.results[+li.dataset.i];
      saveLocation(x.label, x.lat, x.lon);
    };
  } catch (e) { list.innerHTML = `<li class="dim">${esc(e.message)}</li>`; }
}

$("#btnLocSearch").addEventListener("click", searchLocation);
$("#locQuery").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); searchLocation(); } });
$("#btnLocManual").addEventListener("click", () => {
  const lat = parseFloat($("#locLat").value.replace(",", "."));
  const lon = parseFloat($("#locLon").value.replace(",", "."));
  if (isNaN(lat) || isNaN(lon)) return toast("Bitte gültige Koordinaten eingeben.", true);
  saveLocation($("#locName").value.trim(), lat, lon);
});

/* ================= Aktivitäten ================= */
function renderActivities() {
  $("#activityList").innerHTML = S.activities.map((a, i) => `
    <li>
      <input type="text" value="${esc(a.name)}" data-i="${i}" maxlength="40" aria-label="Aktivität umbenennen">
      <button class="btn btn-danger btn-sm" data-del="${i}" aria-label="Löschen">✕</button>
    </li>`).join("") || `<li class="dim small">Noch keine Aktivitäten.</li>`;
  renderActivityChips();
}

async function saveActivities(msg) {
  try {
    const r = await postJSON("/api/settings/activities", { activities: S.activities });
    S.activities = r.activities;
    S.meta.activities = r.activities;
    renderActivities();
    await loadClothes();
    if (msg) toast(msg);
  } catch (e) { toast(e.message, true); }
}

$("#activityList").addEventListener("change", e => {
  const inp = e.target.closest("input[data-i]");
  if (!inp) return;
  const name = inp.value.trim();
  if (!name) { inp.value = S.activities[+inp.dataset.i].name; return; }
  S.activities[+inp.dataset.i].name = name;
  saveActivities("Aktivität umbenannt");
});

$("#activityList").addEventListener("click", e => {
  const btn = e.target.closest("[data-del]");
  if (!btn) return;
  const a = S.activities[+btn.dataset.del];
  if (!confirm(`Aktivität „${a.name}“ löschen? Das Label wird auch von allen Kleidungsstücken entfernt.`)) return;
  S.activities.splice(+btn.dataset.del, 1);
  S.selActs.delete(a.id);
  saveActivities("Aktivität gelöscht");
});

function addActivity() {
  const inp = $("#newActivity");
  const name = inp.value.trim();
  if (!name) return;
  if (S.activities.some(a => a.name.toLowerCase() === name.toLowerCase())) return toast("Gibt es schon.", true);
  S.activities.push({ name });
  inp.value = "";
  saveActivities("Aktivität hinzugefügt");
}
$("#btnAddActivity").addEventListener("click", addActivity);
$("#newActivity").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); addActivity(); } });

/* ================= Formular Kleidungsstück ================= */
function renderActivityChips() {
  $("#activityChips").innerHTML = S.activities.map(a =>
    `<span class="chip ${S.selActs.has(a.id) ? "on" : ""}" data-act="${esc(a.id)}">${esc(a.name)}</span>`
  ).join("") || `<span class="dim small">Zuerst oben Aktivitäten anlegen.</span>`;
}
$("#activityChips").addEventListener("click", e => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  const id = chip.dataset.act;
  S.selActs.has(id) ? S.selActs.delete(id) : S.selActs.add(id);
  chip.classList.toggle("on");
});

function renderSwatches() {
  $("#colorSwatches").innerHTML = S.meta.colors.map(c =>
    `<button type="button" class="swatch ${c.id === S.color ? "on" : ""}" data-color="${c.id}"
      style="background:${colorBg(c)}" title="${esc(c.name)}" aria-label="${esc(c.name)}"></button>`).join("");
  const c = colorById(S.color);
  $("#colorName").textContent = c ? "· " + c.name : "";
}
$("#colorSwatches").addEventListener("click", e => {
  const sw = e.target.closest(".swatch");
  if (!sw) return;
  S.color = sw.dataset.color;
  renderSwatches();
});

function setupSliders() {
  const link = (a, b, isMin) => $("#" + a).addEventListener("input", () => {
    const A = $("#" + a), B = $("#" + b);
    if (isMin && +A.value > +B.value) B.value = A.value;
    if (!isMin && +A.value < +B.value) B.value = A.value;
    updatePreviews();
  });
  link("tempMin", "tempMax", true); link("tempMax", "tempMin", false);
  link("rainMin", "rainMax", true); link("rainMax", "rainMin", false);
  $("#levelHint").textContent = RL().map(lv => levelTitle("rain", lv)).join(" · ");
}

function updatePreviews() {
  $("#tempPreview").innerHTML = levelBar("temp", +$("#tempMin").value, +$("#tempMax").value, TL(), null, { labels: true });
  $("#rainPreview").innerHTML = levelBar("rain", +$("#rainMin").value, +$("#rainMax").value, RL(), null, { labels: true });
}

/* ================= Untertyp (Oberteil) ================= */
function renderSubtypes() {
  const subs = subsOf($("#itemType").value);
  $("#subtypeField").classList.toggle("hidden", !subs.length);
  if (subs.length && !subs.some(x => x.id === S.subtype)) S.subtype = subs[0].id;
  if (!subs.length) S.subtype = null;
  $("#subtypeChips").innerHTML = subs.map(x =>
    `<span class="chip ${x.id === S.subtype ? "on" : ""}" data-sub="${x.id}">${esc(x.name)}</span>`).join("");
}
$("#itemType").addEventListener("change", renderSubtypes);
$("#subtypeChips").addEventListener("click", e => {
  const chip = e.target.closest("[data-sub]");
  if (!chip) return;
  S.subtype = chip.dataset.sub;
  renderSubtypes();
});

/* Bild im Browser verkleinern → spart Speicher auf dem Router */
function resizeImage(file, maxSide = 900, quality = 0.82) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight));
      const w = Math.round(img.naturalWidth * scale), h = Math.round(img.naturalHeight * scale);
      const canvas = document.createElement("canvas");
      canvas.width = w; canvas.height = h;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, w, h); // Transparenz → weiß
      ctx.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      canvas.toBlob(b => resolve(b || file), "image/jpeg", quality);
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
    img.src = url;
  });
}

$("#photoInput").addEventListener("change", async e => {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  S.photoBlob = await resizeImage(file);
  const prev = $("#photoPreview");
  prev.src = URL.createObjectURL(S.photoBlob);
  prev.classList.remove("hidden");
  $("#photoHint").classList.add("hidden");
});

function resetForm() {
  S.editId = null;
  S.color = null;
  S.selActs = new Set();
  S.photoBlob = null;
  S.subtype = null;
  $("#itemForm").reset();
  $("#itemId").value = "";
  $("#tempMin").value = 3; $("#tempMax").value = 5;
  $("#rainMin").value = 1; $("#rainMax").value = 3;
  $("#photoPreview").classList.add("hidden");
  $("#photoPreview").removeAttribute("src");
  $("#photoHint").classList.remove("hidden");
  $("#itemFormTitle").textContent = "Kleidungsstück anlegen";
  $("#btnCancelEdit").classList.add("hidden");
  $("#btnSave").textContent = "Speichern";
  $("#formErrors").textContent = "";
  renderSwatches();
  renderActivityChips();
  renderSubtypes();
  updatePreviews();
}
$("#btnCancelEdit").addEventListener("click", resetForm);

function editItem(id) {
  const it = S.clothes.find(c => c.id === id);
  if (!it) return;
  resetForm();
  S.editId = id;
  S.color = it.color;
  S.selActs = new Set(it.activities || []);
  $("#itemId").value = id;
  $("#itemName").value = it.name;
  $("#itemType").value = it.type;
  S.subtype = it.subtype || null;
  renderSubtypes();
  $("#tempMin").value = it.temp_level_min; $("#tempMax").value = it.temp_level_max;
  $("#rainMin").value = it.rain_level_min; $("#rainMax").value = it.rain_level_max;
  $("#photoPreview").src = "/bilder/" + encodeURIComponent(it.image);
  $("#photoPreview").classList.remove("hidden");
  $("#photoHint").classList.add("hidden");
  $("#itemFormTitle").textContent = "Kleidungsstück bearbeiten";
  $("#btnCancelEdit").classList.remove("hidden");
  $("#btnSave").textContent = "Änderungen speichern";
  renderSwatches();
  renderActivityChips();
  updatePreviews();
  $("#itemCard").scrollIntoView({ behavior: "smooth", block: "start" });
}

$("#itemForm").addEventListener("submit", async e => {
  e.preventDefault();
  const errs = [];
  if (!$("#itemName").value.trim()) errs.push("Bitte einen Namen angeben.");
  if (!S.color) errs.push("Bitte eine Farbe wählen.");
  if (!S.editId && !S.photoBlob) errs.push("Bitte ein Foto auswählen.");
  if (errs.length) { $("#formErrors").textContent = errs.join(" "); return; }

  const fd = new FormData();
  fd.append("name", $("#itemName").value.trim());
  fd.append("type", $("#itemType").value);
  if (S.subtype) fd.append("subtype", S.subtype);
  fd.append("color", S.color);
  S.selActs.forEach(a => fd.append("activities", a));
  for (const k of ["temp_level_min", "temp_level_max", "rain_level_min", "rain_level_max"]) fd.append(k, $(`[name=${k}]`).value);
  if (S.photoBlob) fd.append("image", S.photoBlob, "foto.jpg");

  const btn = $("#btnSave");
  btn.disabled = true;
  try {
    const url = S.editId ? `/api/clothes/${S.editId}` : "/api/clothes";
    await api(url, { method: "POST", body: fd });
    toast(S.editId ? "Änderungen gespeichert" : "Kleidungsstück angelegt");
    resetForm();
    await loadClothes();
  } catch (err) {
    $("#formErrors").textContent = err.message;
  } finally {
    btn.disabled = false;
  }
});

/* ================= Liste ================= */
function renderItemList() {
  $("#itemCount").textContent = S.clothes.length;
  const order = S.meta.types.map(t => t.id);
  const subOrder = it => subsOf(it.type).findIndex(x => x.id === it.subtype);
  const list = [...S.clothes].sort((a, b) =>
    order.indexOf(a.type) - order.indexOf(b.type) || subOrder(a) - subOrder(b) || a.name.localeCompare(b.name, "de"));
  $("#itemList").innerHTML = list.map(it => {
    const col = colorById(it.color);
    const acts = (it.activities || []).map(a => {
      const x = S.activities.find(y => y.id === a);
      return x ? `<span class="tag">${esc(x.name)}</span>` : "";
    }).join(" ");
    return `<div class="item-row">
      <img src="/bilder/${encodeURIComponent(it.image)}" alt="" loading="lazy">
      <div style="min-width:0">
        <div class="title">${esc(it.name)}</div>
        <div class="sub"><span class="swatch-dot" style="background:${colorBg(col)}"></span>${esc(itemTypeName(it))} ${acts}</div>
        ${levelBar("temp", it.temp_level_min, it.temp_level_max, TL())}
        ${levelBar("rain", it.rain_level_min, it.rain_level_max, RL())}
      </div>
      <div class="actions">
        <button class="btn btn-sm" data-edit="${it.id}">Bearbeiten</button>
        <button class="btn btn-sm btn-danger" data-delete="${it.id}">Löschen</button>
      </div>
    </div>`;
  }).join("") || `<div class="dim small">Noch keine Kleidungsstücke angelegt.</div>`;
}

$("#itemList").addEventListener("click", async e => {
  const ed = e.target.closest("[data-edit]");
  if (ed) return editItem(ed.dataset.edit);
  const del = e.target.closest("[data-delete]");
  if (!del) return;
  const it = S.clothes.find(c => c.id === del.dataset.delete);
  if (!it || !confirm(`„${it.name}“ wirklich löschen?`)) return;
  try {
    await api(`/api/clothes/${it.id}`, { method: "DELETE" });
    if (S.editId === it.id) resetForm();
    toast("Gelöscht");
    await loadClothes();
  } catch (err) { toast(err.message, true); }
});

async function loadClothes() {
  S.clothes = await api("/api/clothes");
  renderItemList();
  if (S.meta && $("#storageInfo")) loadStorage();
}

/* ================= Datenspeicher & Sicherung ================= */
function fmtBytes(b) {
  if (b == null) return "–";
  const u = ["B", "KB", "MB", "GB"]; let i = 0;
  while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; }
  return `${fmtNum(b, i ? 1 : 0)} ${u[i]}`;
}

async function loadStorage() {
  try {
    const s = await api("/api/storage");
    $("#storageInfo").innerHTML = `
      <dt>Datenordner</dt><dd><code>${esc(s.home_dir)}</code></dd>
      <dt>Programm</dt><dd><code>${esc(s.program_dir)}</code></dd>
      <dt>Inhalt</dt><dd>${s.items} Kleidungsstücke · ${s.activities} Aktivitäten · ${fmtBytes(s.data_bytes)}</dd>
      <dt>Frei</dt><dd>${fmtBytes(s.free_bytes)}</dd>
      ${s.warning ? `<dt class="warn-dt">Hinweis</dt><dd class="warn-dd">${esc(s.warning)}</dd>` : ""}`;
  } catch (e) { $("#storageInfo").innerHTML = `<dt>Fehler</dt><dd>${esc(e.message)}</dd>`; }
}

$("#restoreInput").addEventListener("change", async e => {
  const file = e.target.files && e.target.files[0];
  e.target.value = "";
  if (!file) return;
  if (!confirm(`Sicherung „${file.name}“ einspielen? Der aktuelle Stand wird dabei ersetzt (vorher automatisch gesichert).`)) return;
  const fd = new FormData();
  fd.append("backup", file);
  toast("Sicherung wird eingespielt …");
  try {
    const r = await api("/api/backup", { method: "POST", body: fd });
    toast(`Wiederhergestellt: ${r.items} Stücke, ${r.images} Fotos`);
    setTimeout(() => location.reload(), 1200);
  } catch (err) { toast(err.message, true); }
});

$("#btnShutdown").addEventListener("click", async () => {
  if (!confirm("Outfit-Dashboard wirklich beenden?")) return;
  try {
    await api("/api/shutdown", { method: "POST" });
    document.body.innerHTML = `<main class="container"><section class="card" style="margin-top:40px">
      <h3>Outfit-Dashboard wurde beendet.</h3>
      <p class="hint">Dieses Fenster kann geschlossen werden.</p></section></main>`;
  } catch (e) { toast(e.message, true); }
});

/* ================= Start ================= */
(async function init() {
  try {
    S.meta = await api("/api/meta");
  } catch (e) { toast("Server nicht erreichbar: " + e.message, true); return; }
  S.activities = S.meta.activities.map(a => ({ ...a }));
  $("#itemType").innerHTML = S.meta.types.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join("");
  S.rules = { ...S.meta.rules };
  renderRules();
  $("#shutdownBox").classList.toggle("hidden", !S.meta.can_shutdown);
  renderLocation();
  renderActivities();
  setupSliders();
  resetForm();
  await loadClothes();
})();
