#!/usr/bin/env python3
"""
Lee los PDF de balances que publica el organizador y sube las 3 filas de MAV
(Sello / Solsticio / Disruptivo) a la base de Notion "Tracker MAV — Balances".
Luego el workflow del repo regenera balances.json y el tablero se actualiza.

USO TÍPICO (a demanda):
    python scripts/pdf_a_notion.py --dir "RUTA\\Balances PDF (privado)\\pendientes"

Procesa todos los *.pdf de esa carpeta:
  - Extrae pts y posición de las 3 formas (Sello/Solsticio/Disruptivo) para
    Principal y Ganagol y hace upsert en Notion por (número de balance + juego).
  - Marca la fila como PARCIAL o definitiva según el PDF ("Parcial", partidos
    sin marcar…). El parcial y su definitivo comparten fila (mismo número), así
    que un parcial nuevo pisa al anterior y el definitivo apaga la marca.
  - Mueve cada PDF a ..\\procesados (definitivo) o ..\\parciales (parcial).

Banderas:
  --file ARCHIVO   procesar un solo PDF
  --dry-run        no escribe en Notion; solo imprime lo que haría (para validar)
  --no-move        no mover los PDF a procesados

Requisitos:
  - Python 3 + pdfplumber  (pip install pdfplumber)  -> solo para leer el PDF
  - Variable de entorno NOTION_TOKEN con permiso de ESCRITURA sobre la base.
  - (Opcional) NOTION_DB_ID para apuntar a otra base.
La parte de Notion usa solo stdlib (urllib). Nunca se escriben claves en el código.
"""

import os
import re
import sys
import json
import time
import shutil
import datetime
import argparse
import urllib.request
import urllib.error


class _Tee:
    """Escribe a la consola (si existe) y a un archivo de log a la vez."""
    def __init__(self, logfile, console):
        self.logfile = logfile
        self.console = console

    def write(self, s):
        try:
            self.logfile.write(s)
        except Exception:
            pass
        if self.console:
            try:
                self.console.write(s)
            except Exception:
                pass

    def flush(self):
        for t in (self.logfile, self.console):
            try:
                if t:
                    t.flush()
            except Exception:
                pass

DB_ID = os.environ.get("NOTION_DB_ID", "45d7083a-287f-45b0-8791-ca66a1ee2c5d")
NOTION_VERSION = "2022-06-28"

MESES = {
    "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04", "MAY": "05", "JUN": "06",
    "JUL": "07", "AGO": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12",
}

FORMAS = {
    "sello": re.compile(r"MAV\s*-\s*SELLO", re.I),
    "solsticio": re.compile(r"MAV\s*-\s*SOLSTICIO", re.I),
    "disruptivo": re.compile(r"MAV\s*-\s*DISRUPTIVO", re.I),
}


# ----------------------------- Lectura del PDF -----------------------------

def leer_pdf(path):
    """Devuelve (texto_completo, filas) donde filas es la lista de filas de todas
    las tablas (cada fila es una lista de celdas string)."""
    import pdfplumber  # import perezoso: solo se necesita aquí
    texto = []
    filas = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            texto.append(t)
            for tabla in page.extract_tables() or []:
                for fila in tabla:
                    filas.append([(c or "").replace("\n", " ").strip() for c in fila])
    return "\n".join(texto), filas


def as_int(celda):
    if celda is None:
        return None
    t = celda.strip()
    return int(t) if re.fullmatch(r"-?\d+", t) else None


def detectar_juego(texto):
    cab = texto[:400].upper()
    if "GANAGOL" in cab:
        return "Ganagol"
    if "PRONÓSTICO MUNDIAL" in cab or "PRONOSTICO MUNDIAL" in cab:
        return "Principal"
    return None


def detectar_numero(texto):
    m = re.search(r"BALANCE\s*#\s*(\d+)", texto, re.I)
    return int(m.group(1)) if m else None


def detectar_fecha(texto):
    m = re.search(r"(\d{1,2})\.([A-Za-z]{3})\.(\d{4})", texto)
    if not m:
        return None
    dia, mes, anio = m.group(1), m.group(2).upper(), m.group(3)
    if mes not in MESES:
        return None
    return f"{anio}-{MESES[mes]}-{int(dia):02d}"


def es_parcial(texto):
    """True si el balance NO es definitivo: rótulos de parcial o partidos sin
    marcador (p.ej. '(CIV - ECU)' o 'USA -:- PAR')."""
    up = texto.upper()
    if "PARCIAL" in up or "AJUSTADOS HASTA" in up:
        return True
    if "-:-" in texto:
        return True
    # fixture sin marcador: dos códigos de equipo separados por guion, sin dígitos
    if re.search(r"\([A-Z]{3}\s+-\s+[A-Z]{3}\)", texto):
        return True
    return False


def detectar_etiqueta(texto, numero):
    letras = re.findall(r"GRUPO\s+([A-L])\b", texto.upper())
    vistos = sorted(set(letras))
    if not vistos:
        sufijo = ""
    elif len(vistos) == 1:
        sufijo = f" · Grupo {vistos[0]}"
    else:
        sufijo = f" · Grupos {vistos[0]}-{vistos[-1]}"
    return f"B{numero}{sufijo}"


def extraer_mav(filas):
    """Devuelve {forma: {'pts': int, 'pos': int}} y el campo (nº de participantes)."""
    datos = {}
    participantes = 0
    for fila in filas:
        # contar participantes: filas cuya primera celda no vacía es una posición (int)
        primera = next((c for c in fila if c and c.strip()), None)
        if primera is not None and as_int(primera) is not None and as_int(primera) >= 1:
            participantes += 1
        # ¿esta fila es de alguna forma MAV?
        idx_nombre = None
        forma_fila = None
        for i, celda in enumerate(fila):
            for forma, rx in FORMAS.items():
                if rx.search(celda):
                    idx_nombre, forma_fila = i, forma
                    break
            if forma_fila:
                break
        if forma_fila is None:
            continue
        pos = next((as_int(c) for c in fila[:idx_nombre] if as_int(c) is not None), None)
        pts = next((as_int(c) for c in fila[idx_nombre + 1:] if as_int(c) is not None), None)
        if pos is None or pts is None:
            continue
        datos[forma_fila] = {"pts": pts, "pos": pos}
    return datos, (participantes or None)


def parsear(path):
    """Lee un PDF y devuelve un dict con todo lo necesario, o lanza ValueError.

    Procesa tanto definitivos como parciales: el flag 'parcial' indica cuál es.
    El parcial y su definitivo comparten (número + juego), así que se suben a la
    misma fila de Notion (un parcial nuevo pisa al anterior; el definitivo apaga
    la marca). Un parcial cuyo ranking no se puede leer se marca 'incompleto'
    (no hay datos que mostrar) para apartarlo sin error."""
    texto, filas = leer_pdf(path)
    juego = detectar_juego(texto)
    numero = detectar_numero(texto)
    fecha = detectar_fecha(texto)
    if not juego or not numero:
        raise ValueError("no pude identificar juego o número de balance")
    parcial = es_parcial(texto)
    datos, campo = extraer_mav(filas)
    faltan = [f for f in FORMAS if f not in datos]
    if faltan:
        if parcial:
            return {"parcial": True, "incompleto": True, "juego": juego, "numero": numero}
        raise ValueError(f"no encontré las filas de MAV: {', '.join(faltan)}")
    return {
        "parcial": parcial,
        "juego": juego,
        "numero": numero,
        "fecha": fecha,
        "etiqueta": detectar_etiqueta(texto, numero),
        "campo": campo,
        "datos": datos,
    }


# ----------------------------- Escritura Notion ----------------------------

def notion_request(method, url, token, body=None):
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def buscar_fila(token, numero, juego):
    url = f"https://api.notion.com/v1/databases/{DB_ID}/query"
    body = {"filter": {"and": [
        {"property": "Orden", "number": {"equals": numero}},
        {"property": "Juego", "select": {"equals": juego}},
    ]}}
    res = notion_request("POST", url, token, body)
    r = res.get("results", [])
    return r[0]["id"] if r else None


def construir_props(info):
    d = info["datos"]
    props = {
        "Etiqueta": {"title": [{"text": {"content": info["etiqueta"]}}]},
        "Juego": {"select": {"name": info["juego"]}},
        "Orden": {"number": info["numero"]},
        "Sello pts": {"number": d["sello"]["pts"]},
        "Sello pos": {"number": d["sello"]["pos"]},
        "Solsticio pts": {"number": d["solsticio"]["pts"]},
        "Solsticio pos": {"number": d["solsticio"]["pos"]},
        "Disruptivo pts": {"number": d["disruptivo"]["pts"]},
        "Disruptivo pos": {"number": d["disruptivo"]["pos"]},
        "Parcial": {"checkbox": bool(info.get("parcial"))},
    }
    if info.get("campo"):
        props["Campo"] = {"number": info["campo"]}
    if info.get("fecha"):
        props["Fecha"] = {"date": {"start": info["fecha"]}}
    return props


def subir(token, info):
    props = construir_props(info)
    pid = buscar_fila(token, info["numero"], info["juego"])
    if pid:
        notion_request("PATCH", f"https://api.notion.com/v1/pages/{pid}", token,
                       {"properties": props})
        return "actualizada"
    notion_request("POST", "https://api.notion.com/v1/pages", token,
                   {"parent": {"database_id": DB_ID}, "properties": props})
    return "creada"


# --------------------------------- Main ------------------------------------

def resumen(info):
    d = info["datos"]
    return (f"Balance {info['numero']} · {info['juego']} ({info.get('fecha','?')}) "
            f"campo={info.get('campo','?')}\n"
            f"    Sello {d['sello']['pts']}/pos {d['sello']['pos']}  ·  "
            f"Solsticio {d['solsticio']['pts']}/pos {d['solsticio']['pos']}  ·  "
            f"Disruptivo {d['disruptivo']['pts']}/pos {d['disruptivo']['pos']}")


def mover_a(path, carpeta):
    """Mueve el archivo a 'carpeta', sobrescribiendo si ya existía uno igual."""
    os.makedirs(carpeta, exist_ok=True)
    dest = os.path.join(carpeta, os.path.basename(path))
    if os.path.exists(dest):
        os.remove(dest)
    shutil.move(path, dest)


def procesar_uno(path, token, dry_run, mover, dir_procesados, dir_parciales):
    nombre = os.path.basename(path)
    try:
        info = parsear(path)
    except Exception as e:
        print(f"[ERROR] {nombre}: {e}  -> no se sube nada (se deja en pendientes)")
        return False
    if info.get("incompleto"):
        print(f"[OMITIDO] {nombre}: Balance {info['numero']} {info['juego']} "
              f"PARCIAL sin ranking legible (nada que mostrar)")
        if mover and not dry_run and dir_parciales:
            mover_a(path, dir_parciales)
            print(f"    -> apartado a parciales")
        return False
    es_par = bool(info.get("parcial"))
    print(f"[OK] {nombre} ({'PARCIAL' if es_par else 'definitivo'})\n    {resumen(info)}")
    if dry_run:
        print("    (dry-run: no se escribió en Notion)")
        return True
    estado = subir(token, info)
    print(f"    -> fila {estado} en Notion (Parcial={es_par})")
    if mover:
        destino = dir_parciales if es_par else dir_procesados
        if destino:
            mover_a(path, destino)
            print(f"    -> movido a {'parciales' if es_par else 'procesados'}")
    return True


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # evita basura con · y acentos
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Sube balances PDF de MAV a Notion.")
    ap.add_argument("--dir", help="carpeta con PDFs (por defecto: env BALANCES_PDF_DIR)")
    ap.add_argument("--file", help="procesar un solo PDF")
    ap.add_argument("--dry-run", action="store_true", help="no escribir en Notion")
    ap.add_argument("--no-move", action="store_true", help="no mover a procesados")
    ap.add_argument("--log", help="archivo donde anexar la salida (para la tarea programada)")
    args = ap.parse_args()

    if args.log:
        try:
            f = open(args.log, "a", encoding="utf-8")
            sys.stdout = _Tee(f, sys.stdout)
            print(f"\n===== {datetime.datetime.now().isoformat(timespec='seconds')} =====")
        except Exception:
            pass

    token = os.environ.get("NOTION_TOKEN")
    if not args.dry_run and not token:
        sys.exit("Falta NOTION_TOKEN (variable de entorno) con permiso de escritura.")

    if args.file:
        pdfs = [args.file]
        base = os.path.dirname(os.path.abspath(args.file))
    else:
        carpeta = args.dir or os.environ.get("BALANCES_PDF_DIR")
        if not carpeta:
            sys.exit("Indica --dir CARPETA o define BALANCES_PDF_DIR.")
        pdfs = sorted(os.path.join(carpeta, f) for f in os.listdir(carpeta)
                      if f.lower().endswith(".pdf"))
        base = os.path.join(carpeta, "..")
    dir_procesados = os.path.join(base, "procesados")
    dir_parciales = os.path.join(base, "parciales")

    if not pdfs:
        print("No hay PDFs para procesar.")
        return

    ok = 0
    for path in pdfs:
        if procesar_uno(path, token, args.dry_run, not args.no_move,
                        dir_procesados, dir_parciales):
            ok += 1
        time.sleep(0.2)  # cortesía con la API
    print(f"\nListo: {ok}/{len(pdfs)} subidos/validados.")


if __name__ == "__main__":
    main()
