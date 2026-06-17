#!/usr/bin/env python3
"""
Lee la base "Tracker MAV — Balances" de Notion y genera balances.json
en la raiz del repo del tracker. El tracker (index.html) lee ese JSON.
Requiere el secreto NOTION_TOKEN en el repo.
"""

import os
import json
import datetime
import urllib.request

_MESES_ABR = ["ene", "feb", "mar", "abr", "may", "jun",
              "jul", "ago", "sep", "oct", "nov", "dic"]


def sello_tiempo_colombia():
    """Fecha y hora actual en hora Colombia (UTC-5), p.ej. '14/jun/2026 17:45'."""
    tz = datetime.timezone(datetime.timedelta(hours=-5))
    n = datetime.datetime.now(tz)
    return f"{n.day}/{_MESES_ABR[n.month - 1]}/{n.year} {n.hour:02d}:{n.minute:02d}"

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATA_SOURCE_ID = os.environ.get("NOTION_DB_ID", "45d7083a-287f-45b0-8791-ca66a1ee2c5d")
NOTION_VERSION = "2022-06-28"


def consultar_notion():
    url = f"https://api.notion.com/v1/databases/{DATA_SOURCE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    resultados = []
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers=headers, method="POST")
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
        resultados.extend(data.get("results", []))
        if data.get("has_more"):
            cursor = data.get("next_cursor")
        else:
            break
    return resultados


def num(prop):
    if not prop:
        return None
    return prop.get("number")


def texto_titulo(prop):
    arr = prop.get("title", []) if prop else []
    return "".join(t.get("plain_text", "") for t in arr).strip()


def texto_select(prop):
    sel = prop.get("select") if prop else None
    return sel.get("name") if sel else None


def es_checkbox(prop):
    return bool(prop.get("checkbox")) if prop else False


def construir_balances(filas):
    registros = []
    for f in filas:
        p = f.get("properties", {})
        registros.append({
            "etiqueta": texto_titulo(p.get("Etiqueta")),
            "juego": (texto_select(p.get("Juego")) or "").lower(),
            "orden": num(p.get("Orden")) or 0,
            "field": num(p.get("Campo")),
            "parcial": es_checkbox(p.get("Parcial")),
            "sello": {"pts": num(p.get("Sello pts")) or 0, "pos": num(p.get("Sello pos"))},
            "solsticio": {"pts": num(p.get("Solsticio pts")) or 0, "pos": num(p.get("Solsticio pos"))},
            "disruptivo": {"pts": num(p.get("Disruptivo pts")) or 0, "pos": num(p.get("Disruptivo pos"))},
        })

    def filtrar(juego):
        items = [r for r in registros if r["juego"] == juego]
        items.sort(key=lambda x: x["orden"])
        return [{
            "label": r["etiqueta"], "field": r["field"], "parcial": r["parcial"],
            "forms": {"sello": r["sello"], "solsticio": r["solsticio"], "disruptivo": r["disruptivo"]}
        } for r in items]

    return {
        "actualizado": "",
        "principal": filtrar("principal"),
        "ganagol": filtrar("ganagol"),
    }


def main():
    filas = consultar_notion()
    balances = construir_balances(filas)
    out = os.path.join(os.getcwd(), "balances.json")

    # Conservar el sello de tiempo si los DATOS no cambiaron (para no generar
    # commits cada 30 min). Solo se actualiza cuando cambia algún balance.
    previo = None
    if os.path.exists(out):
        try:
            with open(out, encoding="utf-8") as fp:
                previo = json.load(fp)
        except Exception:
            previo = None
    sin_cambios = (previo is not None
                   and previo.get("principal") == balances["principal"]
                   and previo.get("ganagol") == balances["ganagol"]
                   and previo.get("actualizado"))
    balances["actualizado"] = previo["actualizado"] if sin_cambios else sello_tiempo_colombia()

    with open(out, "w", encoding="utf-8") as fp:
        json.dump(balances, fp, ensure_ascii=False, indent=2)
    print(f"balances.json generado: {len(balances['principal'])} principal, "
          f"{len(balances['ganagol'])} ganagol. Actualizado: {balances['actualizado']}")


if __name__ == "__main__":
    main()
