// Platzhalter fuer ha-card und ha-icon, die Home Assistant sonst liefert.
// ha-icon zeichnet den Pfad aus Material Design Icons 7.4.47 (wie Home
// Assistant); die Groesse kommt wie dort aus --mdc-icon-size und steht direkt
// am Element, weil das Seiten-CSS nicht in den Shadow DOM der Karten wirkt.
window.MDI = {};

customElements.define("ha-card", class extends HTMLElement {});
customElements.define("ha-icon", class extends HTMLElement {
  static get observedAttributes() {
    return ["icon"];
  }
  connectedCallback() {
    this.zeichnen();
  }
  attributeChangedCallback() {
    this.zeichnen();
  }
  zeichnen() {
    const name = (this.getAttribute("icon") || "").replace("mdi:", "");
    const key = "mdi" + name.split("-").map((t) => t[0].toUpperCase() + t.slice(1)).join("");
    this.style.display = "inline-block";
    this.style.width = this.style.height = "var(--mdc-icon-size, 24px)";
    this.style.verticalAlign = "middle";
    this.innerHTML = `<svg viewBox="0 0 24 24" style="display:block;width:100%;height:100%;fill:currentColor"><path d="${window.MDI[key] || ""}"/></svg>`;
  }
});

// Alle Icon-Pfade laden; vor dem ersten Zeichnen einer Karte aufrufen
export async function ladeIcons() {
  const text = await (await fetch("https://cdn.jsdelivr.net/npm/@mdi/js@7.4.47/mdi.js")).text();
  for (const [, name, pfad] of text.matchAll(/export var (mdi\w+) = "([^"]+)"/g)) {
    window.MDI[name] = pfad;
  }
}

// Karte der Integration in einen Rahmen setzen (Pfad relativ zu dieser Datei)
export async function karte(ziel, typ, config, hass, stil) {
  await import(`../../custom_components/bf6_player/frontend/${typ}.js?v=bilder`);
  const k = document.createElement(typ);
  k.setConfig({ type: `custom:${typ}`, ...config });
  k.hass = hass;
  const h = document.createElement("div");
  h.className = "karte";
  Object.assign(h.style, stil || {});
  h.appendChild(k);
  ziel.appendChild(h);
  return h;
}
