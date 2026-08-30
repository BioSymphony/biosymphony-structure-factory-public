# ChimeraX Peptide Visualization

## Purpose

Plan publication-style molecular render lanes for target windows, candidate poses, and report figures. ChimeraX is the operator-approved render path for structural-biology demos: per-design PNGs, 3-panel hero figures, and labeled spin MP4s straight out of cofold output (top-N PDBs from Boltz / Chai / Genie 3 / RFdiffusion).

## Public-Safe Status

Public scaffold: yes. Runtime use is license-gated. Record the accepted terms and intended commercial or noncommercial use in runtime state. Direct unattended download is not validated by this repository; supply an approved installer path or download client through runtime configuration.

## When To Use

- Per-design hero PNGs (1600×1600, transparent background) for top ranked binder candidates.
- 3-panel figures (receptor / peptide / complex) for the candidate report.
- Labeled spin movies (1080×1080, ~6s at 30fps) for demo deliverables and showcase pages.
- Inactive-vs-active state-comparison morphs for receptor-class campaigns.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the ChimeraX Peptide Visualization tool card. For target <PDB:ID> and candidate <path>, prepare a render lane with the target window, candidate pose, view script, label and coloring plan, figure resolution, and the labeled-spin recipe. Note the operator-gated ChimeraX install and license posture in the manifest.
```

## Install On A Headless GPU Pod

```bash
# On a pod with your network volume mounted at /workspace and the
# pre-staged ChimeraX .deb available under /workspace/installers/chimerax/
cp /workspace/installers/ucsf-chimerax_<version>_amd64.deb /tmp/
apt-get update -qq
apt-get install -y --no-install-recommends \
  /tmp/ucsf-chimerax_<version>_amd64.deb \
  xvfb libegl1 libglu1-mesa libxkbcommon0 libxcb-xinerama0

# Headless wrapper:
cat > /usr/local/bin/chimerax-headless <<'EOF'
#!/usr/bin/env bash
exec xvfb-run -a -s "-screen 0 1920x1920x24" /usr/bin/chimerax --offscreen --nogui --silent "$@"
EOF
chmod +x /usr/local/bin/chimerax-headless
```

`xvfb-run` is mandatory on L40 / L40S even with `--nogui` — ChimeraX still spins up an OpenGL context. EGL works on L40 but the X virtual framebuffer is the cheap path that survives across CUDA versions.

## Matchmaker For Difficult Overlays

ChimeraX's default `mmaker` uses BLOSUM-62 + ssFraction 0.3 + 2.0 Å iterative cutoff. On divergent structures (e.g. matching a designed binder onto a reference complex where sequence identity is below ~30%) this collapses to a tiny atom alignment. The fix is to widen the substitution matrix, weight secondary structure, and disable iterative pruning:

```text
open ref.pdb model_design.pdb
mmaker #2 to #1 cutoffDistance none alg nw ssFraction 0.5 matrix BLOSUM-30
```

- `cutoffDistance none` turns off the iterative atom-pruning loop (no atoms are discarded for distance).
- `alg nw` forces full-length Needleman-Wunsch (good when chains are roughly equal length).
- `ssFraction 0.5` lifts the secondary-structure score from 0.3 to 0.5 so a TM bundle aligns to a TM bundle even when sequences diverge.
- `matrix BLOSUM-30` is the most permissive BLOSUM available (use PAM-150 if going across domain boundaries).

For peptide-receptor overlays where the peptide is too short for `nw`, use `alg sw` (Smith-Waterman, local) on the peptide chain only and keep `nw` for the receptor. For very short peptides (<8 residues), skip matchmaker entirely and use `align` on Cα.

## Cartoon Style Recipe

```text
cartoon style protein modeHelix default arrows true xsection oval width 2 thickness 0.6 sides 20 divisions 20
cartoon style strand xsection rectangle width 2.2 thickness 0.5
graphics quality 4
lighting soft
graphics silhouettes true width 3
set bgColor white
```

`modeHelix default` is the spiraling-ribbon helix (publication look). `modeHelix tube` swaps to a smooth cylinder if you want the schematic "TM bundle" image used in textbook figures — useful for the inactive-vs-active comparison panel. `cylinder` is the straight-axis variant. `modeOldSpline` does **not** exist in ChimeraX 1.11+; if a legacy command file references it, replace with `default`.

## Color Scheme Example (Class B GPCR)

For a receptor + peptide binder rendering, a clean default is muted gray for the receptor, pLDDT-colored for the peptide, gold for hotspots. The example below is calibrated to GCGR (PDB 6LMK / UniProt P47871) but the pattern adapts to any receptor:

```text
# Receptor (model #1) — base layer in light gray
color #1 #d3d3d3
color #1:27-136 #c8c8c8                # ECD slightly darker
color #1:137-418 #a0a0a0               # 7TM bundle medium gray
color #1:351-369 #ff8c00               # TM6 in orange for active; #1f6feb for inactive
color #1:419-438 #6b6b6b               # Helix 8

# Hotspot residues — gold
color #1:128,176,202,225,239,329,355 #ffd700

# Peptide ligand (model #2) — pLDDT in B-factor column
color #2 byattribute bfactor palette alphafold range 50,100
```

The `alphafold` palette is built into ChimeraX 1.11+ and matches the AF EBI viewer (orange<50, yellow 50-70, light blue 70-90, dark blue >90). Cofold tools (Boltz, Chai) all write pLDDT into the B-factor column by default, so no preprocessing is needed. On older ChimeraX builds, fall back to `palette 50,red:70,yellow:90,cyan:100,blue`.

## Hero Figure (3-Panel) Recipe

```text
# Panel 1 — receptor alone, gold hotspots
hide #2 models
view #1
turn y 30; turn x -10
save panel1_receptor.png width 1600 height 1600 supersample 4 transparentBackground true

# Panel 2 — peptide alone, pLDDT colored
show #2 models; hide #1 models
view #2
save panel2_peptide.png width 1600 height 1600 supersample 4 transparentBackground true

# Panel 3 — complex, peptide in pocket
show #1 models
view orient
turn y 30; turn x -10
save panel3_complex.png width 1600 height 1600 supersample 4 transparentBackground true
```

`supersample 4` gives 4× oversampled antialiasing (heavy but worth it for hero PNGs). `transparentBackground true` lets the campaign report composite cleanly over its own background.

## Spin Movie Recipe — With Labels

Every demo video should carry **clear labels** so a non-expert viewer can read what they are seeing without context. Six items per spin movie:

```text
# 1080x1080, 30 fps, 6 s, 180 frames at 2 deg / frame, mp4 with h264

# --- LABEL LAYER (do BEFORE movie record) ---
2dlabel text "<receptor name> (chain X)"     xpos 0.03 ypos 0.93 size 28 color black
2dlabel text "<design ID>"                   xpos 0.03 ypos 0.88 size 22 color #1f6feb
2dlabel text "Hotspots: <hotspot list>"      xpos 0.03 ypos 0.83 size 18 color #b8860b
2dlabel text "<headline metric>: <value>"    xpos 0.03 ypos 0.05 size 22 color black
2dlabel text "<arm + tool source>"           xpos 0.03 ypos 0.10 size 18 color #555555
2dlabel text "pLDDT: red<50, yellow<70, cyan<90, blue=100" xpos 0.78 ypos 0.05 size 14 color #333333

movie record size 1080,1080 supersample 2
turn y 2 180
wait 180
movie encode spin.mp4 framerate 30 quality high
2dlabel delete all
```

**Mandatory labels checklist for every demo video:**
- [ ] Receptor name + chain ID
- [ ] Design ID (arm + index)
- [ ] Hotspot residues (so viewer sees what was targeted)
- [ ] Headline metric (e.g. `ipSAE_min` across the validator slate, or `iPTM` from the chosen cofolder)
- [ ] Arm + tool source (so viewer can compare arms in a multi-arm bake-off)
- [ ] **Color legend** if pLDDT-colored: render a small alphafold-palette legend in a corner

For demo reports, two common renders are useful: a 6-s "headshot" spin of the complex (with full labels) and a 3-s state-comparison morph (e.g. `morph` between an inactive and an active deposition with a label like "Active vs inactive · TM6 swing").

## Gotchas

| # | Gotcha | Fix |
|---|---|---|
| 1 | `xvfb-run` mandatory even with `--nogui` | Wrap into `chimerax-headless` once (see Install) |
| 2 | `2dlabel` placement must precede `movie record` | Add labels first; `2dlabel delete all` after `movie encode` |
| 3 | `modeOldSpline` does not exist in 1.11+ | Use `modeHelix default` (publication) or `modeHelix tube` (textbook) |
| 4 | Default `mmaker` fails on divergent structures | `mmaker #2 to #1 cutoffDistance none alg nw ssFraction 0.5 matrix BLOSUM-30` |
| 5 | `supersample 4` quadruples render time | Use 4 for hero PNGs; 2 for MP4s (4 is prohibitively slow for video) |
| 6 | `alphafold` palette only on 1.11+ | Fallback `palette 50,red:70,yellow:90,cyan:100,blue` on older builds |
| 7 | UCSF download CGI is JS+cookie gated | Never `wget` — pre-stage the `.deb` to your network volume |

Additional small notes:
- `lighting soft` is good for hero PNGs; `lighting full` gives shadows but quadruples render time.
- `graphics silhouettes true width 3` is the cheap "edge-line" trick that makes cartoons pop on white backgrounds.
- `mmaker` silently produces garbage on chains shorter than ~8 residues; use `align` on Cα for very short peptides.

## Integration With The Render Pipeline

```text
[cofold output PDBs]
   |
   v
ChimeraX render stage
   +- per-design: 1600x1600 PNG (complex view, pLDDT-colored peptide)
   +- per-arm:    3-panel hero figure (receptor / peptide / complex)
   +- per-arm:    6 s spin MP4 of the top design (with mandatory labels)
   +- capstone:   3 s state-comparison morph MP4 (when applicable)
```

Runs as a stage in the bridge manifest, downstream of cofold + ranking, in parallel with the Rosetta / MolProbity refinement leg (see [`refinement-stack.md`](refinement-stack.md)).

## Gates

- Do not bake gated binaries into a public image by default.
- Reject screenshot-only closeout for real render lanes — figures need provenance.
- Keep generated render batches out of git; publish only curated summaries or small reviewed images.
- Pre-stage the ChimeraX `.deb` via an operator-side transfer; the UCSF CGI cannot be reached headlessly.
- Run a currency check before any paid GPU dispatch: upstream ChimeraX release notes (new commands, deprecated commands like `modeOldSpline`) and recent rendering / publication-figure preprints. Record the ChimeraX version and the date of the check in the candidate ranking.

## Links

- [ChimeraX cartoon command reference](https://www.rbvi.ucsf.edu/chimerax/docs/user/commands/cartoon.html)
- [ChimeraX matchmaker reference](https://www.rbvi.ucsf.edu/chimerax/docs/user/commands/matchmaker.html)
- [ChimeraX feature highlights (helix tube, alphafold palette)](https://www.rbvi.ucsf.edu/chimerax/features.html)
