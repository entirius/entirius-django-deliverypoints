# Changelog

## 2.2.0 — 2026-10-12

- Access: the module declares its own access areas on its AppConfig and its admin views (copied from the
  entirius-django-access defaults; behaviour unchanged).
- OpenAPI: pagination URL examples use `https://api.example.com` instead of `localhost`. Metadata only.
- OpenAPI: the `id` path parameter of the public delivery point is described. Metadata only.
- Optional sibling apps that are installed but not enabled no longer crash imports (`RuntimeError` is caught like
  `ImportError`).

### Security

- `point_service.update_point` applies only the listed point fields and refuses any other keyword with a
  `ValueError` (it set every keyword on the model, a foreign-key column included). The admin API is unchanged: its
  request schema sends only those fields.

## 2.1.0 — 2026-08-06

- Custom point type change support and a carrier update guard.
- Public API pagination and view caching.

## 2.0.0 — 2026-07-10

- Initial public release: carrier pickup points (InPost, DPD, Orlen) and
  custom locations (showrooms, retail stores) for storefront maps and
  checkout delivery selection.
- v2 Admin + Public API, channel scoping (Pattern 2), translated point-type
  names.
- Migrations squashed into a single initial migration for the Entirius epoch.
