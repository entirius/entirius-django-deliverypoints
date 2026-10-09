# Changelog

## [Unreleased]

- Access: the module declares its own access areas on its AppConfig and its admin views (copied from the
  entirius-django-access defaults; behaviour unchanged).

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
