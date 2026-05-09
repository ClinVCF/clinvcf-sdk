# Changelog

All notable changes to `clinvcf-sdk` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.1] — 2026-05-09

### Added

- `to_qml_payload()` helper to convert a `ModuleResult` into a JSON payload
  consumed by the ClinVCF-OS UI (host integration for PharmGx and future modules).
- `ReportFormat.QML_PAYLOAD` enum value for the new in-process module rendering path.
- Optional `publisher`, `entry`, `apis` fields on `ModuleManifest` (auto-deduced
  from `author` and `main`/`entry_class` when omitted, for backward compatibility).

### Changed

- `ModuleManifest` is now permissive (`extra="ignore"`) — unknown fields are
  silently accepted, allowing modules to add custom metadata without breaking
  validation.

---

## [1.0.0] — Initial release

First public release of the SDK. Provides the core types, contracts, and helpers
to build ClinVCF marketplace modules:

- `ClinVCFModule` abstract base
- `ModuleManifest` with pydantic validation
- `ModuleResult` typed structure
- `ReportFormat` enum (HTML, PDF, JSON)
- `PatientMetadata` typed context
- Coverage analyzer, licensing helpers, data sources, reporting context
