#!/usr/bin/env python3
"""Shared provider-policy constants for Structure Factory validators.

Single source of truth for which compute providers and provider classes are
recognized, and which may be marked as reviewed remote paths. Imported by both
provider_profile_check.py and module_manifest_check.py so the two validators
cannot drift: a previous divergence let `make provider-check` pass while
`make test` failed.
"""

from __future__ import annotations

# Compute providers Structure Factory recognizes.
ALLOWED_PROVIDERS = {
    "runpod",
    "local",
    "ssh_hpc",
    "generic_cloud",
    "neocloud",
    "aws",
    "modal",
    "lambda",
    "fal",
}

# Provider execution classes.
ALLOWED_PROVIDER_CLASSES = {
    "pod",
    "workstation",
    "slurm_job",
    "cloud_vm",
    "gpu_pod",
    "batch_job",
    "serverless_function",
}

# Providers permitted to set `blessed_path: true` (first-class remote paths).
BLESSED_PROVIDERS = {"runpod", "aws", "modal", "lambda"}
