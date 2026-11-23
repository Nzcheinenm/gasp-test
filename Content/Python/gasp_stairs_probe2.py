# -*- coding: utf-8 -*-
"""Probe #2: verify stair step size from root motion + retarget API surface.

Run:  Python console -> import gasp_stairs_probe2
Writes Saved/StairsProbe2.txt
"""

import unreal
import os
import traceback

OUT = os.path.join(unreal.Paths.project_dir(), "Saved", "StairsProbe2.txt")
L = []


def w(*a):
    L.append(" ".join(str(x) for x in a))


def load(p):
    try:
        return unreal.EditorAssetLibrary.load_asset(p)
    except Exception as e:
        w("load %s <ERROR> %s" % (p, e))
        return None


def doc(label, fn):
    try:
        w("%s: %s" % (label, getattr(fn, "__doc__", None)))
    except Exception as e:
        w("%s <ERROR> %s" % (label, e))


w("=" * 70)
w("RETARGET API")
w("=" * 70)
for n in sorted(dir(unreal)):
    if any(k in n for k in ("IKRetarget", "IKRig", "Retarget")):
        w("unreal.%s" % n)
doc("duplicate_and_retarget",
    unreal.IKRetargetBatchOperation.duplicate_and_retarget)
doc("run_batch_retarget",
    unreal.IKRetargetBatchOperation.run_batch_retarget)

w("")
w("=" * 70)
w("CHOOSER / POSE SEARCH PYTHON API")
w("=" * 70)
for n in sorted(dir(unreal)):
    if any(k in n for k in ("Chooser", "PoseSearch")):
        w("unreal.%s" % n)

w("")
w("=" * 70)
w("ROOT MOTION / STEP SIZE")
w("=" * 70)
anim_path = ("/Game/StairsSet/Animations/Mannequin/RootMotion/Walk/"
             "A_Stairs_WalkFwd_Up_Loop.A_Stairs_WalkFwd_Up_Loop")
anim = load(anim_path)
if not anim:
    w("anim not found")
else:
    length = anim.get_play_length()
    w("length: %.4f" % length)
    dm = None
    try:
        dm = anim.data_model
        w("data_model: %s" % dm)
        w("data_model members: %s" % [m for m in dir(dm) if not m.startswith("_")])
    except Exception as e:
        w("data_model <ERROR> %s" % e)

    # Pose sampling
    doc("get_anim_pose_at_time", anim.get_anim_pose_at_time)
    doc("get_anim_pose_at_frame", anim.get_anim_pose_at_frame)
    w("AnimPoseExtensions members: %s"
      % [m for m in dir(unreal.AnimPoseExtensions) if not m.startswith("_")])

    sample = None
    try:
        sample = anim.get_anim_pose_at_time(0.0)
        w("pose class: %s" % sample.get_class().get_name())
        w("pose members: %s" % [m for m in dir(sample) if not m.startswith("_")])
    except Exception as e:
        w("pose sample <ERROR> %s" % e)

    if sample is not None:
        spaces = [n for n in dir(unreal) if "AnimPoseSpace" in n]
        w("space enums: %s" % spaces)

        def bone_pose(pose, name):
            for sname in ("WORLD", "COMPONENT_SPACE", "LOCAL"):
                try:
                    space = getattr(unreal.AnimPoseSpaces, sname)
                    return unreal.AnimPoseExtensions.get_bone_pose(pose, name, space)
                except Exception:
                    continue
            raise RuntimeError("no space enum worked")

        rows = []
        steps = 60
        for i in range(steps + 1):
            t = length * i / steps
            try:
                pose = anim.get_anim_pose_at_time(t)
                tr = bone_pose(pose, "root")
                loc = tr.translation
                rows.append((t, loc.x, loc.y, loc.z))
            except Exception as e:
                w("sample t=%.3f <ERROR> %s" % (t, e))
                break
        if rows:
            w("root samples (t, x, y, z):")
            for r in rows:
                w("  %.3f  %8.3f %8.3f %8.3f" % r)
            x0, y0, z0 = rows[0][1], rows[0][2], rows[0][3]
            xn, yn, zn = rows[-1][1], rows[-1][2], rows[-1][3]
            w("total delta: dx=%.3f dy=%.3f dz=%.3f" % (xn - x0, yn - y0, zn - z0))
            w("path delta: dx=%.3f dy=%.3f dz=%.3f"
              % (abs(xn - x0), abs(yn - y0), abs(zn - z0)))

    # Same for the root-motion jog loop
    w("")
    anim2 = load("/Game/StairsSet/Animations/Mannequin/RootMotion/Jog/"
                 "A_Stairs_JogFwd_Up_Loop.A_Stairs_JogFwd_Up_Loop")
    if anim2:
        w("JOG loop length: %.4f" % anim2.get_play_length())
    w("")
    w("=" * 70)
    w("ABP CDO VARIABLES")
    w("=" * 70)
    for bp_path in ("/Game/Blueprints/ABP_SandboxCharacter.ABP_SandboxCharacter",
                    "/Game/Blueprints/CBP_SandboxCharacter.CBP_SandboxCharacter"):
        try:
            bp = load(bp_path)
            if not bp:
                w("%s NOT FOUND" % bp_path)
                continue
            w("")
            w("### %s (%s)" % (bp_path, bp.get_class().get_name()))
            for prop in ("generated_class", "skeleton_generated_class",
                         "parent_class", "blueprint_type"):
                try:
                    w("  %s: %s" % (prop, bp.get_editor_property(prop)))
                except Exception as e:
                    w("  %s <ERROR> %s" % (prop, e))
            cls = None
            for prop in ("generated_class", "skeleton_generated_class"):
                try:
                    cls = bp.get_editor_property(prop)
                    if cls:
                        break
                except Exception:
                    pass
            if cls:
                cdo = unreal.get_default_object(cls)
                scal = [n for n in dir(cdo) if not n.startswith("_")]
                w("  CDO members: %s" % scal)
        except Exception:
            w("%s FAILED\n%s" % (bp_path, traceback.format_exc()))

try:
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    unreal.log("[StairsProbe2] written to %s" % OUT)
except Exception:
    unreal.log_error("[StairsProbe2] write failed: %s" % traceback.format_exc())
