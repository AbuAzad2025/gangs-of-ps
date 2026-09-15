# Gangs of Palestine

A Flask-based strategy game project with a luxury landing page, game systems, user flows, AI/hostess presentation, and test coverage.

## Project status

This repository is a working game project with:
- Flask app structure and routes
- SQLAlchemy models and database initialization
- templates and custom CSS
- AI/hostess themed presentation and role data
- pytest-based validation

It is not a marketing website only; it is a game app scaffold with game features and active test coverage.

## Tech stack

- Python 3.11+
- Flask
- SQLAlchemy
- Jinja2 templates
- SQLite by default, PostgreSQL supported when configured
- Pytest for automated testing
- Babel for translation infrastructure

## Quick start

1. Clone the repository
   ```bash
   git clone <repo-url>
   cd gangs-of-ps
   ```

2. Create and activate a virtual environment
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Start the app
   ```bash
   python run.py
   ```

5. Open the app in browser
   ```text
   http://localhost:5000
   ```

## Environment variables

The project uses a safe fallback for local development.

Common variables:
```env
SECRET_KEY=change-me
DATABASE_URL=sqlite:///app.db
TEST_DATABASE_URL=sqlite:///:memory:
FLASK_ENV=development
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=700
OPENAI_TEMPERATURE=0.35
```

For PostgreSQL:
```env
DATABASE_URL=postgresql://user:password@host:5432/dbname
TEST_DATABASE_URL=postgresql://user:password@host:5432/test_db
```

If `DATABASE_URL` is malformed, the app falls back to SQLite instead of crashing.

## Testing

Run the real test suite:
```bash
python -m pytest tests -q
```

Current verification in this repo passes with a real pytest run, including route, integration, security, and service tests.

## Project structure

```text
.
??? admin/
??? data/
??? docs/
??? forms/
??? models/
??? routes/
??? services/
??? static/
??? templates/
??? tests/
??? config.py
??? extensions.py
??? factory.py
??? run.py
??? wsgi.py
??? requirements.txt
??? requirements-dev.txt
??? README.md
??? DEPLOY.md
??? pyproject.toml
```

## Database notes

- Default development setup is SQLite for convenience.
- PostgreSQL is supported for production and larger deployments.
- Local development should not depend on a broken DSN string; validation is intentionally forgiving.

## Documentation

Project documentation is organized under [docs/README.md](./docs/README.md). Use it for:
- setup and environment configuration
- deployment procedures
- troubleshooting and support
- project structure overview
- FAQ and configuration decisions

## Deployment notes

For production deployment, use a proper environment file and a real database provider. See [DEPLOY.md](./DEPLOY.md) and [docs/deploy.md](./docs/deploy.md).

## Translation notes

When user-facing text is changed, keep the Babel catalogs in sync:
```bash
python -m babel.messages.frontend extract -F babel.cfg -o translations/messages.pot .
python -m babel.messages.frontend update -i translations/messages.pot -d translations -l en
python -m babel.messages.frontend compile -d translations
```

## Contributing

- Keep documentation factual and current.
- Prefer small, test-backed changes.
- Do not add inflated claims or fictional deployment status into docs.
- Validate with the existing test suite before merging.

## License

This repository currently uses the repository-level project license and conventions already present in the codebase. If a formal license file is added later, it should be documented here explicitly.
