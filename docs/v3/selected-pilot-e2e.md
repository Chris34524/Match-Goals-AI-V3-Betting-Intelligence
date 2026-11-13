# Piloto funcional multimercado E2E — dos partidos futuros

Piloto entregado: `b7ca9c414cb3c1ec945797653f9cc4e6a6bd414aa973b37b675a632a74430eee`. Corte real **2026-11-07 15:05:31 CST** (2026-11-07T21:05:31.532894+00:00). Los dos reportes finalizaron a `2026-11-07T21:05:31.704694+00:00`, antes de los kickoffs programados. Registro operacional: **NO_BET, OOS excluido, sin calibración acreditada**.

| Partido | ID Flashscore | Kickoff programado, Ciudad de México | HTML | JSON |
| --- | --- | --- | --- | --- |
| Tigres UANL vs Cruz Azul | `Agsy2CLs` | 2026-11-07T19:00:00-06:00 | [Abrir](../../v3_data/selected_analysis/pilots/b7ca9c414cb3c1ec945797653f9cc4e6a6bd414aa973b37b675a632a74430eee/reports/2026-11-07/flashscore_Agsy2CLs/59bf4bec8a63a7cedbf8e1e837419c909c119c2d2e3547e296f06a87dfc454af/report.html) | [JSON](../../v3_data/selected_analysis/pilots/b7ca9c414cb3c1ec945797653f9cc4e6a6bd414aa973b37b675a632a74430eee/reports/2026-11-07/flashscore_Agsy2CLs/59bf4bec8a63a7cedbf8e1e837419c909c119c2d2e3547e296f06a87dfc454af/report.json) |
| Pumas UNAM vs Club América | `AR2jbUK6` | 2026-11-07T21:10:00-06:00 | [Abrir](../../v3_data/selected_analysis/pilots/b7ca9c414cb3c1ec945797653f9cc4e6a6bd414aa973b37b675a632a74430eee/reports/2026-11-07/flashscore_AR2jbUK6/5d2730eb1d93c164741081888b37176859a867b95d448a23c23d602742d8555d/report.html) | [JSON](../../v3_data/selected_analysis/pilots/b7ca9c414cb3c1ec945797653f9cc4e6a6bd414aa973b37b675a632a74430eee/reports/2026-11-07/flashscore_AR2jbUK6/5d2730eb1d93c164741081888b37176859a867b95d448a23c23d602742d8555d/report.json) |

[Índice de ambos reportes](../../v3_data/selected_analysis/pilots/b7ca9c414cb3c1ec945797653f9cc4e6a6bd414aa973b37b675a632a74430eee/index.html) · [Manifest del piloto](../../v3_data/selected_analysis/pilots/b7ca9c414cb3c1ec945797653f9cc4e6a6bd414aa973b37b675a632a74430eee/pilot.json) · [Manifest de entradas congeladas](../../v3_data/selected_analysis/pilots/b7ca9c414cb3c1ec945797653f9cc4e6a6bd414aa973b37b675a632a74430eee/input-manifest.json)

## Qué se implementó y reutilizó

- `v3/selected_analysis/pilot.py`: selección exacta de dos fixtures con el selector existente, evidencia de horario, reloj real, copias inmutables, hashes y replay. No realiza HTTP ni construye clientes de proveedor.
- `v3/selected_analysis/market_matrix.py`: ocho mercados/familias, fuente, muestra predictiva/observada, cobertura, temporalidad, método y bloqueo. Se incluye en cada JSON y en el HTML existente.
- `engine.py` y `report.py`: integración aditiva de la matriz y panel prepartido. Continúan los contratos, Poisson, BT0, observaciones archivadas y estados previos.
- Se conservan las fórmulas/ponderaciones del Champion y los gates de `v3/ops/`, OOS y promoción. La diferencia de impresión de None respecto a origin/main procede de la fase anterior y mantiene el release operativo bloqueado.
- No se leen como features `result.json`, labels ni resultados del target. El comparador lambda archivado se conserva sólo como referencia marcada BLOCKED; nunca es el input del nuevo cálculo.

## Horarios y acreditación

La fuente principal de identidad y de resultados históricos sigue siendo Flashscore México archivado. El locale es insuficiente para acreditar la zona de un kickoff. Por eso el piloto requiere un documento independiente de revisión de horario que conserva ID del fixture seleccionado, identidad completa, fecha, hora con offset, zona, método, referencias y fecha real de revisión. La revisión no otorga acreditación OOS ni permiso de adquisición.

Tigres-Cruz Azul: el listado Flashscore registra 19:00 y N+ publica explícitamente 19:00 del centro de México para el 7 de noviembre; la previa oficial del club corrobora la pareja y jornada. [Programación N+](https://www.nmas.com.mx/deportes/futbol/tigres-vs-cruz-azul-pasa-canal-gratis-tv-en-vivo-hoy-donde-ver-partido-liga-mx-2026/), [previa del club](https://www.tigres.com.mx/es/noticias/la-previa-sportiumbet-tigres-vs-cruz-azul-2/).

Pumas-América: el aviso específico del club indica 21:10 y coincide con el archivo Flashscore. El calendario general muestra 21:00; se registra el conflicto y se prioriza el aviso específico. La zona se interpreta según la sede en Ciudad de México, con ese alcance documentado. La revisión se basó en representación del índice público, sin recaptura deportiva de Flashscore. [Aviso específico](https://pumas.mx/noticias/3748/pumas-encara-el-cl%C3%A1sico-con-la-misi%C3%B3n-de-ganar-en-casa), [segunda ficha oficial](https://pumas.mx/noticias/3746/antecedentes-num%C3%A9ricos-vs-am%C3%A9rica).

El corte final es anterior incluso a las dos variantes de horario publicadas para Pumas. Una revisión de programación no certifica que no vaya a existir una reprogramación posterior. No se usan estadísticas de esas noticias como features.

## Entradas predictivas legítimas y auditoría

Se reutilizó `v3.features.audit` y la matriz de Flashscore sobre 6979 directorios. El árbol tenía 6972 historiales y 6864 archivos xG. Se encontraron 55695 pares numéricos en listas, no partidos históricos únicos ni muestras acreditadas. No se encontró ningún archivo de capabilities reales bajo `v3_data/providers`. [Auditoría del corpus](selected-pilot-corpus-audit.json).

El inventario actual de `data/matches` contiene history/xG/standings, agregados, predicciones/confianza/backtest. No hay un artefacto histórico productivo independiente de mitades, córners o tarjetas en ese árbol. Los agregados de predicción y backtesting no se convierten en evidencia raw para completar esos mercados. La auditoría secuencial no bloquea el pipeline concurrente y no se presenta como snapshot transaccional de todo el corpus.

Para los dos partidos se conservaron **47 archivos** usados: calendario, revisión de horario, historiales, xG, standings, cachés pertinentes y comparaciones descriptivas. Cada archivo conserva SHA-256 y momento de lectura local. `source_captured_at` permanece null cuando el scraper no registró esa información. El corte se fija después de persistir las copias; la generación y finalización también deben ser anteriores a ambos kickoffs.

Goles: se aplica la política histórica existente de resultados fechados y scope reglamentario, excluyendo target, mismo día, futuro, identidad inválida y todas las copias de IDs duplicados. Se usan como máximo 20 muestras por equipo y ventanas/sede existentes; no se suma el tamaño de ventanas solapadas. Los últimos scores usados datan de 2026-11-01 para Tigres-Cruz Azul y 2026-10-31 para Pumas-América. Sus bytes estaban disponibles antes del target y quedaron sellados; eso no acredita automáticamente publicaciones/revisiones históricas ni calibración.

xG: los pares observados son descriptivos. Aun con bytes sellados, el periodo activo no está certificado y las publicaciones/revisiones originales siguen sin acreditarse. No se suministran attestations fabricadas ni se renombran las lambdas del modelo como xG.

Mitades, córners y tarjetas: faltan tanto fixtures/equipos/contexto estables para la ruta de capabilities como muestras históricas verificables por periodo. Tarjetas exige además política de conteo y componentes exclusivos. Se muestran null y el motivo de bloqueo. La semántica de segunda amarilla/roja directa/expulsión no se presume desde un total.

## Matriz por mercado

### Tigres UANL vs Cruz Azul

| Mercado | Fuente | n predictivo por equipo | n xG observado | Cobertura predictiva | Acreditación temporal | Método / estado | Bloqueo |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GOLES | Flashscore / history.json | [20, 20] | — | 100% | Fechas históricas válidas + bytes sellados antes del target; no OOS | BT0 / J_BT_sin_temporada / IMPLEMENTED | Sin calibración/OOS acreditados |
| 1X2 | Flashscore / history.json | [20, 20] | — | 100% | Fechas históricas válidas + bytes sellados antes del target; no OOS | BT0 / J_BT_sin_temporada / IMPLEMENTED | Sin calibración/OOS acreditados |
| DOBLE OPORTUNIDAD | Flashscore / history.json | [20, 20] | — | 100% | Fechas históricas válidas + bytes sellados antes del target; no OOS | BT0 / J_BT_sin_temporada / IMPLEMENTED | Sin calibración/OOS acreditados |
| xG | Flashscore / xg_history.json | [0, 0] | [10, 9] | null | Linaje/periodo específico sin acreditar | Paired historical observed xG/xGA means; not model lambda / BLOCKED | unverified_xg_period_capture_publication_or_identity |
| PRIMERA MITAD | Sin historial acreditado | [0, 0] | — | null | Linaje/periodo específico sin acreditar | independent_poisson / BLOCKED | stable_team_competition_season_ids_required |
| SEGUNDA MITAD | Sin historial acreditado | [0, 0] | — | null | Linaje/periodo específico sin acreditar | independent_poisson / BLOCKED | stable_team_competition_season_ids_required |
| CÓRNERS | Sin historial acreditado | [0, 0] | — | null | Linaje/periodo específico sin acreditar | independent_count_moments_v1 / BLOCKED | stable_team_competition_season_ids_required |
| TARJETAS | Sin historial acreditado | [0, 0] | — | null | Linaje/periodo específico sin acreditar | independent_count_moments_v1 / BLOCKED | explicit_verified_card_counting_policy_required |

### Pumas UNAM vs Club América

| Mercado | Fuente | n predictivo por equipo | n xG observado | Cobertura predictiva | Acreditación temporal | Método / estado | Bloqueo |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GOLES | Flashscore / history.json | [20, 20] | — | 100% | Fechas históricas válidas + bytes sellados antes del target; no OOS | BT0 / J_BT_sin_temporada / IMPLEMENTED | Sin calibración/OOS acreditados |
| 1X2 | Flashscore / history.json | [20, 20] | — | 100% | Fechas históricas válidas + bytes sellados antes del target; no OOS | BT0 / J_BT_sin_temporada / IMPLEMENTED | Sin calibración/OOS acreditados |
| DOBLE OPORTUNIDAD | Flashscore / history.json | [20, 20] | — | 100% | Fechas históricas válidas + bytes sellados antes del target; no OOS | BT0 / J_BT_sin_temporada / IMPLEMENTED | Sin calibración/OOS acreditados |
| xG | Flashscore / xg_history.json | [0, 0] | [10, 8] | null | Linaje/periodo específico sin acreditar | Paired historical observed xG/xGA means; not model lambda / BLOCKED | unverified_xg_period_capture_publication_or_identity |
| PRIMERA MITAD | Sin historial acreditado | [0, 0] | — | null | Linaje/periodo específico sin acreditar | independent_poisson / BLOCKED | stable_team_competition_season_ids_required |
| SEGUNDA MITAD | Sin historial acreditado | [0, 0] | — | null | Linaje/periodo específico sin acreditar | independent_poisson / BLOCKED | stable_team_competition_season_ids_required |
| CÓRNERS | Sin historial acreditado | [0, 0] | — | null | Linaje/periodo específico sin acreditar | independent_count_moments_v1 / BLOCKED | stable_team_competition_season_ids_required |
| TARJETAS | Sin historial acreditado | [0, 0] | — | null | Linaje/periodo específico sin acreditar | independent_count_moments_v1 / BLOCKED | explicit_verified_card_counting_policy_required |

La cobertura 100% de goles significa 20/20 muestras en la ventana seleccionada por equipo; no representa cobertura de todos los mercados ni calidad predictiva validada. La cobertura predictiva null en otros mercados no es cero deportivo. xG observado L10: Tigres/Cruz Azul 10/9, Pumas/América 10/8; esos tamaños no son muestras habilitadas para el modelo.

## Probabilidades disponibles (operacionales)

| Partido | λ total | 1 | X | 2 | Over 2.5 | BTTS sí |
| --- | --- | --- | --- | --- | --- | --- |
| Tigres UANL vs Cruz Azul | 3.007 | 32.95% | 24.10% | 42.95% | 57.84% | 60.18% |
| Pumas UNAM vs Club América | 3.602 | 30.04% | 21.39% | 48.58% | 69.76% | 68.81% |

Poisson conserva la independencia condicional y su incertidumbre. No se promociona un modelo ni se declara rentabilidad a partir de estas cifras. Los JSON contienen under/over 1.5–4.5, dobles y marcadores adicionales.

## Comandos reproducibles

```bash
cd /home/leos/projects/match-goals-ai
.venv/bin/python -m v3.selected_analysis.cli list --date 2026-11-07 --country MÉXICO
.venv/bin/python -m v3.selected_analysis.pilot run \
  --date 2026-11-07 --match-id Agsy2CLs --match-id AR2jbUK6 \
  --schedule v3_data/selected_analysis/pilot_inputs/schedule_20261107_25a2387ac8f3.json

# Reproducir los bytes congelados entregados, incluso después de los partidos:
.venv/bin/python -m v3.selected_analysis.pilot replay \
  v3_data/selected_analysis/pilots/b7ca9c414cb3c1ec945797653f9cc4e6a6bd414aa973b37b675a632a74430eee
```

El comando `run` sólo funciona mientras ambos fixtures sean futuros. No permite fijar un reloj histórico por CLI. Sin IDs/índices, en terminal interactiva imprime la lista y solicita exactamente dos; `--indices` reutiliza el selector existente. El documento de revisión debe corresponder a los IDs seleccionados. El replay mantiene la generación original, verifica inventario/hashes y versión de código, y no cuenta como una nueva predicción.

Si cambia el código, replay rechaza la versión en vez de modificar el pronóstico sellado. Alterar o añadir un archivo dentro de inputs también se rechaza. Se conserva el trabajo anterior y las ejecuciones previas de revisión; la ruta enlazada al inicio es la versión final de esta entrega.

Para archivos de capabilities ya adquiridos de forma autorizada se pueden añadir `--capabilities /ruta/historial.json`; tarjetas acepta `--card-policy /ruta/politica-verificada.json`. Esos argumentos no abren ningún transporte ni acreditan los datos por sí solos. Las pruebas positivas de esos mercados son explícitamente sintéticas, nunca evidencia deportiva real.

API-Football requiere selección explícita del proveedor/IDs y adquisición previa autorizada, con clave por entorno y presupuesto limitado, por sus interfaces existentes. Este piloto no hace live ni fallback; los datos de un proveedor no se asocian a otro por nombres. Una captura actual sin linaje histórico no satisface las ventanas prepartido.

## Verificación y pendientes

Ver [evidencia de pruebas y checks](selected-pilot-validation.json). Se preservan NO_BET, OOS y gates. La preparación de este piloto no constituye un release real.

Pendiente: autorización/mecanismo permitido de adquisición Flashscore; IDs estables y cobertura histórica por periodo; política/eventos de tarjetas; acreditación de xG; backtesting temporal, calibración y ledger OOS prospectivo independiente. Ninguno de esos bloqueos se resuelve reemplazando null por cero o reutilizando λ de goles para córners/tarjetas.
