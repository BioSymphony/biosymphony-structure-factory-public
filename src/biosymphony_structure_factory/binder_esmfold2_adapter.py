"""Run Biohub ESMFold2 behind the public binder adapter boundary.

The package imports only the Python standard library at module import time.
The ``readiness`` and ``run`` paths import the operator-installed ESMFold2
runtime. Shipped registry records use local Hugging Face snapshots and make no
network request.

Input is JSONL with one object per candidate. Every object carries a unique
``candidate_id`` and a ``status``. An eligible object also carries ``chains``:

``[{"chain_id": "A", "type": "protein", "sequence": "..."}, ...]``

Output is count-preserving JSONL. Upstream failure and filtered rows remain in
their original order with ``prediction.state`` set to ``not_evaluable``.
Successful rows point to a model mmCIF, a compressed PAE/pLDDT sidecar, and a
confidence summary. Every pointer has a SHA-256 digest.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol


PREDICTION_SCHEMA = "structure-factory-esmfold2-prediction-v1"
CONFIDENCE_SCHEMA = "structure-factory-esmfold2-confidence-v1"
READINESS_SCHEMA = "structure-factory-esmfold2-readiness-v1"
MODEL_SPECS = {
    "full": {
        "predictor_id": "esmfold2",
        "model_id": "biohub/ESMFold2",
        "model_revision": "e1e189d0f5fb70c2693da2332eca4443c0ccccd6",
    },
    "fast": {
        "predictor_id": "esmfold2-fast",
        "model_id": "biohub/ESMFold2-Fast",
        "model_revision": "0438ea0d932a314950665e0b4d0af4322ae88250",
    },
}
ESMC_MODEL_ID = "biohub/ESMC-6B"
ESMC_MODEL_REVISION = "89c554c46a44d825fbfbe3ce2a6bdc539770bdaa"
ELIGIBLE_STATUSES = frozenset({"completed", "eligible", "generated", "passed", "scored"})
CANONICAL_SEQUENCE_RE = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]+$")
CANDIDATE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
CHAIN_ID_RE = re.compile(r"^[A-Za-z0-9]$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAXIMUM_CHAIN_LENGTH = 4096
MAXIMUM_COMPLEX_LENGTH = 8192
READ_BLOCK_BYTES = 1024 * 1024
DEFAULT_NUM_LOOPS = 3
DEFAULT_NUM_SAMPLING_STEPS = 32


class ESMFold2AdapterError(ValueError):
    """The input or runtime cannot satisfy the adapter contract."""


@dataclass(frozen=True)
class PredictionResult:
    """One normalized result returned by an ESMFold2 runtime."""

    structure_cif: str
    pae: Any
    plddt: Any
    ptm: float | None
    iptm: float | None


class PredictionRuntime(Protocol):
    """The small runtime surface used by the dependency-free wrapper."""

    identity: Mapping[str, Any]

    def predict(
        self,
        chains: list[dict[str, str]],
        *,
        candidate_id: str,
        seed: int,
    ) -> PredictionResult: ...


def _reject_constant(_: str) -> None:
    raise ESMFold2AdapterError("prediction JSONL contains a non-finite number")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(READ_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _atomic_write_json(path: Path, value: Any) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    _atomic_write_bytes(path, payload)


def _atomic_write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        for row in rows
    ).encode("utf-8")
    _atomic_write_bytes(path, payload)


def _contained_path(root: Path, raw: Path, label: str, *, output: bool = False) -> Path:
    resolved_root = root.resolve()
    candidate = raw if raw.is_absolute() else resolved_root / raw
    resolved = candidate.resolve()
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise ESMFold2AdapterError(f"{label} must name a path below the run root")
    if not output and (not resolved.is_file() or resolved.is_symlink()):
        raise ESMFold2AdapterError(f"{label} must name a regular file below the run root")
    return resolved


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def read_manifest(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line, parse_constant=_reject_constant)
        except json.JSONDecodeError as exc:
            raise ESMFold2AdapterError(f"prediction JSONL line {line_number} is invalid") from exc
        if not isinstance(row, dict):
            raise ESMFold2AdapterError(f"prediction JSONL line {line_number} must be an object")
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or CANDIDATE_ID_RE.fullmatch(candidate_id) is None:
            raise ESMFold2AdapterError(
                f"prediction JSONL line {line_number} has an invalid candidate_id"
            )
        if candidate_id in seen:
            raise ESMFold2AdapterError("prediction candidate IDs must be unique")
        seen.add(candidate_id)
        if not isinstance(row.get("status"), str) or not row["status"]:
            raise ESMFold2AdapterError(
                f"prediction JSONL line {line_number} must carry a status"
            )
        filter_results = row.get("filter_results", [])
        if not isinstance(filter_results, list) or any(
            not isinstance(item, dict) for item in filter_results
        ):
            raise ESMFold2AdapterError(
                f"prediction JSONL line {line_number} filter_results must be a list of objects"
            )
        rows.append(dict(row))
    if not rows:
        raise ESMFold2AdapterError("prediction JSONL contains no rows")
    return rows


def _eligible(row: Mapping[str, Any]) -> bool:
    return row["status"] in ELIGIBLE_STATUSES and not any(
        result.get("state") in {"filtered", "not_evaluable"}
        for result in row.get("filter_results", [])
    )


def normalize_chains(row: Mapping[str, Any]) -> list[dict[str, str]]:
    raw_chains = row.get("chains")
    if not isinstance(raw_chains, list) or len(raw_chains) < 2:
        raise ESMFold2AdapterError(
            f"candidate {row['candidate_id']} must carry at least two protein chains"
        )
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    total = 0
    for index, raw in enumerate(raw_chains):
        if not isinstance(raw, dict):
            raise ESMFold2AdapterError(
                f"candidate {row['candidate_id']} chain {index} must be an object"
            )
        chain_id = raw.get("chain_id", raw.get("id"))
        if not isinstance(chain_id, str) or CHAIN_ID_RE.fullmatch(chain_id) is None:
            raise ESMFold2AdapterError(
                f"candidate {row['candidate_id']} chain {index} has an invalid chain_id"
            )
        if chain_id in seen:
            raise ESMFold2AdapterError(
                f"candidate {row['candidate_id']} repeats chain_id {chain_id}"
            )
        seen.add(chain_id)
        chain_type = raw.get("type", "protein")
        if chain_type != "protein":
            raise ESMFold2AdapterError(
                f"candidate {row['candidate_id']} chain {chain_id} must have type protein"
            )
        sequence = raw.get("sequence")
        if not isinstance(sequence, str) or CANONICAL_SEQUENCE_RE.fullmatch(sequence) is None:
            raise ESMFold2AdapterError(
                f"candidate {row['candidate_id']} chain {chain_id} must use canonical uppercase amino acids"
            )
        if len(sequence) > MAXIMUM_CHAIN_LENGTH:
            raise ESMFold2AdapterError(
                f"candidate {row['candidate_id']} chain {chain_id} exceeds {MAXIMUM_CHAIN_LENGTH} residues"
            )
        total += len(sequence)
        normalized.append({"chain_id": chain_id, "type": "protein", "sequence": sequence})
    if total > MAXIMUM_COMPLEX_LENGTH:
        raise ESMFold2AdapterError(
            f"candidate {row['candidate_id']} exceeds {MAXIMUM_COMPLEX_LENGTH} total residues"
        )
    observed = complex_sequence_sha256(normalized)
    recorded = row.get("complex_sequence_sha256")
    if recorded is not None and recorded != observed:
        raise ESMFold2AdapterError(
            f"candidate {row['candidate_id']} complex_sequence_sha256 does not match its chains"
        )
    return normalized


def complex_sequence_sha256(chains: list[dict[str, str]]) -> str:
    payload = json.dumps(chains, sort_keys=True, separators=(",", ":")).encode("ascii")
    return _sha256_bytes(payload)


def _to_builtin(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_builtin(item) for item in value]
    raise ESMFold2AdapterError("ESMFold2 returned an unsupported confidence value")


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ESMFold2AdapterError(f"ESMFold2 {label} contains a non-numeric value")
    number = float(value)
    if not math.isfinite(number):
        raise ESMFold2AdapterError(f"ESMFold2 {label} contains a non-finite value")
    return number


def _matrix(value: Any, expected_size: int) -> list[list[float]]:
    normalized = _to_builtin(value)
    while (
        isinstance(normalized, list)
        and len(normalized) == 1
        and isinstance(normalized[0], list)
        and normalized[0]
        and isinstance(normalized[0][0], list)
    ):
        normalized = normalized[0]
    if not isinstance(normalized, list) or len(normalized) != expected_size:
        raise ESMFold2AdapterError("ESMFold2 PAE does not match the complex residue count")
    matrix: list[list[float]] = []
    for row in normalized:
        if not isinstance(row, list) or len(row) != expected_size:
            raise ESMFold2AdapterError("ESMFold2 PAE is not a square residue matrix")
        matrix.append([_finite_number(item, "PAE") for item in row])
    return matrix


def _vector(value: Any, expected_size: int) -> list[float]:
    normalized = _to_builtin(value)
    while isinstance(normalized, list) and len(normalized) == 1 and isinstance(normalized[0], list):
        normalized = normalized[0]
    if not isinstance(normalized, list) or len(normalized) != expected_size:
        raise ESMFold2AdapterError("ESMFold2 pLDDT does not match the complex residue count")
    return [_finite_number(item, "pLDDT") for item in normalized]


def _optional_scalar(value: Any, label: str) -> float | None:
    if value is None:
        return None
    normalized = _to_builtin(value)
    while isinstance(normalized, list) and len(normalized) == 1:
        normalized = normalized[0]
    return _finite_number(normalized, label)


def _validate_structure(cif_text: str) -> None:
    if "_atom_site." not in cif_text or not any(
        line.startswith(("ATOM", "HETATM")) for line in cif_text.splitlines()
    ):
        raise ESMFold2AdapterError("ESMFold2 returned mmCIF without atom_site coordinates")


def _failure_prediction(
    *,
    spec: Mapping[str, str],
    seed: int,
    state: str,
    code: str,
    reason: str,
    input_sha256: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": PREDICTION_SCHEMA,
        "state": state,
        "predictor_id": spec["predictor_id"],
        "model_id": spec["model_id"],
        "model_revision": spec["model_revision"],
        "seed": seed,
        "complex_sequence_sha256": input_sha256,
        "failure_code": code,
        "failure_reason": reason,
        "structure_path": None,
        "structure_sha256": None,
        "confidence_path": None,
        "confidence_sha256": None,
        "confidence_summary_path": None,
        "confidence_summary_sha256": None,
    }


def _write_prediction(
    *,
    run_root: Path,
    artifact_root: Path,
    row: Mapping[str, Any],
    chains: list[dict[str, str]],
    result: PredictionResult,
    runtime_identity: Mapping[str, Any],
    spec: Mapping[str, str],
    seed: int,
) -> dict[str, Any]:
    _validate_structure(result.structure_cif)
    residue_count = sum(len(chain["sequence"]) for chain in chains)
    pae = _matrix(result.pae, residue_count)
    plddt = _vector(result.plddt, residue_count)
    candidate_root = artifact_root / row["candidate_id"] / f"seed-{seed:04d}"
    structure_path = candidate_root / "structure.cif"
    confidence_path = candidate_root / "confidence.json.gz"
    summary_path = candidate_root / "confidence-summary.json"
    structure_payload = result.structure_cif.encode("utf-8")
    confidence_record = {
        "schema_version": CONFIDENCE_SCHEMA,
        "candidate_id": row["candidate_id"],
        "seed": seed,
        "chain_ids": [chain["chain_id"] for chain in chains],
        "chain_lengths": [len(chain["sequence"]) for chain in chains],
        "pae": pae,
        "plddt": plddt,
    }
    confidence_payload = gzip.compress(
        json.dumps(
            confidence_record,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8"),
        compresslevel=9,
        mtime=0,
    )
    _atomic_write_bytes(structure_path, structure_payload)
    _atomic_write_bytes(confidence_path, confidence_payload)
    summary = {
        "schema_version": PREDICTION_SCHEMA,
        "candidate_id": row["candidate_id"],
        "predictor_id": spec["predictor_id"],
        "model_id": spec["model_id"],
        "model_revision": spec["model_revision"],
        "seed": seed,
        "complex_sequence_sha256": complex_sequence_sha256(chains),
        "residue_count": residue_count,
        "chain_ids": [chain["chain_id"] for chain in chains],
        "chain_lengths": [len(chain["sequence"]) for chain in chains],
        "ptm": _optional_scalar(result.ptm, "pTM"),
        "iptm": _optional_scalar(result.iptm, "ipTM"),
        "plddt_mean": sum(plddt) / len(plddt),
        "runtime_identity": dict(runtime_identity),
        "structure_sha256": sha256_file(structure_path),
        "confidence_sha256": sha256_file(confidence_path),
    }
    _atomic_write_json(summary_path, summary)
    return {
        "schema_version": PREDICTION_SCHEMA,
        "state": "predicted",
        "predictor_id": spec["predictor_id"],
        "model_id": spec["model_id"],
        "model_revision": spec["model_revision"],
        "seed": seed,
        "complex_sequence_sha256": summary["complex_sequence_sha256"],
        "chain_ids": summary["chain_ids"],
        "chain_lengths": summary["chain_lengths"],
        "structure_path": _relative(run_root, structure_path),
        "structure_sha256": summary["structure_sha256"],
        "confidence_path": _relative(run_root, confidence_path),
        "confidence_sha256": summary["confidence_sha256"],
        "confidence_summary_path": _relative(run_root, summary_path),
        "confidence_summary_sha256": sha256_file(summary_path),
        "ptm": summary["ptm"],
        "iptm": summary["iptm"],
        "plddt_mean": summary["plddt_mean"],
        "failure_code": None,
        "failure_reason": None,
    }


def run_predictions(
    *,
    run_root: Path,
    input_path: Path,
    output_path: Path,
    artifact_dir: Path,
    variant: str,
    seed: int,
    expected_count: int,
    runtime_factory: Callable[[str], PredictionRuntime],
) -> dict[str, Any]:
    """Run one fixed-seed prediction pass and preserve every input row."""
    if variant not in MODEL_SPECS:
        raise ESMFold2AdapterError("variant must be full or fast")
    if seed < 0:
        raise ESMFold2AdapterError("seed must be zero or greater")
    if expected_count < 1:
        raise ESMFold2AdapterError("expected_count must be a positive integer")
    root = run_root.resolve()
    source = _contained_path(root, input_path, "input")
    destination = _contained_path(root, output_path, "output", output=True)
    artifacts = _contained_path(root, artifact_dir, "artifact directory", output=True)
    if destination == source:
        raise ESMFold2AdapterError("output must differ from input")
    rows = read_manifest(source)
    if len(rows) != expected_count:
        raise ESMFold2AdapterError(
            f"prediction input has {len(rows)} rows; expected {expected_count}"
        )
    normalized = {
        row["candidate_id"]: normalize_chains(row) for row in rows if _eligible(row)
    }
    runtime = runtime_factory(variant) if normalized else None
    spec = MODEL_SPECS[variant]
    output_rows: list[dict[str, Any]] = []
    predicted = 0
    failed = 0
    skipped = 0
    for source_row in rows:
        row = dict(source_row)
        row["upstream_status"] = source_row["status"]
        if not _eligible(source_row):
            row["prediction"] = _failure_prediction(
                spec=spec,
                seed=seed,
                state="not_evaluable",
                code="upstream_status_or_filter",
                reason="The upstream row is failed or filtered.",
                input_sha256=None,
            )
            skipped += 1
            output_rows.append(row)
            continue
        chains = normalized[source_row["candidate_id"]]
        input_sha256 = complex_sequence_sha256(chains)
        try:
            assert runtime is not None
            result = runtime.predict(chains, candidate_id=source_row["candidate_id"], seed=seed)
            row["prediction"] = _write_prediction(
                run_root=root,
                artifact_root=artifacts,
                row=source_row,
                chains=chains,
                result=result,
                runtime_identity=runtime.identity,
                spec=spec,
                seed=seed,
            )
        except (ESMFold2AdapterError, OSError, UnicodeError, ValueError, TypeError) as exc:
            row["status"] = "failed_prediction"
            row["prediction"] = _failure_prediction(
                spec=spec,
                seed=seed,
                state="failed",
                code="prediction_or_sidecar_validation_failed",
                reason=f"The ESMFold2 result failed validation ({type(exc).__name__}).",
                input_sha256=input_sha256,
            )
            failed += 1
        except Exception as exc:  # Optional runtimes expose installation-specific exception types.
            row["status"] = "failed_prediction"
            row["prediction"] = _failure_prediction(
                spec=spec,
                seed=seed,
                state="failed",
                code="runtime_prediction_failed",
                reason=f"The ESMFold2 runtime raised {type(exc).__name__}.",
                input_sha256=input_sha256,
            )
            failed += 1
        else:
            row["status"] = "predicted"
            predicted += 1
        output_rows.append(row)
    if len(output_rows) != len(rows):
        raise ESMFold2AdapterError("prediction output count differs from input count")
    _atomic_write_jsonl(destination, output_rows)
    summary = {
        "input_count": len(rows),
        "output_count": len(output_rows),
        "predicted_count": predicted,
        "failed_count": failed,
        "not_evaluable_count": skipped,
        "output_sha256": sha256_file(destination),
    }
    if normalized and predicted == 0:
        raise ESMFold2AdapterError(
            "no eligible candidate produced a validated prediction; failure rows were written"
        )
    return summary


def _runtime_imports() -> dict[str, Any]:
    """Import the optional ESMFold2 stack only inside a runtime path."""
    import torch
    from esm.models.esmfold2 import ESMFold2InputBuilder
    try:
        from esm.utils.structure import input_builder
    except ImportError:
        import esm.models.esmfold2 as input_builder  # type: ignore[no-redef]
    from huggingface_hub import snapshot_download
    from transformers.models.esmfold2.modeling_esmfold2 import ESMFold2Model

    return {
        "torch": torch,
        "builder": ESMFold2InputBuilder,
        "inputs": input_builder,
        "snapshot_download": snapshot_download,
        "model": ESMFold2Model,
    }


def _snapshot(components: Mapping[str, Any], repo_id: str, revision: str, allow_download: bool) -> Path:
    path = components["snapshot_download"](
        repo_id=repo_id,
        revision=revision,
        local_files_only=not allow_download,
    )
    return Path(path).resolve()


class _BiohubRuntime:
    """Operator-installed Biohub ESMFold2 runtime."""

    def __init__(self, variant: str, *, allow_download: bool, require_cuda: bool) -> None:
        try:
            components = _runtime_imports()
            torch = components["torch"]
            if require_cuda and not torch.cuda.is_available():
                raise ESMFold2AdapterError("CUDA is required but torch reports no CUDA device")
            spec = MODEL_SPECS[variant]
            model_snapshot = _snapshot(
                components, spec["model_id"], spec["model_revision"], allow_download
            )
            esmc_snapshot = _snapshot(
                components, ESMC_MODEL_ID, ESMC_MODEL_REVISION, allow_download
            )
            raw_ccd = os.environ.get("ESMFOLD2_CCD_PATH", "")
            ccd_path = Path(raw_ccd).expanduser().resolve() if raw_ccd else None
            if ccd_path is None or not ccd_path.is_file():
                raise ESMFold2AdapterError(
                    "ESMFOLD2_CCD_PATH must name the reviewed cached ccd.pkl file"
                )
            os.environ["ESMCFOLD_CCD_PATH"] = str(ccd_path)
            try:
                import esm.models.esmfold2.conformers as conformers

                conformers.CCD_PICKLE_PATH = ccd_path
            except ImportError:
                pass
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = components["model"].from_pretrained(
                str(model_snapshot), load_esmc=False, local_files_only=True
            )
            model.load_esmc(str(esmc_snapshot), precision="bf16")
            model = model.to(device)
            model.set_chunk_size(64)
            model.eval()
        except ESMFold2AdapterError:
            raise
        except ModuleNotFoundError as exc:
            raise ESMFold2AdapterError(
                f"the optional ESMFold2 runtime cannot import {exc.name}; run readiness"
            ) from None
        except Exception as exc:
            raise ESMFold2AdapterError(
                f"the ESMFold2 runtime setup failed ({type(exc).__name__}); run readiness"
            ) from None
        self._components = components
        self._model = model
        self._builder = components["builder"](ccd_cache=ccd_path.parent)
        self._device = device
        self.identity = {
            "esm_distribution_version": importlib.metadata.version("esm"),
            "model_id": spec["model_id"],
            "model_revision": spec["model_revision"],
            "esmc_model_id": ESMC_MODEL_ID,
            "esmc_model_revision": ESMC_MODEL_REVISION,
            "device_class": "cuda" if device == "cuda" else "cpu",
            "weight_route": "huggingface_snapshot",
        }

    def predict(
        self,
        chains: list[dict[str, str]],
        *,
        candidate_id: str,
        seed: int,
    ) -> PredictionResult:
        torch = self._components["torch"]
        inputs = self._components["inputs"]
        sequence_inputs = [
            inputs.ProteinInput(id=chain["chain_id"], sequence=chain["sequence"])
            for chain in chains
        ]
        structure_input = inputs.StructurePredictionInput(sequences=sequence_inputs)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        with torch.inference_mode():
            raw = self._builder.fold(
                self._model,
                structure_input,
                num_loops=DEFAULT_NUM_LOOPS,
                num_sampling_steps=DEFAULT_NUM_SAMPLING_STEPS,
                num_diffusion_samples=1,
                seed=seed,
                complex_id=candidate_id,
            )
        if isinstance(raw, list):
            if len(raw) != 1:
                raise ESMFold2AdapterError("ESMFold2 returned an unexpected sample count")
            raw = raw[0]
        return PredictionResult(
            structure_cif=raw.complex.to_mmcif(),
            pae=getattr(raw, "pae", None),
            plddt=getattr(raw, "plddt", None),
            ptm=getattr(raw, "ptm", None),
            iptm=getattr(raw, "iptm", None),
        )


def runtime_readiness(variant: str, *, require_cuda: bool = True) -> dict[str, Any]:
    """Return wrapper, package, cache, CCD, and accelerator readiness separately."""
    if variant not in MODEL_SPECS:
        raise ESMFold2AdapterError("variant must be full or fast")
    result: dict[str, Any] = {
        "schema_version": READINESS_SCHEMA,
        "variant": variant,
        "wrapper_ready": True,
        "package_ready": False,
        "model_cache_ready": False,
        "ccd_ready": False,
        "accelerator_ready": False,
        "ready": False,
        "next_actions": [],
    }
    try:
        components = _runtime_imports()
    except ModuleNotFoundError as exc:
        result["next_actions"].append(
            f"Install the pinned Biohub ESMFold2 runtime; Python cannot import {exc.name}."
        )
        return result
    except (ImportError, RuntimeError):
        result["next_actions"].append(
            "Install compatible pinned esm, transformers, huggingface_hub, and torch packages."
        )
        return result
    result["package_ready"] = True
    torch = components["torch"]
    result["accelerator_ready"] = bool(torch.cuda.is_available()) or not require_cuda
    if not result["accelerator_ready"]:
        result["next_actions"].append("Expose a CUDA device to the installed torch runtime.")
    spec = MODEL_SPECS[variant]
    try:
        _snapshot(components, spec["model_id"], spec["model_revision"], False)
        _snapshot(components, ESMC_MODEL_ID, ESMC_MODEL_REVISION, False)
    except Exception:
        result["next_actions"].append(
            "Cache the pinned ESMFold2 and ESMC-6B Hugging Face snapshots under HF_HOME."
        )
    else:
        result["model_cache_ready"] = True
    ccd_value = os.environ.get("ESMFOLD2_CCD_PATH", "")
    result["ccd_ready"] = bool(ccd_value and Path(ccd_value).expanduser().is_file())
    if not result["ccd_ready"]:
        result["next_actions"].append(
            "Set ESMFOLD2_CCD_PATH to the reviewed cached ccd.pkl file."
        )
    result["ready"] = all(
        result[field]
        for field in ("package_ready", "model_cache_ready", "ccd_ready", "accelerator_ready")
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    readiness = subparsers.add_parser("readiness", help="Check package, cache, CCD, and CUDA state.")
    readiness.add_argument("--variant", choices=sorted(MODEL_SPECS), required=True)
    readiness.add_argument("--allow-cpu", action="store_true")
    run = subparsers.add_parser("run", help="Predict every eligible JSONL row.")
    run.add_argument("--run-root", type=Path, required=True)
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--artifact-dir", type=Path, required=True)
    run.add_argument("--variant", choices=sorted(MODEL_SPECS), required=True)
    run.add_argument("--seed", type=int, required=True)
    run.add_argument("--expected-count", type=int, required=True)
    run.add_argument("--allow-weight-download", action="store_true")
    run.add_argument("--allow-cpu", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "readiness":
        try:
            report = runtime_readiness(args.variant, require_cuda=not args.allow_cpu)
        except ESMFold2AdapterError as exc:
            print(f"esmfold2 adapter: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(report, sort_keys=True, allow_nan=False))
        return 0 if report["ready"] else 2
    try:
        summary = run_predictions(
            run_root=args.run_root,
            input_path=args.input,
            output_path=args.output,
            artifact_dir=args.artifact_dir,
            variant=args.variant,
            seed=args.seed,
            expected_count=args.expected_count,
            runtime_factory=lambda variant: _BiohubRuntime(
                variant,
                allow_download=args.allow_weight_download,
                require_cuda=not args.allow_cpu,
            ),
        )
    except (ESMFold2AdapterError, OSError, UnicodeError) as exc:
        print(f"esmfold2 adapter: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
