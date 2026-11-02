// Banner (index.html?f=banner) und Social Preview (index.html?f=social):
// Erkennungsmarke mit Fadenkreuz, Titel, Stichworte und drei aufgefaecherte
// Karten der Integration (Klassen, Spieler, Karten), wie der Banner von
// WoW Charakter. Kein Battlefield-Logo und keine Spielgrafik.
const F = new URLSearchParams(location.search).get("f") || "banner";
const S = F === "social";
document.body.className = F;

import { ladeIcons, karte as setzeKarte } from "./platzhalter.js";
import { hass } from "./daten.js";

await ladeIcons();

const rahmen = document.createElement("div");
rahmen.className = "rahmen";
document.body.appendChild(rahmen);

function el(html, style) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  const n = t.content.firstElementChild;
  if (style) Object.assign(n.style, style);
  rahmen.appendChild(n);
  return n;
}

// Erkennungsmarke mit Fadenkreuz (eigenes Motiv)
function emblem(x, y, h) {
  el(`<svg class="emblem" viewBox="0 0 74 100" width="${h * 0.74}" height="${h}" aria-hidden="true">
      <defs>
        <linearGradient id="marke" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#3a2a36"/><stop offset="1" stop-color="#241b25"/>
        </linearGradient>
      </defs>
      <circle cx="37" cy="4" r="2.2" fill="none" stroke="#8794a5" stroke-width="1.4"/>
      <path d="M37 6 L37 13" stroke="#8794a5" stroke-width="1.4" stroke-dasharray="1.6 1.6"/>
      <rect x="6" y="13" width="62" height="84" rx="17" fill="url(#marke)" stroke="#e6a0c4" stroke-width="2.4"/>
      <circle cx="37" cy="23" r="3.6" fill="#10151d" stroke="#e6a0c4" stroke-width="1.6"/>
      <g transform="translate(17 38) scale(1.68)" fill="#e6a0c4"><path d="${window.MDI.mdiCrosshairsGps}"/></g>
    </svg>`, { left: x + "px", top: y + "px" });
}

function titelblock(x, y, g) {
  el(`<div class="text">
      <div class="titel" style="font-size:${g.titel}px"><b>BF6</b> Spieler</div>
      <div class="unter" style="font-size:${g.unter}px;margin-top:${g.abstand1}px">Battlefield&nbsp;6 für Home Assistant</div>
      <div class="tags" style="font-size:${g.tags}px;letter-spacing:${g.tags * 0.19}px;margin-top:${g.abstand2}px">gametools API<i>·</i>HACS<i>·</i>8 Nachtblau-Karten</div>
    </div>`, { left: x + "px", top: y + "px" });
}

const karte = (typ, cfg, stil) => setzeKarte(rahmen, typ, cfg, hass, stil);

const E = "sensor.nachtfalke_kills";
if (!S) {
  emblem(64, 46, 164);
  titelblock(222, 58, { titel: 78, unter: 26, tags: 14, abstand1: 14, abstand2: 18 });
  await karte("bf6-classes-card", { entity: E }, { left: "706px", top: "44px", transform: "scale(0.58) rotate(-8deg)" });
  await karte("bf6-maps-card", { entity: E, limit: 4 }, { left: "1002px", top: "40px", transform: "scale(0.58) rotate(8deg)" });
  await karte("bf6-player-card", { entity: E }, { left: "846px", top: "20px", transform: "scale(0.64)", zIndex: 4 });
} else {
  emblem(96, 64, 140);
  titelblock(96, 236, { titel: 104, unter: 34, tags: 17, abstand1: 18, abstand2: 24 });
  await karte("bf6-classes-card", { entity: E }, { left: "720px", top: "150px", transform: "scale(0.78) rotate(-8deg)" });
  await karte("bf6-maps-card", { entity: E, limit: 4 }, { left: "1000px", top: "140px", transform: "scale(0.78) rotate(8deg)" });
  await karte("bf6-player-card", { entity: E }, { left: "850px", top: "70px", transform: "scale(0.9)", zIndex: 4 });
}

await document.fonts.ready;
await new Promise((r) => setTimeout(r, 500));
window.fertig = true;
