# tracker-mav

Tablero web para seguir el desempeño de tres formularios de pronóstico
(**MAV - SELLO**, **MAV - SOLSTICIO**, **MAV - DISRUPTIVO**) en un concurso del
Mundial 2026.

**Tablero en vivo:** https://gerente-lgtm.github.io/tracker-mav/

## Qué muestra

- **Dos pestañas:** *Principal* (posiciones del pronóstico) y *Ganagol* (partidos 1·X·2).
- Tarjetas por formulario con puntos y posición actual.
- Gráfica de evolución (Chart.js) balance a balance.
- Tabla histórica con puntos y posición de cada balance.
- Tema claro/oscuro con un toggle que se recuerda en el navegador.

Es un sitio **estático** (un solo `index.html`, sin backend). Se publica con GitHub Pages
y lee los datos desde `balances.json`.

## Cómo se actualiza (desde Notion)

Los datos salen de una base de Notion ("Tracker MAV — Balances"). El flujo es automático:

1. Tras cada partido se agrega una fila de balance en la base de Notion — normalmente
   automático a partir del PDF del balance (ver [Cargar balances desde PDF](#cargar-balances-desde-pdf)),
   o a mano.
2. El script [`scripts/actualizar_balances.py`](scripts/actualizar_balances.py) consulta
   Notion y regenera [`balances.json`](balances.json), sellando el campo `actualizado`
   (fecha/hora, hora Colombia) que el tablero muestra como "Última actualización".
3. El tablero (`index.html`) lee ese JSON y se actualiza solo.

> `balances.json` es un archivo **generado**. No editarlo a mano.

### Estructura de `balances.json`

```jsonc
{
  "actualizado": "15/jun/2026 00:32",   // fecha/hora de la última actualización (hora Colombia)
  "principal": [
    {
      "label": "B1 · Grupo A",
      "field": 197,                       // tamaño del campo (participantes)
      "forms": {
        "sello":      { "pts": 7, "pos": 79 },
        "solsticio":  { "pts": 7, "pos": 79 },
        "disruptivo": { "pts": 4, "pos": 176 }
      }
    }
  ],
  "ganagol": [ /* misma forma */ ]
}
```

## Automatización (GitHub Actions)

El workflow [`.github/workflows/actualizar-balances.yml`](.github/workflows/actualizar-balances.yml)
ejecuta el script y, si `balances.json` cambió, hace commit y push.

- **Por evento (lo normal):** cuando el repo "buzón" termina de escribir un balance en
  Notion, dispara este workflow con `repository_dispatch` (tipo `balance-actualizado`) y
  el tablero se actualiza en segundos. Ver [Cargar balances desde PDF](#cargar-balances-desde-pdf).
- **Respaldo programado:** 23:00 y 05:00 UTC (≈ 6:00 PM y 12:00 AM hora Colombia, UTC-5),
  por si el disparo falla o si se edita Notion a mano.
- **Manual:** pestaña **Actions → "Actualizar balances desde Notion" → Run workflow**.

### Configuración necesaria

- Secreto del repo **`NOTION_TOKEN`**: token de una integración de Notion con permiso de
  lectura sobre la base de balances.
- (Opcional) variable de entorno `NOTION_DB_ID` para apuntar a otra base; por defecto usa
  el `database_id` de la base "Tracker MAV — Balances".
- El disparo por evento requiere un secreto **`TRACKER_DISPATCH_PAT`** en el **repo buzón**
  (no en este): un token de GitHub con `Contents: write` sobre `tracker-mav`.

El script solo usa la biblioteca estándar de Python (sin dependencias que instalar).

## Correr el script localmente

```bash
export NOTION_TOKEN="<token de la integración de Notion>"
python scripts/actualizar_balances.py
```

Esto regenera `balances.json` en la raíz del repo.

## Cargar balances desde PDF

El organizador publica cada balance como PDF. El script
[`scripts/pdf_a_notion.py`](scripts/pdf_a_notion.py) los lee (con `pdfplumber`),
**descarta los parciales** (partidos sin marcar, "Parcial", "Pronósticos ajustados
hasta…") y escribe las 3 formas MAV (puntos + posición, Principal y Ganagol) en Notion,
haciendo *upsert* por (número de balance + juego).

En producción corre **sin PC**, en un **repo privado aparte** ("buzón"): al subir un PDF a
su carpeta `pendientes/`, un GitHub Action descarga este script por URL cruda y lo ejecuta
con `NOTION_TOKEN` (la integración de Notion necesita permiso de *Insert/Update content*).
Al terminar, ese mismo Action dispara el workflow de este repo (`repository_dispatch`) para
que regenere `balances.json` al instante. Así un balance se carga subiendo el PDF —incluso
desde el celular— y el tablero se actualiza en segundos.

> Los PDF contienen datos de otros participantes: van en el repo privado, **nunca aquí**.
> El [`.gitignore`](.gitignore) bloquea `*.pdf` por seguridad.

Para probar la lectura en local (no escribe en Notion):

```bash
python scripts/pdf_a_notion.py --file BALANCE.pdf --dry-run
```

## Ver el tablero localmente

Como hace `fetch("balances.json")`, abrir el archivo con `file://` no funciona; usar un
servidor estático:

```bash
python -m http.server 8000
# abrir http://localhost:8000
```
