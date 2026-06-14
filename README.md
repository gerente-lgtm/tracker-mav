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

1. Tras cada partido se agrega una fila de balance en la base de Notion.
2. El script [`scripts/actualizar_balances.py`](scripts/actualizar_balances.py) consulta
   Notion y regenera [`balances.json`](balances.json).
3. El tablero (`index.html`) lee ese JSON y se actualiza solo.

> `balances.json` es un archivo **generado**. No editarlo a mano.

### Estructura de `balances.json`

```jsonc
{
  "actualizado": "",
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

- **Programado:** cada 30 min en la franja de partidos
  (18:00–06:00 UTC ≈ 1:00 PM–1:00 AM hora Colombia, UTC-5).
- **Manual:** pestaña **Actions → "Actualizar balances desde Notion" → Run workflow**.

### Configuración necesaria

- Secreto del repo **`NOTION_TOKEN`**: token de una integración de Notion con permiso de
  lectura sobre la base de balances.
- (Opcional) variable de entorno `NOTION_DB_ID` para apuntar a otra base; por defecto usa
  el `database_id` de la base "Tracker MAV — Balances".

El script solo usa la biblioteca estándar de Python (sin dependencias que instalar).

## Correr el script localmente

```bash
export NOTION_TOKEN="<token de la integración de Notion>"
python scripts/actualizar_balances.py
```

Esto regenera `balances.json` en la raíz del repo.

## Ver el tablero localmente

Como hace `fetch("balances.json")`, abrir el archivo con `file://` no funciona; usar un
servidor estático:

```bash
python -m http.server 8000
# abrir http://localhost:8000
```
