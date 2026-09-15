# Game data

This directory contains source data used to initialize and train game
features. It is runtime input, not a cache or a backup directory.

## `seeds/`

The JSON files in `seeds/` provide the initial catalog for game entities:

- `basic_crimes.json` and `organized_crimes.json` — crime definitions
- `daily_tasks.json` — daily task definitions
- `farm_products.json` and `materials.json` — resource and farming items
- `gang_upgrades.json` — gang upgrade definitions
- `hostess_knowledge.json` — shared hostess knowledge
- `items.json` — item catalog
- `locations.json` — map locations
- `vehicles.json` — vehicle catalog

These files are loaded by `utils/essentials.py` and by selected gameplay
services and routes. Keep their field names compatible with the corresponding
models and seed functions.

## `training/hostesses/`

Each hostess directory contains the source material for one AI identity:

- `profile.json` — public identity, role, pricing, visual asset, and gameplay
  attributes
- `system_prompt.txt` — behavioral boundaries and response style
- `knowledge_base.json` — role-specific knowledge
- `training_examples.json` — representative dialogue examples

The repository currently includes named hostesses (`jasmin`, `layla`, `ruby`,
and `sarah`) and role-based profiles used to develop differentiated behavior
(`role_companion`, `role_greeter`, `role_luck`, `role_spy`, and
`role_support`).

## Maintenance rules

1. Do not store backups, database dumps, logs, or generated cache files here.
2. Keep seed JSON valid and encoded as UTF-8.
3. Keep each hostess profile and prompt in the same directory.
4. Do not remove a data file solely because it is not referenced by a
   template; data is consumed by initialization and service code.
5. When changing a schema or a required field, update the loader and tests in
   the same change.
6. Use stable identifiers and avoid duplicate catalog entries.

## Validation

Validate the JSON files before committing:

```bash
python -c "import json; from pathlib import Path; root=Path('data'); [json.loads(p.read_text(encoding='utf-8')) for p in root.rglob('*.json')]; print('data json ok')"
```

Then run the existing test suite:

```bash
python -m pytest tests -q
```

## Ownership

`data/` is maintained alongside the code that consumes it. A data-only change
should still be reviewed for compatibility with models, services, routes, and
translations where applicable.
