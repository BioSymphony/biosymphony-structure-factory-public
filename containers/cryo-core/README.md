# cryo-core Image Plan

## Purpose

Open-source cryo-EM prep lane for no-download smoke checks, environment validation, and future RELION/Warp/M/Topaz/CTF workflows.

## Candidate Contents

- Ubuntu 22.04 or 24.04 CUDA devel base
- Python 3.11+
- RELION lane
- Warp/M lane where license/build terms permit
- Topaz
- CTFFIND/Gctf gated by terms
- pyem/starfile/mrcfile/gemmi/numpy/scipy/pandas
- Structure Factory scripts copied to `/opt/structure-factory`

## Smoke Command

```bash
python3 /opt/structure-factory/scripts/structure_factory/toolcheck_runner.py \
  --manifest /opt/structure-factory/runpod/launch-manifests/no-download-smoke.json \
  --out /workspace/structure-factory/runs/${STRUCTURE_FACTORY_RUN_ID}
```

## License Policy

Do not include restricted installers or license IDs. Record unavailable tools as gated or missing in `toolcheck.json`.
