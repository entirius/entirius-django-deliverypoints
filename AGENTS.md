# AGENTS.md

Delivery points Django module for Volkanos — distribution `entirius-django-deliverypoints`,
Django app `django_deliverypoints`. Carrier pickup points and custom locations with geo search,
CSV import, translations and channel scoping.

## Commands

| Command | Meaning |
|---|---|
| `make install` | sync dependencies (uv, incl. extras) |
| `make check` | lint + format-check (ruff) |
| `make fix` | auto-fix lint + format |
| `make test` | test suite (pytest + pytest-django) |

## Conventions

- English only: code, docs, commits, branches, PRs.
- MPL-2.0: every non-trivial source file carries the license header (pre-commit inserts it).
- Toolchain: uv + ruff + hatchling + pytest; all config in `pyproject.toml`; `uv.lock` committed.
- Git flow: `master` (production) + `develop` (integration); changes land via PR; semver tag on `master`.
- Never rename the package / Django app_label / DB table prefix `django_deliverypoints` — it is a schema contract.
- Migrations are part of the public contract — never edit an already released migration.
- Access: areas live on the AppConfig (`access_areas`, `access_route_rules`), every admin view carries
  `access_area`; a new admin route without one fails `tests/test_access_ownership.py`.
- Default: do not commit — git is the user's call.

## Architecture

- `models/` — `DeliveryPointType` (carrier vs custom), `DeliveryPoint` (geo coordinates, channels M2M),
  `DeliveryPointChannel` (scoping channel), `DeliveryPointT9N` (name/hint per language),
  `ImportLog` (CSV import audit trail).
- `services/` — point/type/channel CRUD, CSV import (incremental/full), Haversine nearby search,
  optional Google Maps geocoding.
- `schemas/` — pydantic request/response models.
- `api/` — `admin/` (v2, JWT + IsAdminUser) and `public/` (v2, AllowAny, channel-scoped).

Layer rule: `API → Services → Models → DB`. No ORM in views.

## Gotchas

- Empty `channels` M2M means global scope — public API returns both global and channel-matching points.
- `(type, code)` is the natural key for import upsert — not `id`.
- Full import mode disables only points matching the `--type` argument.
- Haversine geo search is application-level (no PostGIS); for >100k points add a bounding-box pre-filter.
- Carrier types (`is_carrier=True`) are read-only — update/delete raise `ValueError`, API returns 403.
- Translation fallback chain: requested language → `channel.default_language` → base point fields.
- `channel_service.sync_channels_from_pim()` is a no-op (returns 0) when `django_pim` is not installed.
- Geocoding is optional — empty `DELIVERYPOINTS_GOOGLE_GEOCODING_API_KEY` = disabled, not broken.
- `code` on point create is auto-generated from `name` if not provided (slugify + `-2`, `-3` dedup).
