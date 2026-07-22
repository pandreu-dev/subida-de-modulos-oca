# 07 · Multiempresa / CITRIC / partes de horas

## Compañías (BD `grupo_zambudio_prod_pruebas`)
| id | Compañía |
|----|----------|
| 1 | AUNNA IT / Select Asterisco SL (principal) |
| 2 | CITRIC NETWORKS SL |
| — | MONTOYA, ii, … |

## Usuario afectado
- Manuel Mateo Sendra · login `mmateo@aunnait.es` · user id **52**.
- Compañía principal: AUNNA. Permitidas: AUNNA, MONTOYA, CITRIC, ii.

**Empleados de Manuel:**
| emp id | Nombre | Compañía | Partes |
|--------|--------|----------|--------|
| 64 | Manuel Mateo Sendra | AUNNA | 77 |
| **126** | manuel int. (citric) | CITRIC | 3 ← el de partes antiguos |
| 129 | Manuel ext. (citric) | CITRIC | 0 |
| 134 | C. Manuel int | CITRIC | 0 |

## El error
Al crear un parte nuevo en CITRIC:
```
El proyecto, la tarea y las cuentas analíticas del parte de horas deben pertenecer
a la misma compañía.
```
Traza: `hr_timesheet/models/hr_timesheet.py` → `_timesheet_postprocess_values`; también
aparece `aunna_project_cost_account_moves/models/account_analytic_line.py` (create).

## Causa
`analytic_distribution` mezclaba cuentas de distintas compañías:
- `{'155,90': 100}` / `{'254,90': 100}` — la cuenta **90 "Horas internas" es de AUNNA**.
- Para **CITRIC** debía usarse la cuenta **271** ("Horas internas" de CITRIC).

Sospecha técnica: `account.analytic.distribution.model` inyecta la cuenta 90 al recomputar
`analytic_distribution`, resolviéndose en contexto de **AUNNA** (compañía principal del
usuario).

## Correcciones hechas en PRE
- Creada cuenta **271** "Horas internas" para CITRIC.
- CITRIC configurada con `aunna_default_timesheet_pl_analytic_account_id = 271`.
- En líneas antiguas: `x_plan3_id` cambiado de 90 → 271.
- Proyecto **133** (S00032) pasado a `company_id=2` (CITRIC); sus tareas también.
- Cuenta analítica **155** pasada a `company_id=2` (CITRIC).

**Resultado líneas antiguas:** 13683 → `{'155,271':100}`, 13702 → `{'155,271':100}`,
13837 → `{'254,271':100}`.

## Datos técnicos importantes
- `account.analytic.line.analytic_distribution` es **calculado no almacenado** (json,
  `store=False`, `_compute_analytic_distribution` / inverse). **No existe como columna SQL.**
- Campos reales en `account.analytic.line`: `account_id`, `auto_account_id`,
  `x_plan2_id`, `x_plan3_id`, `x_plan4_id`. El P&L "Horas internas" va en **`x_plan3_id`**.

## Diagnóstico: modelos de distribución que usan la cuenta 90
```bash
sudo -u postgres env PAGER=cat psql -d grupo_zambudio_prod_pruebas <<'SQL'
\set ON_ERROR_STOP on
SELECT id, company_id, account_prefix, partner_id, product_id, product_categ_id, analytic_distribution
FROM account_analytic_distribution_model
WHERE analytic_distribution::text LIKE '%90%'
ORDER BY id;
SQL
```
> Lección para el despliegue: al recrear las **automatizaciones de Studio** y los modelos
> de distribución, deben ser **conscientes de la compañía** (que CITRIC use 271, no 90).
