// Fuehrt die Dashboard-Karten in Node aus (seit 0.6.10) und gibt JSON aus.
//
// Aufruf: node karten_lauf.mjs  (im selben Verzeichnis wie die Karten; der
// Test kopiert beides mit einem package.json {"type": "module"} in ein
// temporaeres Verzeichnis). Ausgewertet in tests/test_karten_verhalten.py.
//
// Nachgebaut ist nur, was die Karten vom Browser brauchen: HTMLElement mit
// attachShadow, customElements und window.customCards. Die Karten schreiben
// ihr HTML als Text in shadowRoot.innerHTML; das reicht, um es zu pruefen.

const gezeigt = new Map();
globalThis.HTMLElement = class {
  attachShadow() {
    this.shadowRoot = { innerHTML: "" };
    return this.shadowRoot;
  }
};
globalThis.customElements = {
  get: (name) => gezeigt.get(name),
  define: (name, klasse) => gezeigt.set(name, klasse),
};
globalThis.window = globalThis;

const basis = new URL("./", import.meta.url);
const C = await import(new URL("bf6-common.js", basis));

// Wert, der aus jedem Textfeld ausbrechen wuerde, wenn er ungeprueft in HTML
// landete
export const BOESE = '"><img src=x onerror=alert(1)>';

const SPIELER_KEYS = [
  "kills", "deaths", "assists", "revives", "matches", "wins", "losses", "xp",
  "time_played", "kd", "kpm", "win_rate", "accuracy", "headshot_rate",
  "human_kill_rate", "rank", "favorite_class", "top_weapon", "top_vehicle",
  "platform", "match_finished", "rank_up", "rank_badge",
];
const WELT_KEYS = ["season_end", "portal_servers", "portal_players"];

function entities() {
  const ergebnis = {};
  for (const key of SPIELER_KEYS) {
    const id = `sensor.spieler_${key}`;
    ergebnis[id] = { entity_id: id, platform: "bf6_player", device_id: "geraet-spieler", translation_key: key };
  }
  for (const key of WELT_KEYS) {
    const id = `sensor.welt_${key}`;
    ergebnis[id] = { entity_id: id, platform: "bf6_player", device_id: "geraet-welt", translation_key: key };
  }
  // Fremde Entitaeten wie in einer echten Instanz
  for (let i = 0; i < 50; i++) {
    ergebnis[`sensor.fremd_${i}`] = { entity_id: `sensor.fremd_${i}`, platform: "andere", device_id: `fremd-${i % 5}` };
  }
  return ergebnis;
}

// text: Wert fuer jedes Textfeld; zahl: Wert fuer die Spielzeit je Klasse
function hassMit(text, klassenSekunden) {
  const st = (key, state, attributes = {}) => [`sensor.spieler_${key}`, { state: String(state), attributes }];
  const liste = (felder) => [{ name: text, type: text, kills: 120, accuracy: 25.5, headshot_rate: 12.5, kpm: 1.2, seconds: 3600, image: null, ...felder }];
  const states = Object.fromEntries([
    st("kills", 1000), st("deaths", 400), st("assists", 300), st("revives", 120),
    st("matches", 50, {
      maps: [{ name: text, aliases: [text], matches: 10, wins: 6, losses: 4, win_rate: 60, seconds: 3600 }],
      modes: [{ name: text, aliases: [text], matches: 10, wins: 6, losses: 4, win_rate: 60, kills: 100, kd: 1.5 }],
    }),
    st("wins", 30), st("losses", 20), st("xp", 500000),
    st("time_played", 15, { unit_of_measurement: "h" }),
    st("kd", 2.5), st("kpm", 1.11), st("win_rate", 60), st("accuracy", 25), st("headshot_rate", 15),
    st("human_kill_rate", 80),
    st("rank", 42, { rank_name: text, rank_image: null, ranked: [] }),
    st("favorite_class", text, {
      classes: [
        { name: text, kills: 500, deaths: 200, kd: 2.5, kpm: 1.2, seconds: klassenSekunden },
        { name: "Recon", kills: 100, deaths: 50, kd: 2, kpm: 1, seconds: 1800 },
      ],
    }),
    st("top_weapon", text, { top: liste({}) }),
    st("top_vehicle", text, { top: liste({}) }),
    st("platform", "steam"),
    ["sensor.welt_season_end", { state: "2027-01-19T11:59:00+00:00", attributes: { season: 5, battle_pass: 5, season_start: "2026-10-13T12:00:00+00:00" } }],
    ["sensor.welt_portal_servers", { state: "1000", attributes: {} }],
    ["sensor.welt_portal_players", { state: "500", attributes: {} }],
  ]);
  return {
    entities: entities(),
    devices: {
      "geraet-spieler": { name: text, model: "Battlefield 6 · Steam" },
      "geraet-welt": { name: "BF6-Spielwelt" },
    },
    states,
    locale: { language: "de" },
    callWS: async () => ({}),
  };
}

const KARTEN = {
  "bf6-player-card": {},
  "bf6-arsenal-card": {},
  "bf6-classes-card": {},
  "bf6-maps-card": { min_matches: 1, limit: 10 },
  "bf6-modes-card": {},
  "bf6-squad-card": {},
  "bf6-world-card": {},
  "bf6-history-card": { metric: "kd", period: "day", days: 30 },
};

function zeichnen(element, config, hass) {
  const karte = new (customElements.get(element))();
  karte.setConfig(config);
  karte.hass = hass;
  return karte;
}

for (const element of Object.keys(KARTEN)) {
  await import(new URL(`${element}.js`, basis));
}

const ergebnis = { karten: {}, index: {} };
const normal = hassMit("Testspieler", 7200);
const boese = hassMit(BOESE, BOESE);
for (const [element, config] of Object.entries(KARTEN)) {
  ergebnis.karten[element] = {
    normal: zeichnen(element, config, normal).shadowRoot.innerHTML,
    boese: zeichnen(element, config, boese).shadowRoot.innerHTML,
  };
}

// Index: Wie oft werden die Entitaeten durchlaufen? Ein Proxy zaehlt jedes
// Auflisten der Schluessel (Object.values ruft ownKeys).
let durchlaeufe = 0;
const gezaehlt = new Proxy(entities(), {
  ownKeys(ziel) {
    durchlaeufe += 1;
    return Reflect.ownKeys(ziel);
  },
});
const basisHass = { ...hassMit("Testspieler", 7200), entities: gezaehlt };
const erste = C.spieler(basisHass);
ergebnis.index.spieler = erste.map((s) => ({ name: s.name, modell: s.modell, kills: s.ids.kills }));
ergebnis.index.welt = C.welt(basisHass)?.name ?? null;
// Wie in Home Assistant: bei jeder Zustandsaenderung ein neues hass-Objekt
// mit denselben entities und devices; die Karten zeichnen jedes Mal.
const karten = Object.entries(KARTEN).map(([element, config]) => zeichnen(element, config, basisHass));
const vorUpdates = durchlaeufe;
for (let i = 0; i < 100; i++) {
  const neu = { ...basisHass, states: { ...basisHass.states } };
  for (const karte of karten) {
    karte.hass = neu;
  }
}
ergebnis.index.durchlaeufe_erster_aufbau = vorUpdates;
ergebnis.index.durchlaeufe_100_updates_8_karten = durchlaeufe - vorUpdates;
ergebnis.index.gleiche_liste = C.spieler({ ...basisHass }) === erste;
ergebnis.index.eingefroren = Object.isFrozen(erste) && Object.isFrozen(erste[0]) && Object.isFrozen(erste[0].ids);

// Registry geaendert: neues devices-Objekt (Geraet umbenannt) und neues
// entities-Objekt (Entitaet entfernt)
const umbenannt = { ...basisHass, devices: { ...basisHass.devices, "geraet-spieler": { name: "Neuer Name", model: "Battlefield 6 · Steam" } } };
ergebnis.index.name_nach_umbenennen = C.spieler(umbenannt)[0]?.name ?? null;
const ohneKills = { ...entities() };
delete ohneKills["sensor.spieler_kills"];
ergebnis.index.spieler_ohne_kills_sensor = C.spieler({ ...basisHass, entities: ohneKills }).length;
ergebnis.index.ohne_entities = C.spieler({}).length;

process.stdout.write(JSON.stringify(ergebnis));
