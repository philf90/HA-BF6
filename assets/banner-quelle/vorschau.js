// Vorschaubild: sieben der acht Karten in drei Spalten.
// Links Klassen und Spielwelt, in der Mitte Spieler und Squad, rechts Karten
// und Verlauf. Breite je Karte 344 px wie auf dem Handy (DESIGN.md).
import { ladeIcons, karte } from "./platzhalter.js";
import { hass } from "./daten.js";

await ladeIcons();
const rahmen = document.createElement("div");
rahmen.className = "rahmen";
document.body.appendChild(rahmen);

function spalte(links, oben) {
  const s = document.createElement("div");
  s.className = "spalte";
  Object.assign(s.style, { left: `${links}px`, top: `${oben}px` });
  rahmen.appendChild(s);
  return s;
}

const E = "sensor.nachtfalke_kills";
const links = spalte(70, 92);
const mitte = spalte(448, 40);
const rechts = spalte(826, 70);
await karte(links, "bf6-classes-card", { entity: E }, hass);
await karte(links, "bf6-world-card", {}, hass);
await karte(mitte, "bf6-player-card", { entity: E }, hass);
await karte(mitte, "bf6-squad-card", {}, hass);
await karte(rechts, "bf6-maps-card", { entity: E, limit: 5 }, hass);
await karte(rechts, "bf6-history-card", { entity: E, metric: "kd" }, hass);

const fuss = document.createElement("div");
fuss.className = "fuss";
fuss.textContent = "Beispieldaten · Nachtblau-Karten";
rahmen.appendChild(fuss);

await document.fonts.ready;
await new Promise((r) => setTimeout(r, 500));
window.fertig = true;
