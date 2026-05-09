# ClinVCF SDK

[![PyPI version](https://img.shields.io/pypi/v/clinvcf-sdk.svg)](https://pypi.org/project/clinvcf-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/clinvcf-sdk.svg)](https://pypi.org/project/clinvcf-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/ClinVCF/clinvcf-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/ClinVCF/clinvcf-sdk/actions/workflows/ci.yml)

**Official SDK for building [ClinVCF-OS](https://www.fdevelopment.eu/clinVCF) marketplace modules.**

The ClinVCF SDK provides Python types, contracts, and helpers to build clinical genomic modules
that integrate seamlessly with the ClinVCF-OS desktop application — pharmacogenomics callers,
variant classification engines, prediction tools, and annotation pipelines.

> ⚠️ **Research Use Only (RUO)** — Modules built with this SDK are intended for research and
> educational purposes only. They are **not** validated for clinical diagnosis or patient care.

---

## Installation

```bash
pip install clinvcf-sdk
```

Requires Python 3.10 or later.

---

## Quick start

```python
from clinvcf_sdk import (
    ClinVCFModule,
    ModuleManifest,
    ModuleResult,
    ReportFormat,
    PatientMetadata,
    to_qml_payload,
)


class MyModule(ClinVCFModule):
    """Minimal example of a ClinVCF marketplace module."""

    def run(
        self,
        vcf_path: str,
        patient: PatientMetadata,
        config: dict,
    ) -> ModuleResult:
        # Your analysis logic here
        return ModuleResult(
            module_id="my-module",
            module_version="1.0.0",
            executed_at=datetime.now(timezone.utc),
            findings=[...],
        )

    def render_report(
        self,
        result: ModuleResult,
        fmt: ReportFormat,
        language: str = "fr",
    ) -> bytes:
        if fmt == ReportFormat.QML_PAYLOAD:
            payload = self.to_qml_payload(result, language=language)
            return json.dumps(payload).encode("utf-8")
        # ...
```

See the [full documentation](https://www.fdevelopment.eu/clinVCF/sdk) for module manifest
schema, packaging into `.cvf` files, and submission to the ClinStore marketplace.

---

## What's in the SDK

The SDK exposes the contracts and helpers that the ClinVCF-OS host uses to load and run
your module:

- **`ClinVCFModule`** — abstract base class your module subclasses
- **`ModuleManifest`** — pydantic model for `manifest.json` (validation & deserialization)
- **`ModuleResult`** — typed structure returned by `run()`
- **`ReportFormat`** — enum of supported output formats (`HTML`, `PDF`, `JSON`, `QML_PAYLOAD`)
- **`to_qml_payload()`** — convert a result into the JSON payload consumed by the ClinVCF-OS UI
- **`PatientMetadata`** — typed patient context passed to `run()`

The SDK is intentionally minimal. It defines the **contract** between the host and modules,
and provides the **glue** to render results in the host UI. Domain-specific logic
(variant calling, classification, etc.) is the responsibility of each module.

---

## Marketplace certification

Modules submitted to the ClinStore marketplace go through automated validation:

- ✅ `pytest` test suite must pass
- ✅ Manifest schema validation
- ✅ Dependency audit (no known CVEs)
- ✅ Module load + sample-data smoke test
- ✅ Score ≥ 80% to be auto-published
- ✅ Author accepts the **Research Use Only** disclaimer

Modules signed by Fdevelopment LTD are tagged **🛡 Certified Fdevelopment©**, which means
they have been manually audited in addition to passing automated checks.

---

## Repository

- Source: https://github.com/ClinVCF/clinvcf-sdk
- Issues: https://github.com/ClinVCF/clinvcf-sdk/issues
- ClinVCF-OS app: https://www.fdevelopment.eu/clinVCF

---

## License

MIT © 2026 Fdevelopment LTD — see [LICENSE](LICENSE).
