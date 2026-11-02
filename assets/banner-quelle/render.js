// Rendert assets/banner.png und assets/social-preview.png aus index.html.
//
//   python3 -m http.server 8000 --bind 127.0.0.1   (im Wurzelverzeichnis des Repos)
//   node assets/banner-quelle/render.js             (Playwright mit Chromium)
//
// Braucht Netz fuer Google Fonts und jsDelivr. Prueft, dass beide Schriften
// geladen sind, damit kein Ersatz in den Bildern landet.
const { chromium } = require("playwright");
const path = require("path");

const BASIS = process.env.BASIS || "http://127.0.0.1:8000/assets/banner-quelle/index.html";
const ZIEL = path.resolve(__dirname, "..");

(async () => {
  const browser = await chromium.launch();
  const fehler = [];
  for (const [f, hoehe, dichte, datei] of [
    ["banner", 256, 2, "banner.png"],
    ["social", 640, 1, "social-preview.png"],
  ]) {
    const seite = await browser.newPage({ viewport: { width: 1280, height: hoehe }, deviceScaleFactor: dichte });
    seite.on("pageerror", (e) => fehler.push(`${f}: ${e.message}`));
    await seite.goto(`${BASIS}?f=${f}`);
    await seite.waitForFunction(() => window.fertig, null, { timeout: 30000 });
    const schriften = await seite.evaluate(() => [...document.fonts].filter((x) => x.status === "loaded").map((x) => x.family));
    for (const s of ["Saira Condensed", "Inter"]) {
      if (!schriften.some((x) => x.replace(/"/g, "") === s)) fehler.push(`${f}: Schrift ${s} nicht geladen`);
    }
    await seite.locator(".rahmen").screenshot({ path: path.join(ZIEL, datei), omitBackground: f === "banner" });
    console.log(`${datei}: ${1280 * dichte} x ${hoehe * dichte}`);
    await seite.close();
  }
  await browser.close();
  if (fehler.length) {
    console.error(fehler.join("\n"));
    process.exit(1);
  }
})();
