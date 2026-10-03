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

/**
 * Balkendiagramm für einen Wertebereich.
 * kind: "temp" | "rain", scale: [min, max], marker: Tageswert oder null
 */
function rangeBar(kind, lo, hi, scale, marker = null) {
  const [smin, smax] = scale;
  const span = smax - smin;
  const pct = v => Math.max(0, Math.min(100, ((v - smin) / span) * 100));
  const left = pct(lo);
  const width = Math.max(pct(hi) - left, 1.5);
  const unit = kind === "temp" ? "°C" : "mm";
  const title = kind === "temp" ? "Temperatur" : "Niederschlag";
  const digits = kind === "rain" && (lo % 1 || hi % 1) ? 1 : 0;
  let fillStyle = `left:${left}%;width:${width}%;`;
  if (kind === "temp") {
    // Verlauf bezieht sich auf die ganze Skala → Farbe entspricht absoluter Temperatur
    const w = width / 100, l = left / 100;
    const pos = w >= 1 ? 0 : (l / (1 - w)) * 100;
    fillStyle += `background-size:${(100 / width) * 100}% 100%;background-position:${pos}% 0;`;
  }
  const zero = kind === "temp" && smin < 0 && smax > 0
    ? `<span class="bar-zero" style="left:${pct(0)}%"></span>` : "";
  const mark = marker !== null && marker !== undefined
    ? `<span class="bar-marker" style="left:${pct(marker)}%" title="Heute: ${fmtNum(marker, 1)} ${unit}"></span>` : "";
  const mid = kind === "temp" ? `<span>0</span>` : `<span>${(smin + smax) / 2}</span>`;
  return `
    <div class="bar bar-${kind}">
      <div class="bar-label"><span>${title}</span><b>${fmtNum(lo, digits)} – ${fmtNum(hi, digits)} ${unit}</b></div>
      <div class="bar-track">${zero}<span class="bar-fill" style="${fillStyle}"></span>${mark}</div>
      <div class="bar-scale"><span>${smin}</span>${mid}<span>${smax} ${unit}</span></div>
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
