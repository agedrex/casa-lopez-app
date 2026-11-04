# Panel de costos (costo-volumen)

Objective: make the dashboard answer "how much does it cost to produce, what went up, what is stale" and add a break-even simulator with a user-typed price.
Branch: feat/panel-costos. Delivery: single PR (ask-on-risk). Test runner: backend `.venv/bin/python -m pytest -q`; front lint/typecheck.

## Specs

- S1 Scope is costs only. Sales are out; the sale price is a simulator input typed by the user, never stored. (L1, L2)
- S2 Break-even uses FABRICA fixed costs only. "Solo en la Fabrica por ahora". (L3)
- S3 equilibrio_unidades = fijos_fabrica / (precio - costo_variable_unitario); only when precio > costo variable, else a reason, never a number. SUPUESTO: validar con Gerardo/Alejandro.
- S4 Fixed cost per unit = fijos_fabrica / units produced in the month (lots). Total cost per unit = variable + fixed per unit. Volume is PRODUCED, not sold; the screen says so.
- S5 All money is computed by the backend as Decimal strings; the front computes nothing.
- S6 The panel shows: cost of the month, what went up vs the previous month, what is stale (dollar, prices, fixed costs of the month missing, products to requote), and a banner when fixed costs are fictitious or pending (the break-even is not reliable).
- S7 Plain Spanish UI copy for non-technical users; no positional indexes into /grilla.

## Tasks

- [x] T1 (S3, S4, S5) Pure functions in costeo.py + tests. Route: inline.
- [x] T2 (S2, S4, S6) Service `panel_de_costos` + `GET /panel/costos?periodo=&precio=` + tests. Route: delegated (context backstop). Check: 998 passed, 118 skipped; DB loaders not run against PostgreSQL (no local DB).
- [ ] T3 (S6, S7) New panel UI in front/app/(app)/page.tsx using the endpoint. Route: inline.
- [ ] T4 (S6) Automatic month period fallback + stale alerts. Route: inline.

## Log

- L1 (2026-11-04) Original request: audit the system around cost, volume, profit; dashboard focused on costs, how they are managed, how they rise, how they stay updated; non-technical users; scalable recipes; leave ready to test in real time.
- L2 (2026-11-04) "Dejémoslo como una opción para que el usuario ponga el precio de venta ... el precio de venta sea una variable que el usuario ponga al final. No es el foco".
- L3 (2026-11-04) "Solo en la Fabrica por ahora".
