"""
Actualiza stock.json desde Google Sheets (CSV).
Lee por TITULO de columna (fila 1):  Nombre | BasePrice | Stock
Genera: {"actualizado": "...", "perfumes": [{"nombre", "stock", "precio", ...}, ...]}
  - stock : True/False segun la columna Stock (SI/NO)
  - precio: precio del proveedor (BasePrice). La pagina le aplica el multiplicador.
  - categoria, genero, temporada, notas, imagen: se copian si existen (la pagina los usa
    para agregar sola los perfumes nuevos). El ORDEN de la lista es el orden de la hoja.
"""
import csv
import io
import json
import os
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

SHEET_CSV_URL = os.getenv("SHEET_CSV_URL", "")
ORIGINALES_GID = os.getenv("ORIGINALES_GID", "1700000001")   # numero (gid) de la pestana Originales

# Nombres de la planilla que difieren del nombre que usa la pagina (errores de tipeo).
# Formato:  "NOMBRE EN LA PLANILLA": "Nombre en la pagina"
ALIAS = {
    "OSYSSEY TYRANT G5": "Odyssey Tyrant G5",
    "VULVAN SABLE G5": "Vulcan Sable G5",
    "KHARMRAH DUKHAN G5": "Khamrah Dukhan G5",
    "KHARMRAH WAHA G5": "Khamrah Waha G5",
    "HOMME ANIVERSARY G5": "Homme Anniversary G5",
    "LATEEN ROJO": "Lateen Rojo G5",
    "AL HARAMAIN GOLD 120ml G5 (dorado y negro)": "Al Haramain Gold 120ml G5",
}


def norm(s):
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


ALIAS_N = {norm(k): v for k, v in ALIAS.items()}


def fetch_csv(url, gid_forzado=None):
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
            try:
                gid = url.split("gid=")[1].split("#")[0].split("&")[0]
            except Exception:
                pass
        if gid:
            final_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        else:
            final_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    else:
        final_url = url

    if gid_forzado:   # otra pestana de la misma hoja (ej: Originales)
        if "gid=" in final_url:
            final_url = re.sub(r"gid=\d+", f"gid={gid_forzado}", final_url)
        else:
            final_url += ("&" if "?" in final_url else "?") + f"gid={gid_forzado}"

    print(f"Descargando CSV de: {final_url}")
    r = requests.get(final_url, timeout=30)
    r.raise_for_status()
    r.encoding = "utf-8"
    print(f"CSV descargado, {len(r.text)} chars, primeras 200: {r.text[:200]}")
    return r.text


def parse_price(raw):
    """'18000', '$18.000', '18,000', '$ 18.000,00', '18000.50' -> entero. Vacio/invalido -> None."""
    s = re.sub(r"[^\d.,]", "", str(raw or ""))
    if not s:
        return None
    if "." in s and "," in s:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        s = s.replace("," if dec == "." else ".", "").replace(dec, ".")
    elif re.fullmatch(r"\d{1,3}([.,]\d{3})+", s):      # separador de miles (18.000 / 18,000)
        s = re.sub(r"[.,]", "", s)
    else:
        s = s.replace(",", ".")                         # decimal con coma
    try:
        v = float(s)
    except ValueError:
        return None
    return int(round(v)) if v > 0 else None


def parse_stock(text, con_venta=False):
    perfumes = []
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise ValueError("No se detectaron columnas en el CSV")

    fieldnames_lower = {norm(k): k for k in reader.fieldnames if k}
    print(f"Columnas detectadas: {reader.fieldnames}")

    def find_key(options):
        for possible in options:
            if possible in fieldnames_lower:
                return fieldnames_lower[possible]
        return None

    nombre_key = find_key(["nombre"]) or list(reader.fieldnames)[0]

    stock_key = find_key(["stock", "disponible", "estado", "h"])
    if not stock_key:
        stock_key = reader.fieldnames[7] if len(reader.fieldnames) > 7 else reader.fieldnames[-1]

    precio_key = find_key(["baseprice", "base price", "precio proveedor", "precio base", "precio"])
    venta_key = find_key(["precio venta", "precio de venta"]) if con_venta else None

    # Columnas opcionales: se copian tal cual al stock.json
    extras = {
        "categoria": find_key(["categoria", "marca"]),
        "genero": find_key(["genero"]),
        "temporada": find_key(["temporada"]),
        "notas": find_key(["notas"]),
        "imagen": find_key(["imagen", "foto"]),
    }

    print(f"Usando Nombre={nombre_key}, Stock={stock_key}, Precio={precio_key}")
    print(f"Columnas extra: {extras}")
    if not precio_key:
        print("AVISO: no encontre la columna de precio (BasePrice); stock.json saldra sin precios")

    for row in reader:
        nombre = (row.get(nombre_key) or "").strip()
        if not nombre or nombre.lower() == "nombre":
            continue
        nombre = ALIAS_N.get(norm(nombre), nombre)

        stock_raw = (row.get(stock_key) or "").strip().lower()
        # si dice no, sin, false, 0, vacio = sin stock
        stock = stock_raw not in ["no", "n", "false", "0", "sin stock", "sin", "falta", "x", ""]

        item = {"nombre": nombre, "stock": stock}
        precio = parse_price(row.get(precio_key)) if precio_key else None
        if precio:
            item["precio"] = precio
        if venta_key:
            venta = parse_price(row.get(venta_key))
            if venta:
                item["venta"] = venta
        for campo, key in extras.items():
            valor = (row.get(key) or "").strip() if key else ""
            if valor:
                item[campo] = valor
        perfumes.append(item)

    return perfumes


def main():
    if not SHEET_CSV_URL:
        raise ValueError("Falta SHEET_CSV_URL")
    csv_text = fetch_csv(SHEET_CSV_URL)
    perfumes = parse_stock(csv_text)

    print(f"Total leidos: {len(perfumes)}")
    sin_stock = [p["nombre"] for p in perfumes if not p["stock"]]
    print(f"Sin stock ({len(sin_stock)}): {sin_stock}")
    sin_precio = [p["nombre"] for p in perfumes if "precio" not in p]
    if sin_precio:
        print(f"Sin precio ({len(sin_precio)}): {sin_precio}")

    # Seguridad: si algo salio mal y viene casi vacio, NO pisar el stock.json bueno
    if len(perfumes) < 50:
        raise ValueError(f"Solo se leyeron {len(perfumes)} perfumes; se cancela para no romper stock.json")

    ahora = datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d %H:%M")
    output = {"actualizado": ahora, "perfumes": perfumes}

    # Pestana "Originales" (misma hoja, otra pestana). Si falla, se conserva lo anterior y NO se toca lo de los G5.
    try:
        csv_o = fetch_csv(SHEET_CSV_URL, gid_forzado=ORIGINALES_GID)
        orig = parse_stock(csv_o, con_venta=True)
        orig = [o for o in orig if o.get("precio")]        # hace falta nombre y precio
        print(f"Originales leidos: {len(orig)}")
        # Defensa: si trajo los mismos perfumes que la pestana de los G5, el enlace no distingue pestanas
        nombres_g5 = {norm(x["nombre"]) for x in perfumes}
        repetidos = [x for x in orig if norm(x["nombre"]) in nombres_g5]
        if orig and len(repetidos) >= max(3, len(orig) // 2):
            print("AVISO: la pestana Originales trajo los mismos perfumes que la de los G5 "
                  "(el enlace de la hoja no esta distinguiendo pestanas). Se ignora y no se guardan originales.")
            orig = []
        output["originales"] = orig
    except Exception as e:
        print(f"AVISO: no pude leer la pestana Originales ({e}); se conserva lo anterior")
        try:
            previo = json.loads(Path("stock.json").read_text(encoding="utf-8")).get("originales")
            if previo is not None:
                output["originales"] = previo
        except Exception:
            pass
    Path("stock.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print("stock.json generado OK")


if __name__ == "__main__":
    main()
