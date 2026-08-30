# ChimeraX Onboarding For Teammates

You are a new agent or operator who needs to render publication-grade structure figures and videos for a binder-design demo. This is the **single-file brief** that gets you to first render in ~30 minutes. The authoritative reference is [`chimerax-peptide-viz.md`](chimerax-peptide-viz.md); this file points you there with calibration on what matters.

## Why this file exists

A consistent ChimeraX-on-cloud-GPU render pipeline produces visibly higher-quality demo videos than PyMOL on the same inputs. Every new demo follows the same pattern. New teammates burn a day re-discovering the gotchas — this doc collapses them.

## TL;DR

You will:

1. Spin a GPU pod (L40 / L40S is the typical render target) with your operator's network volume mounted at `/workspace`.
2. Install ChimeraX from an approved installer path or user-supplied download client after the license gate passes.
3. Drive renders via SSH using ChimeraX command scripts (`.cxc`) wrapped with `xvfb-run` for headless operation.
4. Output: 1600×1600 PNG hero panels + 1080×1080 mp4 spin movies, both with mandatory labels overlaid.

## Where to read deeper

| File | What's in it |
|---|---|
| [`tools/chimerax-peptide-viz.md`](chimerax-peptide-viz.md) | The authoritative cookbook — install recipe, cartoon style, color scheme example, hero recipe, labeled-spin recipe, matchmaker fix |
| [`docs/operational-gotchas.md`](../docs/operational-gotchas.md) | Class #12: UCSF download CGI is JS+cookie gated |

## Install (one-time per pod)

The repository has not validated a direct unattended download from the UCSF ChimeraX download flow. Supply an approved installer path or download client through runtime configuration after the license gate passes. The existing Network Volume path is one supported option, not a requirement.

```bash
# On a pod with the NV mounted at /workspace
cp /workspace/installers/ucsf-chimerax_<version>_amd64.deb /tmp/
apt-get update -qq
apt-get install -y --no-install-recommends \
  /tmp/ucsf-chimerax_<version>_amd64.deb \
  xvfb libegl1 libglu1-mesa libxkbcommon0 libxcb-xinerama0

# Headless shim (xvfb-run is mandatory on L40 even with --nogui)
cat > /usr/local/bin/chimerax-headless <<'EOF'
#!/usr/bin/env bash
exec xvfb-run -a -s "-screen 0 1920x1920x24" /usr/bin/chimerax --offscreen --nogui --silent "$@"
EOF
chmod +x /usr/local/bin/chimerax-headless
```

If you need a different ChimeraX version, you need a fresh `.deb` re-staged on the NV — there is no non-interactive UCSF download path. Operator pre-stages once; install pods are `cp` + `apt-get install` only.

## The 7 gotchas that bite everyone

| # | Gotcha | Fix |
|---|---|---|
| 1 | `xvfb-run` is mandatory even with `--nogui` | Wrap into `chimerax-headless` once (see Install) |
| 2 | `2dlabel` placement must precede `movie record` | Add labels first; `2dlabel delete all` after `movie encode` |
| 3 | `modeOldSpline` does not exist in ChimeraX 1.11+ | Use `modeHelix default` (publication look) or `modeHelix tube` (textbook look) |
| 4 | Default `mmaker` fails on divergent structures | `mmaker #2 to #1 cutoffDistance none alg nw ssFraction 0.5 matrix BLOSUM-30` (use `alg sw` for very short peptides) |
| 5 | Supersample 4 quadruples render time | `supersample 4` for hero PNGs (worth it), `supersample 2` for MP4s (4 is prohibitively slow for video) |
| 6 | `alphafold` palette only exists on 1.11+ | `color #2 byattribute bfactor palette alphafold range 50,100`; on older builds, fallback `palette 50,red:70,yellow:90,cyan:100,blue` |
| 7 | UCSF download CGI is JS+cookie gated | Never `wget` from a fresh pod; always pre-stage the `.deb` to NV |

## Mandatory labels checklist

Every demo video should carry clear labels so a non-expert viewer can read what they are seeing without context. Six items per spin movie:

- [ ] **Receptor name + chain ID** (e.g. "<receptor> (chain X)")
- [ ] **Design ID** (arm + index, e.g. "Design #042")
- [ ] **Hotspots targeted** (e.g. "Hotspots: F33 / W36 / W87")
- [ ] **Headline metric** (e.g. "ipSAE_min: 0.78", or "iPTM: 0.65" if a single cofolder is the chosen validator)
- [ ] **Arm + tool source** (e.g. "Arm B · PepGLAD codesign")
- [ ] **pLDDT color legend** (if peptide is pLDDT-colored): "pLDDT: red<50, yellow<70, cyan<90, blue=100" in a fixed corner

The full `2dlabel` recipe is in [`chimerax-peptide-viz.md`](chimerax-peptide-viz.md#spin-movie-recipe--with-labels).

## Standard render pipeline

```
[cofold output PDBs]
   |
   v
ChimeraX render stage
   +- per-design: 1600×1600 PNG (complex view, pLDDT-colored peptide)
   +- per-arm:    3-panel hero figure (receptor / peptide / complex)
   +- per-arm:    6 s spin MP4 with all 6 labels of the top design
   +- capstone:   3 s morph MP4 for state comparison (when applicable)
```

Runs as a stage in the bridge manifest, downstream of cofold + ranking, in parallel with the Rosetta / MolProbity refinement leg.

## Minimal SSH-driven render skeleton

```bash
# On your driving machine:
read IP PORT < /tmp/render_pod_ssh.txt

# Push your cofold output PDB + a .cxc command script to the pod
scp -P $PORT design_042.pdb root@$IP:/workspace/render/
scp -P $PORT render_design_042.cxc root@$IP:/workspace/render/

# Drive the render
ssh -p $PORT root@$IP \
  'cd /workspace/render && chimerax-headless render_design_042.cxc'

# Pull artifacts back
scp -P $PORT root@$IP:/workspace/render/design_042_spin.mp4 .
scp -P $PORT root@$IP:/workspace/render/design_042_hero.png .
```

A working `render_design_NNN.cxc` template is in your last shipped demo's `render/` directory — start from there.

## Cross-team etiquette

- **Don't `pkill chimerax` or `pkill xvfb`** — there may be other agents' render jobs running on the same host. Kill by PID only, derived from your own SSH session.
- **Don't pre-stage a different ChimeraX version** to the NV without telling the operator — it's reused across all demos.
- **Tag your pods with a unique name** (`<demo>-render-<run-id>`) so other agents can filter by name and avoid touching yours.

## Calibration

A "good" demo video should:

- render in <2 min on L40
- be ≤5 MB at 1080×1080 / 30fps / 6s
- have all 6 labels readable on first viewing
- color-resolve the receptor / ligand / hotspots visually
- pop on a white-background HTML page

If yours doesn't, re-read [`chimerax-peptide-viz.md`](chimerax-peptide-viz.md) — the recipes there are the calibrated baseline.

## Gates

- Do not bake gated binaries into a public image by default.
- Reject screenshot-only closeout for real render lanes.
- Keep generated render batches out of git; publish only curated summaries or small reviewed images.
- Pre-stage the ChimeraX `.deb` via an operator-side transfer; the UCSF CGI cannot be reached headlessly.
- Run a currency check before any paid render lane: upstream ChimeraX release notes (new commands, deprecated commands like `modeOldSpline`) and recent rendering / publication-figure preprints. Record the ChimeraX version and the date of the check in the candidate ranking or validation notes.
