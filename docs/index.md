---
title: Delivery Points
description: Pickup points and custom locations for Volkanos storefronts and checkout.
sidebar:
  label: Overview
  collapsed: true
---

django-deliverypoints manages carrier pickup points (InPost, DPD, Orlen) and custom locations (showrooms, retail stores). Two use cases: storefront maps for nearest-point lookup, and checkout delivery method selection.

## What It Does

- Stores delivery point types (carriers vs custom locations)
- Manages point coordinates, address, opening hours per type
- Channel-scoped custom points (showrooms per channel) alongside global carrier points
- CSV import with incremental or full sync modes
- Public API for storefront maps with Haversine geo search
- Admin API for full CRUD and bulk import

## Architecture

```
CSV / Admin API (multipart upload)
  → import_service (upsert by type+code)
    → DeliveryPoint (DB)

Public API (AllowAny, channel-scoped)
  → point_service (global + channel points merged)
  → geo_service (Haversine nearby search)
    → Storefront map / Checkout picker
```

Layer rule: `API → Services → Models → DB`. No ORM in views.

## Point Scope: Global vs Channel

| `channel` value | Scope | Example |
|-----------------|-------|---------|
| `NULL` | Global — all channels see this point | InPost locker |
| Set to a Channel | Channel-specific — only that channel | Client showroom |

The public API returns both global points and channel-specific points for the requested channel. Never filter to channel-only in public views.

## Module Dependencies

- **Depends on:** `django_pim.Channel` — `DeliveryPoint.channel` is a nullable FK
- **Depended on by:** `django_checkout` (planned) — will reference `DeliveryPointType` for carrier selection

## Geocoding

Auto-fills lat/lng from address data during CSV import and via CMS address search.

**How to enable:** Set `DELIVERYPOINTS_GOOGLE_GEOCODING_API_KEY` in Django settings. Docker reads the existing `GOOGLE_MAPS_API` env var.

**Behavior when disabled:** Points created without coordinates. CMS address search shows a notice explaining the feature requires configuration. Import proceeds normally, just without coordinate generation.

See [Configuration](./configuration/) for the full settings reference.

## Pages

- [Configuration](./configuration/) — all settings, geocoding setup
- [Data model](/volkanos/modules/deliverypoints/data-model/) — entity fields, constraints, default types
- [Import system](/volkanos/modules/deliverypoints/import/) — CSV format, modes, management command
