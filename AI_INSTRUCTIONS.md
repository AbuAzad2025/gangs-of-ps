# Project working rules

This document records the practical rules for working in this repository.

## Core rules

1. Prefer small, test-backed changes.
2. Keep documentation factual and current.
3. Do not claim a feature is production-ready unless it is validated.
4. Use SQLite for local development unless PostgreSQL is explicitly configured.
5. If user-facing text changes, update the Babel catalogs when relevant.
6. Preserve existing patterns and avoid needless duplication.

## Validation

Run the project tests before finishing work when possible:
```bash
python -m pytest tests -q
```

## Database guidance

- SQLite is the default local development database.
- PostgreSQL is supported but should be configured intentionally.
- Malformed DSN values should not be relied on; the app falls back safely in local scenarios.

## Documentation guidance

- Keep the project docs accurate and readable.
- Avoid unrealistic marketing language or legal claims that are not enforced in the repo.
- Prefer short, direct instructions over inflated descriptions.
