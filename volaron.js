// MISTYCAL - Los que volaron hoy
fetch('./stock.json?v='+Date.now(),{cache:'no-store'})
.then(r=>r.json()).then(data=>{
  const sin = data.perfumes.filter(p=>!p.stock);
  if(!sin.length) return;
  const html = `
  <section style="background:#0f0f0f;padding:60px 20px;text-align:center;color:#fff;margin:40px 0">
    <h2 style="font-size:28px;letter-spacing:3px;margin-bottom:10px">🔥 LOS QUE VOLARON HOY</h2>
    <p style="opacity:0.6;margin-bottom:30px">Hoy se fueron estos, pero te dejamos su reemplazo idéntico</p>
    <div style="display:flex;gap:20px;justify-content:center;flex-wrap:wrap">
      ${sin.map(p=>`
        <div style="background:#1a1a1a;padding:20px;border-radius:12px;width:200px">
          <div style="text-decoration:line-through;opacity:0.5">${p.nombre}</div>
          <div style="margin:10px 0">👇</div>
          <div style="color:#d4af37;font-weight:bold">${p.reemplazo || 'Mismo ADN - Consultar'}</div>
          <button style="margin-top:15px;background:#d4af37;border:none;padding:10px 20px;border-radius:20px;cursor:pointer">RESERVAR REEMPLAZO</button>
        </div>
      `).join('')}
    </div>
  </section>`;
  const target = document.querySelector('#perfumes') || document.querySelector('main');
  if(target) target.insertAdjacentHTML('beforebegin', html);
});
