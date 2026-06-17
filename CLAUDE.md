# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
  - Botón "Actualizar datos" (`#refreshBtn`) en el encabezado: re-lee `balances.json`
    y repinta (solo cliente). NO regenera desde Notion (eso requeriría un token, que
    no puede ir en una página pública).
- [balances.json](balances.json): datos que consume el tablero. **Generado**, no editar a mano.
- [scripts/actualizar_balances.py](scripts/actualizar_balances.py): lee la base de Notion
  "Tracker MAV — Balances" y reescribe `balances.json`. Solo stdlib (`urllib`), sin deps.
- [.github/workflows/actualizar-balances.yml](.github/workflows/actualizar-balances.yml):
  corre el script y hace commit/push de `balances.json` si cambió. Se dispara **por
  evento** (`repository_dispatch` tipo `balance-actualizado`) cuando el buzón termina de
  escribir en Notion; un **cron de respaldo** (23:00 y 05:00 UTC = 6 PM y 12 AM COL) cubre
  fallos del disparo o ediciones a mano en Notion. También se dispara a mano (Actions).

## Comandos

No hay build, lint ni tests. Es un sitio estático + scripts de stdlib.

- **Ver el tablero en local:** `python -m http.server 8000` y abrir
  `http://localhost:8000`. Abrir `index.html` con `file://` **no** funciona porque hace
  `fetch("balances.json")`.
- **Regenerar `balances.json` desde Notion:** `python scripts/actualizar_balances.py`
  (requiere `NOTION_TOKEN` en el entorno).
- **Probar el parser de PDF sin escribir en Notion:**
  `python scripts/pdf_a_notion.py --file BALANCE.pdf --dry-run` (requiere pdfplumber).

## Notion (fuente de datos)

- El script usa el **database_id** `45d7083a-287f-45b0-8791-ca66a1ee2c5d` en la API
  (`/v1/databases/{id}/query`). **NO** usar el data_source_id (`bad6f75f-...`) ahí:
  causa error 404. Override por env var `NOTION_DB_ID` si hace falta.
- Auth: **`NOTION_TOKEN`** (integración Notion "Agente MAV"). Capacidades necesarias:
  **Read + Update + Insert content**. El tracker solo lee; la ingesta de PDFs hace
  *update* (filas existentes) e *insert* (filas nuevas). Ojo: sin **Insert content**,
  crear un balance nuevo da `403 Forbidden` (actualizar sí funciona) — fue un tropiezo real.
  El código lee todo de `os.environ` — nunca escribir claves en el repo.
- Columnas de la base: Etiqueta (title), Juego (Principal/Ganagol), Orden, Campo,
  y `{Sello,Solsticio,Disruptivo} pts` + `{...} pos`, Fecha.

## Flujo de mantenimiento

El organizador publica un PDF de balance tras cada partido. Caminos para llevar
esos datos a Notion (y de ahí, vía workflow, al tablero):

1. **Automático, sin PC (lo normal).** Se sube el PDF a un repo privado "buzón" y
   un GitHub Action lo procesa y escribe la fila en Notion. Ver "Ingesta de
   balances desde PDF" abajo.
2. **Manual.** Agregar/editar la fila directamente en la base de Notion
   "Tracker MAV — Balances".

En ambos casos el workflow `actualizar-balances.yml` regenera `balances.json` y el
tablero se actualiza. En el camino automático (1) el buzón **dispara el workflow al
instante** (`repository_dispatch`) al terminar de escribir en Notion; el camino manual (2)
queda cubierto por el cron de respaldo (o disparándolo a mano en Actions). Los reportes
**intermedios** durante un partido NO son definitivos; el definitivo es cuando
termina toda la jornada.

`balances.json` lleva el campo `actualizado` (fecha/hora hora Colombia) que el
tablero muestra como "Última actualización"; solo cambia cuando cambian los datos.

## Ingesta de balances desde PDF (repo privado "buzón")

- **El parser vive aquí:** [scripts/pdf_a_notion.py](scripts/pdf_a_notion.py). Lee
  los PDF con **pdfplumber** y hace *upsert* de las 3 formas MAV (pts + pos, Principal y
  Ganagol) en Notion por (número de balance + juego). **Marca cada fila como parcial o
  definitiva** (`es_parcial` detecta "Parcial", partidos sin marcar, "ajustados hasta…")
  en la columna checkbox **`Parcial`**. Como el parcial y su definitivo comparten
  (número + juego), van a la **misma fila**: un parcial nuevo pisa al anterior y el
  definitivo apaga la marca. El tablero muestra el aviso "Parcial" en tarjeta, tabla y
  gráfica. Un parcial cuyo ranking no se puede leer se aparta a `parciales/` sin subir. La
  parte de Notion usa solo stdlib (`urllib`); pdfplumber es la única dependencia.
- **Dónde corre (sin PC):** en un **repo privado aparte** (el "buzón"). Un Action se
  dispara al subir un PDF a su carpeta `pendientes/`; instala pdfplumber, **descarga
  este parser por URL cruda**
  (`raw.githubusercontent.com/gerente-lgtm/tracker-mav/main/scripts/pdf_a_notion.py`),
  lo corre con `NOTION_TOKEN` (secreto del repo privado) y archiva el PDF en
  `procesados/` o `parciales/`. **Por eso `pdf_a_notion.py` debe seguir en este repo
  público** (no tiene secretos).
- **Dispara el tracker al terminar:** como último paso, el Action del buzón hace
  `POST /repos/gerente-lgtm/tracker-mav/dispatches` con `{"event_type":"balance-actualizado"}`
  usando el secreto **`TRACKER_DISPATCH_PAT`** del buzón (un PAT con `Contents: write`
  sobre `tracker-mav`; el `GITHUB_TOKEN` normal no puede disparar workflows cross-repo).
  Eso lanza `actualizar-balances.yml` de inmediato. Disparar de más es inocuo: el
  workflow es idempotente y no commitea si Notion no cambió.
- El buzón es **privado** porque los PDF traen datos de otros participantes; NUNCA
  van en este repo público (el `.gitignore` bloquea `*.pdf` por si acaso).
- **Uso:** subir el PDF a `pendientes/` del buzón (desde el celular). En ~1 min el
  Action escribe en Notion y dispara el tracker; el tablero se actualiza en segundos.
- **Depurar en local:** `python scripts/pdf_a_notion.py --file X.pdf --dry-run`
  (no escribe en Notion; requiere pdfplumber instalado).

## Convenciones al editar

- `index.html` es un solo archivo autocontenido: mantener ese estilo, no separar en módulos
  ni introducir build tools salvo que Martín lo pida.
- No editar `balances.json` a mano: es salida del script. Si cambia el esquema del JSON,
  ajustar `construir_balances()` en el script **y** el render en `index.html`.
- `actualizar_balances.py` (corre en GitHub Actions de ESTE repo): mantenerlo **sin
  dependencias externas** (solo stdlib). `pdf_a_notion.py` sí usa pdfplumber y corre
  en el Action del repo privado "buzón" (que lo descarga de aquí).
- Commits y comentarios en español, como el resto del repo.
- No commitear datos personales ni secretos. Las credenciales van solo como secretos
  del repo en GitHub (`NOTION_TOKEN`).

## Contexto más amplio (otros repos, no en este directorio)

- **`agente-pronosticos-mav`**: agente diario en Telegram que recomienda picks según el
  protocolo MAV. Lee los picks vigentes desde Notion (base "Picks Vigentes MAV").
- Los lineamientos completos del sistema (los 3 formularios, reglas de puntos, IDs de Notion)
  se mantienen fuera de este repo público por contener datos del concurso.
