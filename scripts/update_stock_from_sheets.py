import csv
import json
import urllib.request
from datetime import datetime

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR-DZF295JuU8woZXtd_oacPPzKpnLED6yEutWTmeQsh__u8q-3ZxSlxxMOPaKFOQ/pub?gid=357045591&single=true&output=csv"

print(f"Descargando {CSV_URL}...")
try:
    with urllib.request.urlopen(CSV_URL) as response:
        content = response.read().decode('utf-8')
except Exception as e:
    print(f"Error descargando: {e}")
    exit(1)

# Parse CSV - maneja comas dentro de campos y saltos de línea
reader = csv.DictReader(content.splitlines())
perfumes = []
con_stock = 0

for row in reader:
    # Nombres de columnas pueden variar
    nombre = (row.get('Nombre Proveedor') or row.get('Nombre') or '').strip()
    if not nombre or 'Nombre Proveedor' in nombre:
        continue
    # Limpiar saltos de línea dentro del nombre
    nombre = nombre.replace('\n',' ').replace('\r',' ').strip()
    
    categoria = (row.get('Categoria') or row.get('Categoría') or '').strip()
    costo = (row.get('Costo Proveedor') or row.get('Costo') or '25000').strip()
    stock_raw = (row.get('Stock Hoy (SI/NO)') or row.get('Stock') or '').strip().upper()
    precio = (row.get('Precio Venta Mistycal') or row.get('Precio') or '62360').strip()
    link = (row.get('Link Pedix') or '').strip()
    
    # Normalizar SI/NO
    if not stock_raw:
        stock = False
    elif 'SI' in stock_raw:
        stock = True
        con_stock += 1
    else:
        stock = False
    
    # Limpiar precio
    try:
        precio_num = int(''.join(filter(str.isdigit, precio)) or '62360')
    except:
        precio_num = 62360
    
    try:
        costo_num = int(''.join(filter(str.isdigit, costo)) or '25000')
    except:
        costo_num = 25000

    perfumes.append({
        "nombre": nombre,
        "categoria": categoria,
        "costo": costo_num,
        "stock": stock,  # true/false
        "stock_text": "SI" if stock else "NO",
        "precio": precio_num,
        "link_pedix": link
    })

print(f"Total: {len(perfumes)} perfumes, {con_stock} con stock")

# Generar stock.json en formato que ya usa tu landing
output = {
    "actualizado": datetime.now().isoformat(),
    "total": len(perfumes),
    "con_stock": con_stock,
    "sin_stock": len(perfumes) - con_stock,
    "perfumes": perfumes
}

with open('stock.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("stock.json generado OK")
