// Revisa el catálogo de Pedix y guarda en stock.json qué perfumes están "Sin stock".
// Lo ejecuta GitHub Actions cada 10 minutos (ver stock.yml).
const { chromium } = require('playwright');
const fs = require('fs');

const CATEGORY_URL = 'https://pedix.app/labusca/categoria/dGlBqD50PcsXAXVpgE3k';
const OUT_FILE = 'stock.json';
const MIN_PRODUCTS = 100;      // si lee menos productos que esto, asume que falló y NO toca stock.json
const HEARTBEAT_HOURS = 6;     // aunque no haya cambios, renueva la fecha cada tanto (la landing ignora datos viejos)

function sameList(a, b) {
  return a.length === b.length && a.every((x, i) => x === b[i]);
}

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, locale: 'es-AR' });
       await page.goto(CATEGORY_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForSelector('a[href*="/producto/"]', { timeout: 60000 });
    // Pedix carga los productos a medida que se baja: scrolleamos hasta que deje de aparecer gente nueva
    let last = -1, still = 0;
    for (let i = 0; i < 200 && still < 6; i++) {
      const n = await page.evaluate(() => document.querySelectorAll('a[href*="/producto/"]').length);
      if (n === last) still++; else { still = 0; last = n; }
      await page.evaluate(() => {
        const links = document.querySelectorAll('a[href*="/producto/"]');
        if (links.length) links[links.length - 1].scrollIntoView({ block: 'end' });
        window.scrollBy(0, window.innerHeight * 0.9);
      });
      await page.waitForTimeout(600);
    }

    const items = await page.evaluate(() => {
      const SEL = 'a[href*="/producto/"]';
      const seen = new Map();
      document.querySelectorAll(SEL).forEach(a => {
        if (seen.has(a.href)) return;
        // subir hasta la "tarjeta" que contiene SOLO este producto
        let node = a;
        while (node.parentElement && node.parentElement.querySelectorAll(SEL).length === 1) node = node.parentElement;
        const sinStock = [...node.querySelectorAll('.content-without-stock')]
          .some(e => /sin stock/i.test(e.textContent || ''));
        let name = (a.getAttribute('title') || '').trim();
        if (!name) {
          name = (a.textContent || '').split('$')[0].trim().replace(/\s+/g, ' ');
          const half = name.length / 2;                       // el texto viene duplicado: "X X"
          if (name.slice(0, half).trim() === name.slice(half).trim()) name = name.slice(0, half).trim();
        }
        seen.set(a.href, { name, sinStock });
      });
      return [...seen.values()];
    });

    const total = items.length;
    const out = [...new Set(items.filter(i => i.sinStock && i.name).map(i => i.name))].sort();
    console.log(`Productos leídos: ${total} | Sin stock: ${out.length}`);
    out.forEach(n => console.log('  - ' + n));

    if (total < MIN_PRODUCTS) throw new Error(`Solo se leyeron ${total} productos (mínimo ${MIN_PRODUCTS}). No se actualiza stock.json.`);
    if (out.length === total) throw new Error('Todos los productos figuran sin stock: probablemente falló la lectura. No se actualiza stock.json.');

    let prev = { outOfStock: [], updated: null };
    try { prev = JSON.parse(fs.readFileSync(OUT_FILE, 'utf8')); } catch (e) {}
    const ageH = prev.updated ? (Date.now() - new Date(prev.updated).getTime()) / 36e5 : Infinity;

    if (sameList(prev.outOfStock || [], out) && ageH < HEARTBEAT_HOURS) {
      console.log('Sin cambios, no se escribe nada.');
      return;
    }
    fs.writeFileSync(OUT_FILE, JSON.stringify({ updated: new Date().toISOString(), total, outOfStock: out }, null, 2) + '\n');
    console.log('stock.json actualizado.');
  } finally {
    await browser.close();
  }
})().catch(err => { console.error(err); process.exit(1); });
