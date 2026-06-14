# CLAUDE.md

Guía para trabajar en este repo. Este directorio es el repo **`tracker-mav`**
(remote: https://github.com/gerente-lgtm/tracker-mav, **público**), que es el
**Componente 1 (Tracker web)** + el script de balances del **Componente 3 (Notion)**
del sistema de Pronósticos Mundial 2026.

> Repo **público**: no incluir datos personales (nombres, correos, teléfonos) en
> archivos versionados, comentarios ni commits.

## Idioma y trato

- Responder en **español**, tuteo. Ser directo y honesto; decir "no sé" si no hay certeza.
- NO usar nombres de mitología griega para la IA.
- Señalar un riesgo **una vez** con claridad y luego **ejecutar** lo que decida el dueño,
  sin repetir advertencias ni empujar a "la opción más fácil".

## Qué hace este repo

Un tablero web estático que muestra cómo van los 3 formularios
(**MAV - SELLO**, **MAV - SOLSTICIO**, **MAV - DISRUPTIVO**) en un concurso de
pronósticos del Mundial 2026.

- [index.html](index.html): el tablero completo (HTML+CSS+JS en un solo archivo).
  - Diseño estilo Apple, temas claro/oscuro con toggle que persiste en `localStorage`
    (solo el tema; los datos NO van en localStorage).
  - Colores por formulario: **Sello azul, Solsticio naranja, Disruptivo violeta**.
  - Dos pestañas: **Principal** (posiciones) y **Ganagol** (partidos 1·X·2).
  - Tarjetas por formulario, gráfica Chart.js (CDN) de evolución, y tabla histórica
    (puntos + posición balance a balance).
  - Lee los datos con `fetch("balances.json?ts=...")`. **No** hay backend.
- [balances.json](balances.json): datos que consume el tablero. **Generado**, no editar a mano.
- [scripts/actualizar_balances.py](scripts/actualizar_balances.py): lee la base de Notion
  "Tracker MAV — Balances" y reescribe `balances.json`. Solo stdlib (`urllib`), sin deps.
- [.github/workflows/actualizar-balances.yml](.github/workflows/actualizar-balances.yml):
  corre el script cada 30 min en franja de partidos (18:00–06:00 UTC = 1 PM–1 AM COL),
  y hace commit/push de `balances.json` si cambió. También se dispara a mano (Actions).

## Notion (fuente de datos)

- El script usa el **database_id** `45d7083a-287f-45b0-8791-ca66a1ee2c5d` en la API
  (`/v1/databases/{id}/query`). **NO** usar el data_source_id (`bad6f75f-...`) ahí:
  causa error 404. Override por env var `NOTION_DB_ID` si hace falta.
- Auth: secreto de repo **`NOTION_TOKEN`** (integración Notion "Agente MAV", solo lectura).
  El código lee todo de `os.environ` — nunca escribir claves en el repo.
- Columnas de la base: Etiqueta (title), Juego (Principal/Ganagol), Orden, Campo,
  y `{Sello,Solsticio,Disruptivo} pts` + `{...} pos`, Fecha.

## Flujo de mantenimiento

1. El organizador publica un balance tras cada partido → se agrega una fila en la base de
   Notion "Tracker MAV — Balances" → este repo lo recoge solo (workflow) y actualiza el tablero.
2. Los reportes intermedios durante un partido no son definitivos; el balance definitivo es
   cuando termina toda la jornada.

## Convenciones al editar

- `index.html` es un solo archivo autocontenido: mantener ese estilo, no separar en módulos
  ni introducir build tools salvo que Martín lo pida.
- No editar `balances.json` a mano: es salida del script. Si cambia el esquema del JSON,
  ajustar `construir_balances()` en el script **y** el render en `index.html`.
- Mantener el script sin dependencias externas (solo stdlib de Python).
- Commits y comentarios en español, como el resto del repo.
- No commitear datos personales ni secretos. Las credenciales van solo como secretos
  del repo en GitHub (`NOTION_TOKEN`).

## Contexto más amplio (otros repos, no en este directorio)

- **`agente-pronosticos-mav`**: agente diario en Telegram que recomienda picks según el
  protocolo MAV. Lee los picks vigentes desde Notion (base "Picks Vigentes MAV").
- Los lineamientos completos del sistema (los 3 formularios, reglas de puntos, IDs de Notion)
  se mantienen fuera de este repo público por contener datos del concurso.
