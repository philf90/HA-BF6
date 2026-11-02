// Erfundene Daten fuer die Banner (kein echter Spieler). Aufbau wie die
// Entitaeten der Integration, damit die echten Karten rendern.
const entities = {}, states = {}, devices = {};
function geraet(dev, name, model, werte) {
  devices[dev] = { id: dev, name, model };
  for (const [key, [state, attributes]] of Object.entries(werte)) {
    const id = `sensor.${dev}_${key}`;
    entities[id] = { entity_id: id, platform: "bf6_player", device_id: dev, translation_key: key };
    states[id] = { entity_id: id, state: String(state), attributes: attributes || {}, last_changed: "2026-11-02T10:00:00Z" };
  }
}
const klassen = [
  { name: "Assault", kills: 4210, deaths: 2730, kd: 1.54, kpm: 1.08, seconds: 241200 },
  { name: "Engineer", kills: 3120, deaths: 2210, kd: 1.41, kpm: 0.97, seconds: 193000 },
  { name: "Support", kills: 2380, deaths: 1690, kd: 1.41, kpm: 0.88, seconds: 162400 },
  { name: "Recon", kills: 1460, deaths: 850, kd: 1.72, kpm: 0.93, seconds: 94300 },
];
const karten = [
  { name: "Siege of Cairo", aliases: [], matches: 96, wins: 58, losses: 38, win_rate: 60.42, seconds: 101200 },
  { name: "Empire State", aliases: [], matches: 84, wins: 44, losses: 40, win_rate: 52.38, seconds: 88600 },
  { name: "Liberation Peak", aliases: [], matches: 71, wins: 33, losses: 38, win_rate: 46.48, seconds: 79400 },
  { name: "Mirak Valley", aliases: [], matches: 65, wins: 36, losses: 29, win_rate: 55.38, seconds: 70100 },
  { name: "Manhattan Bridge", aliases: [], matches: 52, wins: 21, losses: 31, win_rate: 40.38, seconds: 55800 },
];
const modi = [
  { name: "Conquest", aliases: [], matches: 288, wins: 161, losses: 127, win_rate: 55.9, kills: 6120, kd: 1.52 },
  { name: "Breakthrough", aliases: [], matches: 214, wins: 103, losses: 111, win_rate: 48.13, kills: 4390, kd: 1.61 },
  { name: "Rush", aliases: [], matches: 96, wins: 54, losses: 42, win_rate: 56.25, kills: 1480, kd: 1.38 },
];
geraet("nachtfalke", "Nachtfalke", "Battlefield 6 · Steam", {
  kills: [11170], deaths: [7480], matches: [652, { maps: karten, modes: modi }], wins: [342], losses: [308], xp: [13820450],
  time_played: [192.3, { unit_of_measurement: "h" }], kd: [1.49], kpm: [0.97], win_rate: [52.45], accuracy: [27.8], headshot_rate: [21.4], human_kill_rate: [97.6],
  rank: [112, { rank_name: "Captain II" }], favorite_class: ["Assault", { classes: klassen }],
  top_weapon: ["M4A1", { top: [] }], top_vehicle: ["M1A2 SEPv3", { top: [] }], platform: ["steam"],
});
geraet("eisvogel", "Eisvogel", "Battlefield 6 · PlayStation", {
  kills: [8240], matches: [511], time_played: [151.0, { unit_of_measurement: "h" }], kd: [1.27], kpm: [0.91], win_rate: [49.71], platform: ["psn"],
});
geraet("welt", "BF6-Spielwelt", "Battlefield 6", {
  season_end: ["2027-01-19T11:59:00+00:00", { season: 5, season_start: "2026-10-13T08:00:00+00:00", battle_pass: 5 }],
  portal_servers: [1493], portal_players: [3120],
});
// Langzeitstatistik fuer die Verlauf-Karte: 30 Tage, K/D leicht steigend mit
// kleinen Schwankungen, zwei Tage ohne Spiel
function statistik(msg) {
  const id = msg.statistic_ids[0], out = [];
  for (let k = 29; k >= 0; k--) {
    if (k === 9 || k === 21) continue;
    const i = 29 - k;
    const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - k);
    out.push({ start: d.getTime(), mean: 1.31 + 0.17 * (i / 29) + 0.03 * Math.sin(i * 0.9) + 0.018 * Math.sin(i * 2.3 + 1), change: 20 + ((k * 53) % 70) });
  }
  return { [id]: out };
}
export const hass = {
  states, entities, devices, language: "de", locale: { language: "de" },
  callWS: async (msg) => statistik(msg),
};
