/* Outfit-Dashboard-MK1 – gemeinsame Hilfsfunktionen */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(url, opts = {}) {
  const res = await fetch(url, opts);
  let data = null;
  try { data = await res.json(); } catch (_) { /* keine JSON-Antwort */ }
  if (!res.ok) {
    const msg = (data && data.errors && data.errors.join(" ")) || `Fehler ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function postJSON(url, body) {
  return api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
}

let toastTimer = null;
function toast(msg, isError = false) {
  const el = $("#toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.toggle("err", !!isError);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch (_) { /* privater Modus o. ä. */ }
  return null;
}

function fmtNum(v, digits = 0) {
  if (v === null || v === undefined || isNaN(v)) return "–";
  return Number(v).toLocaleString("de-DE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/* Farbe als Hintergrund (Hex oder Verlauf für "Bunt") */
function colorBg(color) {
  return color ? color.hex : "#555";
}

/* Stufen-Hilfen ---------------------------------------------------------- */
function levelOf(value, levels) {
  if (value === null || value === undefined) return null;
  for (const lv of levels) if (value < lv.hi) return lv.level;
  return levels[levels.length - 1].level;
}

function levelName(levels, n) {
  const lv = levels.find(l => l.level === n);
  return lv ? lv.name : "–";
}

function levelRangeText(levels, a, b) {
  return a === b ? levelName(levels, a) : `${levelName(levels, a)} – ${levelName(levels, b)}`;
}

function levelTitle(kind, lv) {
  const u = kind === "temp" ? "°C" : "mm";
  if (lv.level === 1) return `${lv.name}: unter ${fmtNum(lv.hi, lv.hi % 1 ? 1 : 0)} ${u}`;
  if (lv.level === 6) return `${lv.name}: ab ${fmtNum(lv.lo, 0)} ${u}`;
  return `${lv.name}: ${fmtNum(lv.lo, lv.lo % 1 ? 1 : 0)}–${fmtNum(lv.hi, lv.hi % 1 ? 1 : 0)} ${u}`;
}

/**
 * Balkendiagramm mit 6 Stufen.
 * kind: "temp" | "rain", a/b: Stufenbereich (1–6), today: Stufe des Tages oder null
 * opts.labels: Stufennamen unter den Segmenten anzeigen
 * opts.select: Segmente anklickbar (data-level), opts.from: ab dieser Stufe markieren
 */
function levelBar(kind, a, b, levels, today = null, opts = {}) {
  const title = opts.title || (kind === "temp" ? "Temperatur" : "Niederschlag");
  const right = opts.rightText !== undefined ? opts.rightText : levelRangeText(levels, a, b);
  const segs = levels.map(lv => {
    const on = lv.level >= a && lv.level <= b;
    const cls = ["seg", on ? "on" : "", lv.level === today ? "today" : ""].join(" ");
    const tag = opts.select ? "button type=\"button\"" : "span";
    const end = opts.select ? "button" : "span";
    return `<${tag} class="${cls}" data-level="${lv.level}" title="${esc(levelTitle(kind, lv))}"
      style="--seg:${lv.color}">${lv.level === today ? "<i></i>" : ""}</${end}>`;
  }).join("");
  const labels = opts.labels
    ? `<div class="seg-labels">${levels.map(lv => `<span>${esc(lv.name)}</span>`).join("")}</div>` : "";
  return `
    <div class="bar lbar lbar-${kind}${opts.select ? " lbar-select" : ""}">
      <div class="bar-label"><span>${esc(title)}</span><b>${esc(right)}</b></div>
      <div class="segs">${segs}</div>
      ${labels}
    </div>`;
}

/* einfache Wetter-Icons als SVG */
function weatherIcon(kind) {
  const s = 'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"';
  const cloud = `<path ${s} d="M7 18h10a4 4 0 0 0 .5-7.97A5.5 5.5 0 0 0 7 9.5 4.25 4.25 0 0 0 7 18z"/>`;
  const icons = {
    sun: `<circle ${s} cx="12" cy="12" r="4.2"/><path ${s} d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"/>`,
    partly: `<circle ${s} cx="8.5" cy="8" r="3"/><path ${s} d="M8.5 2.5v1.3M3 8h1.3M4.6 4.1l.9.9M12.4 4.1l-.9.9"/><path ${s} d="M9 19h8.5a3.5 3.5 0 0 0 .4-7A4.8 4.8 0 0 0 9 11.5a3.75 3.75 0 0 0 0 7.5z"/>`,
    cloud: cloud,
    fog: `<path ${s} d="M4 9h16M3 13h18M5 17h14"/>`,
    rain: `<path ${s} d="M7 15h10a4 4 0 0 0 .5-7.97A5.5 5.5 0 0 0 7 6.5 4.25 4.25 0 0 0 7 15z"/><path ${s} d="M9 18l-1 2.5M13 18l-1 2.5M17 18l-1 2.5"/>`,
    snow: `<path ${s} d="M7 14h10a4 4 0 0 0 .5-7.97A5.5 5.5 0 0 0 7 5.5 4.25 4.25 0 0 0 7 14z"/><path ${s} d="M8 18h.01M12 19h.01M16 18h.01M10 21h.01M14 21h.01"/>`,
    storm: `<path ${s} d="M7 14h10a4 4 0 0 0 .5-7.97A5.5 5.5 0 0 0 7 5.5 4.25 4.25 0 0 0 7 14z"/><path ${s} d="M12.5 15l-2 3.5h3l-2 3.5"/>`,
  };
  return `<svg viewBox="0 0 24 24" class="wx-icon" aria-hidden="true">${icons[kind] || cloud}</svg>`;
}
