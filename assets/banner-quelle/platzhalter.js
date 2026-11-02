// Platzhalter fuer ha-card und ha-icon, die Home Assistant sonst liefert.
// ha-icon und ha-svg-icon sind wie in home-assistant/frontend aufgebaut, damit
// Groesse und Ausrichtung der Symbole den echten Karten entsprechen:
//   ha-icon:     Shadow DOM, :host { fill: currentcolor } (sonst Inline),
//                rendert <ha-svg-icon>
//   ha-svg-icon: :host { display: var(--ha-icon-display, inline-flex);
//                align-items/justify-content: center; vertical-align: middle;
//                width/height: var(--mdc-icon-size, 24px) }
// Die Pfade stammen aus Material Design Icons 7.4.47 (wie Home Assistant).
window.MDI = {};

customElements.define("ha-card", class extends HTMLElement {});

customElements.define("ha-svg-icon", class extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }
  set path(pfad) {
    this.shadowRoot.innerHTML = `<style>
        :host { display: var(--ha-icon-display, inline-flex); align-items: center; justify-content: center;
          position: relative; vertical-align: middle; fill: var(--icon-primary-color, currentcolor);
          width: var(--mdc-icon-size, 24px); height: var(--mdc-icon-size, 24px); }
        svg { width: 100%; height: 100%; pointer-events: none; display: block; }
      </style><svg viewBox="0 0 24 24" preserveAspectRatio="xMidYMid meet" focusable="false" aria-hidden="true"><g><path d="${pfad}"></path></g></svg>`;
  }
});

customElements.define("ha-icon", class extends HTMLElement {
  static get observedAttributes() {
    return ["icon"];
  }
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
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
    this.shadowRoot.innerHTML = "<style>:host { fill: currentcolor; }</style>";
    const svg = document.createElement("ha-svg-icon");
    svg.path = window.MDI[key] || "";
    this.shadowRoot.appendChild(svg);
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
