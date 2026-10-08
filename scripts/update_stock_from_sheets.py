
"""
Script CORREGIDO FINAL - respeta gid y lee Stock correctamente
"""
import csv
import json
import os
import requests
from pathlib import Path
from urllib.parse import urlparse, parse_qs

SHEET_CSV_URL = os.getenv("SHEET_CSV_URL", "")

def fetch_csv(url):
    print(f"URL original: {url}")
    # Si ya es export?format=csv la dejamos tal cual
    if "export?format=csv" in url:
        final_url = url
    elif "/edit" in url:
        # Extraer ID y gid si existe
        parsed = urlparse(url)
        sheet_id = url.split("/d/")[1].split("/")[0]
        qs = parse_qs(parsed.query)
        # gid puede estar en fragment o query
        gid = None
        if "gid" in qs:
            gid = qs["gid"][0]
        elif "gid=" in url:
            # buscar en fragment #gid=
            try:
                gid = url.split("gid=")[1].split("#")[0].split("&")[0]
            except:
                pass
        if gid:
            final_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        else:
            final_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    else:
        final_url = url

    print(f"Descargando CSV de: {final_url}")
    r = requests.get(final_url, timeout=30)
    r.raise_for_status()
    r.encoding = 'utf-8'
    print(f"CSV descargado, {len(r.text)} chars, primeras 200: {r.text[:200]}")
    return r.text

def parse_stock(text):
    perfumes = []
    reader = csv.DictReader(text.splitlines())
    
    if not reader.fieldnames:
        raise ValueError("No se detectaron columnas en el CSV")
    
    fieldnames_lower = {k.lower().strip(): k for k in reader.fieldnames}
    print(f"Columnas detectadas: {reader.fieldnames}")
    
    nombre_key = fieldnames_lower.get("nombre") or list(reader.fieldnames)[0]
    # buscar stock
    stock_key = None
    for possible in ["stock", "disponible", "estado", "h"]:
        if possible in fieldnames_lower:
            stock_key = fieldnames_lower[possible]
            break
    if not stock_key:
        stock_key = reader.fieldnames[-1]
    
    print(f"Usando Nombre={nombre_key}, Stock={stock_key}")
    
    for row in reader:
        nombre = (row.get(nombre_key) or "").strip()
        if not nombre or nombre.lower() == "nombre":
            continue
        stock_raw = (row.get(stock_key) or "").strip().lower()
        
        # si dice no, sin, false, 0, vacio = sin stock
        if stock_raw in ["no", "n", "false", "0", "sin stock", "sin", "falta", "x", ""]:
            stock = False
        else:
            stock = True
        
        perfumes.append({"nombre": nombre, "stock": stock})
    
    return perfumes

def main():
    if not SHEET_CSV_URL:
        raise ValueError("Falta SHEET_CSV_URL")
    csv_text = fetch_csv(SHEET_CSV_URL)
    perfumes = parse_stock(csv_text)
    
    print(f"Total leídos: {len(perfumes)}")
    sin_stock = [p["nombre"] for p in perfumes if not p["stock"]]
    print(f"Sin stock ({len(sin_stock)}): {sin_stock}")
    
    output = {"perfumes": perfumes}
    Path("stock.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print("stock.json generado OK")

if __name__ == "__main__":
    main()
