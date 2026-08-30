#!/usr/bin/env python3
"""Publication-quality PyMOL ray-traced 360° spin videos for binder cofolds.

Per candidate:
  <out>/<cid>_spin.mp4         60-frame ray-traced cartoon+surface+sticks rotation
  <out>/<cid>_hero.png         single hero still from a chosen view angle
  <out>/<cid>.pml              the .pml command script (for reproducibility)

Runs local PyMOL headless: `pymol -cq <pml>`. CPU-only ray tracer — does not
benefit from RunPod GPU. ~2-5 s/frame on M3 Max, ~3-5 min for 60-frame video.

Inputs:
  --ranking path/to/candidate_ranking.local.json
  --out  destination dir (created)
  --hotspots-json optional JSON with {"chain": "A", "residues": [44, 45, 47, ...]}
  --frames N (default 60)
  --width WxH (default 1920x1080)
  --quick  small fast preview (480x270, antialias 0, surface_quality 0)

Skip a candidate that lacks a usable cofold CIF.

License posture: PyMOL Open-Source (BSD-3) — fine for any use, no Schrödinger
educational license needed. Homebrew formula `pymol` is the OS build despite
the license note.
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path
from typing import Any


PML_TEMPLATE = """\
# Auto-generated render script — DO NOT EDIT
# Candidate: {cid} | label: {label}
load {cif_path}, complex
bg_color white
hide everything

# Target = chain A; binder = chain B
show cartoon, chain A
color grey80, chain A
show surface, chain A
set transparency, 0.55, chain A
set surface_quality, {surface_quality}

show cartoon, chain B
color marine, chain B

# Hotspot sticks on target
{hotspot_block}

# Look / ray parameters
set ray_shadows, {ray_shadows}
set ambient, 0.25
set specular, 0.30
set antialias, {antialias}
set ray_trace_mode, 1
set ray_trace_color, black
set cartoon_smooth_loops, 1
set cartoon_fancy_helices, 1
set cartoon_transparency, 0.0
set cache_frames, 0

orient complex
zoom complex, 4

# Hero still (frame -1 — written before spin loop)
ray {width}, {height}
png {hero_png}, dpi=300

# 60-frame Y-axis spin
python
import os
for i in range({frames}):
    cmd.turn("y", {turn_deg})
    cmd.ray({width}, {height})
    cmd.png(os.path.join({frames_dir!r}, "frame_%03d.png" % i), dpi=300)
python end
"""


# Binder-only template: for raw designer outputs (CA-only or full atom).
# Auto-detects which chain is the smaller (binder) and renders only that as a
# clean rainbow ribbon. Uses cartoon_trace_atoms=1 so CA-only PDBs still draw.
PML_TEMPLATE_BINDER_ONLY = """\
# Auto-generated render script (binder-only mode) — DO NOT EDIT
# Candidate: {cid} | label: {label}
load {cif_path}, complex
bg_color white
hide everything

# Settings BEFORE chain detection — thick ribbon, smooth curves, CA-trace mode
set cartoon_trace_atoms, 1
set cartoon_oval_length, 1.0
set cartoon_oval_width, 0.4
set cartoon_loop_radius, 0.5
set cartoon_loop_quality, 16
set cartoon_smooth_loops, 1
set ribbon_width, 6
set ribbon_smooth, 1

# Detect the binder chain (smaller of the two by residue count)
python
chains = cmd.get_chains('complex')
sizes = {{ch: cmd.count_atoms('complex and chain {{}} and name CA'.format(ch)) for ch in chains}}
binder_chain = min(sizes, key=sizes.get) if sizes else 'A'
sel = 'chain ' + binder_chain
cmd.show('cartoon', sel)
cmd.show('ribbon', sel)
cmd.color('marine', sel)
cmd.spectrum('resi', 'blue_white_red', sel)
cmd.orient(sel)
cmd.zoom(sel, 8)
python end

# Look / ray parameters: no outline, full color, soft shading
set ray_shadows, {ray_shadows}
set ambient, 0.35
set specular, 0.15
set antialias, {antialias}
set ray_trace_mode, 0
set cache_frames, 0

# Hero still
ray {width}, {height}
png {hero_png}, dpi=300

# 60-frame Y-axis spin
python
import os
for i in range({frames}):
    cmd.turn("y", {turn_deg})
    cmd.ray({width}, {height})
    cmd.png(os.path.join({frames_dir!r}, "frame_%03d.png" % i), dpi=300)
python end
"""


def build_hotspot_block(chain: str, residues: list[int], color: str = "hotpink") -> str:
    if not residues:
        return "# (no hotspots provided)"
    sel = "+".join(str(r) for r in residues)
    return (
        f"select hot, chain {chain} and resi {sel}\n"
        f"show sticks, hot\n"
        f"color {color}, hot"
    )


def render_one(
    cid: str, label: str, cif_path: Path, out_dir: Path,
    hotspot_chain: str, hotspot_resnums: list[int],
    frames: int, width: int, height: int,
    antialias: int, surface_quality: int, ray_shadows: int,
    pymol_bin: str, mode: str = "complex",
) -> dict[str, Any]:
    frames_dir = out_dir / f"_frames_{cid}"
    frames_dir.mkdir(parents=True, exist_ok=True)
    pml_path = out_dir / f"{cid}.pml"
    hero_png = out_dir / f"{cid}_hero.png"
    mp4_path = out_dir / f"{cid}_spin.mp4"
    turn_deg = 360.0 / max(1, frames)

    template = PML_TEMPLATE_BINDER_ONLY if mode == "binder" else PML_TEMPLATE
    if mode == "binder":
        pml_text = template.format(
            cid=cid, label=label, cif_path=str(cif_path),
            ray_shadows=ray_shadows, antialias=antialias,
            width=width, height=height,
            hero_png=str(hero_png),
            frames=frames, turn_deg=turn_deg,
            frames_dir=str(frames_dir),
        )
    else:
        pml_text = template.format(
            cid=cid, label=label,
            cif_path=str(cif_path),
            hotspot_block=build_hotspot_block(hotspot_chain, hotspot_resnums),
            ray_shadows=ray_shadows, antialias=antialias,
            surface_quality=surface_quality,
            width=width, height=height,
            hero_png=str(hero_png),
            frames=frames, turn_deg=turn_deg,
            frames_dir=str(frames_dir),
        )
    pml_path.write_text(pml_text)

    t0 = time.monotonic()
    proc = subprocess.run(
        [pymol_bin, "-cq", str(pml_path)],
        capture_output=True, text=True,
    )
    render_secs = time.monotonic() - t0
    if proc.returncode != 0:
        return {
            "candidate_id": cid, "ok": False, "render_secs": render_secs,
            "stderr_tail": (proc.stderr or "")[-400:],
            "stdout_tail": (proc.stdout or "")[-400:],
        }

    # ffmpeg mux
    ffmpeg_cmd = [
        "ffmpeg", "-y", "-framerate", "30",
        "-i", str(frames_dir / "frame_%03d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", "18", "-movflags", "+faststart",
        str(mp4_path),
    ]
    fproc = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    if fproc.returncode != 0:
        return {
            "candidate_id": cid, "ok": False, "render_secs": render_secs,
            "ffmpeg_err": (fproc.stderr or "")[-400:],
        }

    # Cleanup raw frames (keep .pml + hero + mp4)
    shutil.rmtree(frames_dir, ignore_errors=True)

    return {
        "candidate_id": cid, "ok": True,
        "render_secs": round(render_secs, 1),
        "hero_png": str(hero_png),
        "mp4": str(mp4_path),
        "pml": str(pml_path),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ranking", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repo-root", type=Path, default=Path.cwd())
    ap.add_argument("--label", default="run")
    ap.add_argument("--hotspots-json", type=Path,
                    help='JSON: {"chain": "A", "residues": [44,45,...]}')
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--quick", action="store_true",
                    help="small fast preview: 480x270, antialias 0, no surface")
    ap.add_argument("--pymol-bin", default="pymol")
    ap.add_argument("--limit", type=int, default=0,
                    help="only render first N candidates (0=all)")
    ap.add_argument("--source-field", default="boltz_prediction_cif",
                    help="ranking candidate field to render (default: boltz_prediction_cif). "
                         "Use 'genie3_complex_pdb' or 'rfdiffusion_backbone_pdb' to render "
                         "raw designer output instead of the Boltz cofold.")
    ap.add_argument("--mode", default="complex", choices=["complex", "binder"],
                    help="complex: render target+binder cofold (default). "
                         "binder: render just the binder chain as a clean rainbow ribbon "
                         "(auto-detects smaller chain; works on CA-only PDBs).")
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    if not shutil.which(args.pymol_bin):
        print(f"ERROR: pymol binary not found at '{args.pymol_bin}'", file=sys.stderr)
        return 2
    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg not found (brew install ffmpeg)", file=sys.stderr)
        return 2

    if args.quick:
        antialias = 0; surface_quality = 0; ray_shadows = 0
        width, height = 480, 270
    else:
        antialias = 2; surface_quality = 1; ray_shadows = 1
        width, height = args.width, args.height

    hotspot_chain = "A"; hotspot_resnums: list[int] = []
    if args.hotspots_json and args.hotspots_json.is_file():
        h = json.loads(args.hotspots_json.read_text())
        hotspot_chain = h.get("chain", "A")
        hotspot_resnums = list(h.get("residues", []))

    ranking = json.loads(args.ranking.read_text())
    candidates = ranking.get("candidates", [])
    if args.limit > 0:
        candidates = candidates[: args.limit]

    summary: dict[str, Any] = {
        "label": args.label, "pymol_bin": args.pymol_bin,
        "frames": args.frames, "resolution": f"{width}x{height}",
        "antialias": antialias, "ray_shadows": ray_shadows,
        "hotspot_chain": hotspot_chain,
        "hotspot_count": len(hotspot_resnums),
        "results": [],
    }
    for c in candidates:
        cid = c["candidate_id"]
        cif_rel = c.get(args.source_field)
        if not cif_rel:
            summary["results"].append({"candidate_id": cid, "ok": False,
                                       "reason": f"no_{args.source_field}"})
            continue
        cif_path = (args.repo_root / cif_rel).resolve()
        if not cif_path.is_file():
            summary["results"].append({"candidate_id": cid, "ok": False,
                                       "reason": "source_missing",
                                       "field": args.source_field,
                                       "expected": str(cif_path)})
            continue

        hero_done = args.out / f"{cid}_hero.png"
        spin_done = args.out / f"{cid}_spin.mp4"
        pml_done = args.out / f"{cid}.pml"
        if hero_done.is_file() and hero_done.stat().st_size > 1024 \
                and spin_done.is_file() and spin_done.stat().st_size > 100_000 \
                and pml_done.is_file():
            print(f"  [{cid}] skip (hero+spin+pml already present)", file=sys.stderr)
            summary["results"].append({
                "candidate_id": cid, "ok": True, "skipped": True,
                "hero_png": str(hero_done.relative_to(args.repo_root)),
                "spin_mp4": str(spin_done.relative_to(args.repo_root)),
                "pml": str(pml_done.relative_to(args.repo_root)),
            })
            continue

        print(f"  [{cid}] rendering {cif_path.name} ...", file=sys.stderr)
        res = render_one(
            cid=cid, label=args.label, cif_path=cif_path, out_dir=args.out,
            hotspot_chain=hotspot_chain, hotspot_resnums=hotspot_resnums,
            frames=args.frames, width=width, height=height,
            antialias=antialias, surface_quality=surface_quality,
            ray_shadows=ray_shadows,
            pymol_bin=args.pymol_bin, mode=args.mode,
        )
        summary["results"].append(res)
        if res.get("ok"):
            print(f"  [{cid}] OK in {res['render_secs']}s", file=sys.stderr)
        else:
            print(f"  [{cid}] FAILED: {res.get('reason') or res.get('stderr_tail','')[:120]}",
                  file=sys.stderr)

    idx = args.out / f"pymol_render_index_{args.label}.json"
    idx.write_text(json.dumps(summary, indent=2) + "\n")
    n_ok = sum(1 for r in summary["results"] if r.get("ok"))
    print(json.dumps({"ok": True, "label": args.label,
                      "n_candidates": len(summary["results"]),
                      "n_rendered": n_ok}, indent=2))
    return 0 if n_ok else 1


if __name__ == "__main__":
    sys.exit(main())
