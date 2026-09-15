# Static assets

This folder contains the browser-facing files used by the game UI.

## Structure

- `css/` — game and theme stylesheets
- `js/` — frontend behavior and UI logic
- `images/` — gameplay images, avatars, hostesses, items, vehicles, locations
- `adminlte/` — AdminLTE assets used by the admin panel and shared UI
- `plugins/` — third-party plugin assets
- `favicon.ico` — site favicon
- `manifest.json` — PWA manifest
- `sw.js` — service worker

## Maintenance rules

- Keep only files that are referenced by code or templates.
- Avoid adding temporary or duplicate asset variants.
- Prefer reusing project assets instead of creating near-duplicate files.
- If a file is not used in templates, routes, or JS, remove it.

## Naming guidance

- Use lowercase, hyphenated names when possible.
- Keep file names descriptive and stable.
- Prefer one canonical source for each visual asset.
