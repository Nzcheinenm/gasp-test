# -*- coding: utf-8 -*-
"""Read-only inspection for the StairsSet integration.

Run inside Unreal Editor:
    Python console:  import gasp_stairs_inspect
    or Cmd console:  py "C:/Users/user/Documents/Unreal Projects/GameAnimationSample/Content/Python/gasp_stairs_inspect.py"

Writes a report to Saved/StairsInspect.txt. Changes nothing except
temporarily opening the StairsSet Overview map, then restoring the level.
"""

import unreal
import os
import re
import traceback

OUT = os.path.join(unreal.Paths.project_dir(), "Saved", "StairsInspect.txt")
L = []


def w(*args):
    L.append(" ".join(str(a) for a in args))


def sect(title):
    w("")
    w("=" * 70)
    w(title)
    w("=" * 70)


def safe(label, fn):
    try:
        v = fn()
        w("%s: %s" % (label, v))
        return v
    except Exception as e:
        w("%s: <ERROR> %s" % (label, e))
        return None


def sect_safe(title, fn):
    try:
        fn()
    except Exception:
        w("%s FAILED\n%s" % (title, traceback.format_exc()))


def load(path):
    try:
        return unreal.EditorAssetLibrary.load_asset(path)
    except Exception as e:
        w("load %s <ERROR> %s" % (path, e))
        return None


def _candidates(name):
    out = [name, name[0].upper() + name[1:]]
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    out.append(snake)
    out.append("".join(p.capitalize() for p in snake.split("_")))
    return list(dict.fromkeys(out))


def gp(obj, name, default=None):
    """get_editor_property that tolerates naming styles."""
    for n in _candidates(name):
        try:
            return obj.get_editor_property(n)
        except Exception:
            pass
    return default


def scalar_props(obj, keys=(), limit=60):
    out = []
    for n in sorted(dir(obj)):
        if n.startswith("_"):
            continue
        try:
            v = getattr(obj, n)
        except Exception:
            continue
        if not isinstance(v, (bool, int, float, str)):
            continue
        if keys and not any(k.lower() in n.lower() for k in keys):
            continue
        out.append("%s=%r" % (n, v))
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- environment
sect("ENV")
safe("project dir", lambda: unreal.Paths.project_dir())
safe("engine version", lambda: unreal.SystemLibrary.get_engine_version())
safe("has IKRetargetBatchOperation", lambda: hasattr(unreal, "IKRetargetBatchOperation"))
if hasattr(unreal, "IKRetargetBatchOperation"):
    safe("IKRetargetBatchOperation members",
         lambda: [m for m in dir(unreal.IKRetargetBatchOperation) if not m.startswith("_")])

# ------------------------------------------------------------------ skeletons
sect("SKELETONS / BONES")


def skeleton_bones(asset_path, label):
    w("")
    w("### %s (%s)" % (label, asset_path))
    asset = load(asset_path)
    if not asset:
        w("NOT FOUND")
        return set()
    safe("class", lambda: asset.get_class().get_name())
    sk = gp(asset, "skeleton")
    if sk:
        w("skeleton: %s" % sk.get_path_name())
    names = set()
    for getter in ("get_bone_names", "get_reference_skeleton"):
        try:
            v = getattr(sk or asset, getter)()
            w("%s(): %s" % (getter, str(v)[:3000]))
        except Exception:
            pass
    try:
        ref = (sk or asset).get_editor_property("reference_skeleton")
        w("reference_skeleton: %s" % ref)
    except Exception:
        pass
    # fallback: property dump
    for prop in ("bone_tree", "bone_names", "skeleton"):
        try:
            v = (sk or asset).get_editor_property(prop)
            if isinstance(v, (list, tuple, set)):
                names = set(str(x) for x in v)
                w("%s -> %d entries" % (prop, len(names)))
                break
        except Exception:
            pass
    if not names:
        w("bone enumeration not exposed; dir(): %s" % [m for m in dir(sk or asset) if "bone" in m.lower()])
    return names


a = skeleton_bones("/Game/Characters/UEFN_Mannequin/Meshes/SK_UEFN_Mannequin.SK_UEFN_Mannequin", "UEFN")
b = skeleton_bones("/Game/StairsSet/Demo/Mannequins/Meshes/SK_Mannequin.SK_Mannequin", "DEMO")
if a and b:
    w("")
    w("only in DEMO: %s" % sorted(b - a))
    w("only in UEFN: %s" % sorted(a - b))

# ---------------------------------------------------------------- demo level
sect_safe("DEMO MAP / STAIR BUILDER", lambda: None)


def dump_demo_map():
    les = None
    try:
        les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    except Exception as e:
        w("LevelEditorSubsystem <ERROR> %s" % e)
        return

    prev_level = None
    try:
        prev_level = les.get_current_level().get_path_name()
        w("previous level: %s" % prev_level)
    except Exception as e:
        w("get_current_level <ERROR> %s" % e)

    try:
        ok = les.load_level("/Game/StairsSet/Maps/Overview")
        w("load Overview: %s" % ok)
        if not ok:
            return
        aas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for act in aas.get_all_level_actors():
            try:
                cls = act.get_class().get_name()
            except Exception:
                cls = "?"
            try:
                label = act.get_actor_label()
            except Exception:
                label = "?"
            w("")
            w("--- %s | %s" % (label, cls))
            try:
                w("    loc: %s" % act.get_actor_location())
                w("    scale: %s" % act.get_actor_scale3d())
            except Exception:
                pass
            interesting = scalar_props(
                act, ("rise", "step", "depth", "width", "count", "num", "height", "tread"))
            if interesting:
                w("    " + " | ".join(interesting))
            try:
                comps = act.get_components_by_class(unreal.StaticMeshComponent)
            except Exception:
                comps = []
            for c in comps:
                try:
                    m = c.get_editor_property("static_mesh")
                    if m:
                        w("    mesh: %s" % m.get_path_name())
                        w("    bounds: %s" % m.get_bounds())
                except Exception as e:
                    w("    mesh <ERROR> %s" % e)
    finally:
        if prev_level:
            try:
                les.load_level(prev_level)
                w("restored level: %s" % prev_level)
            except Exception as e:
                w("restore level <ERROR> %s" % e)


dump_demo_map()

# ------------------------------------------------------------- stairs assets
sect("STAIRS ANIMATIONS")
for p in [
    "/Game/StairsSet/Animations/Mannequin/InPlace/Walk/A_INP_Stairs_WalkFwd_Up_Loop.A_INP_Stairs_WalkFwd_Up_Loop",
    "/Game/StairsSet/Animations/Mannequin/RootMotion/Walk/A_Stairs_WalkFwd_Up_Loop.A_Stairs_WalkFwd_Up_Loop",
    "/Game/StairsSet/Animations/Mannequin/InPlace/Idle/A_INP_Idle.A_INP_Idle",
]:
    w("")
    w("### " + p)
    anim = load(p)
    if not anim:
        w("NOT FOUND")
        continue
    safe("class", lambda: anim.get_class().get_name())
    safe("skeleton", lambda: gp(anim, "skeleton").get_path_name())
    safe("length", lambda: gp(anim, "sequence_length"))
    safe("enable_root_motion", lambda: gp(anim, "enable_root_motion"))
    safe("root_motion_root_lock", lambda: gp(anim, "root_motion_root_lock"))
    try:
        notifies = gp(anim, "notifies")
        w("notifies(%d): %s" % (len(notifies), [str(n) for n in notifies]))
    except Exception as e:
        w("notifies <ERROR> %s" % e)
    try:
        dm = anim.get_data_model()
        w("data_model: %s" % dm)
        safe("  num_keys", lambda: dm.get_num_keys())
        safe("  curve_names", lambda: [str(c) for c in dm.get_curve_names()])
        safe("  bone_tracks", lambda: [str(bn) for bn in dm.get_bone_track_names()][:8])
    except Exception as e:
        w("data model <ERROR> %s" % e)
    w("members: %s" % [m for m in dir(anim) if not m.startswith("_")][:150])

# ------------------------------------------------------------- pose search db
sect("POSE SEARCH DATABASE / CHOOSER")
for p in [
    "/Game/Characters/UEFN_Mannequin/Animations/MotionMatchingData/Databases/Dense/PSD_Dense_Stand_Walk_Loops.PSD_Dense_Stand_Walk_Loops",
    "/Game/Characters/UEFN_Mannequin/Animations/MotionMatchingData/CHT_PoseSearchDatabases_Dense.CHT_PoseSearchDatabases_Dense",
]:
    w("")
    w("### " + p)
    asset = load(p)
    if not asset:
        w("NOT FOUND")
        continue
    safe("class", lambda: asset.get_class().get_name())
    w("members: %s" % [m for m in dir(asset) if not m.startswith("_")][:150])
    w("scalars: %s" % scalar_props(asset))
    for prop in ("schema", "database_entries", "number_of_entries", "sample_rate"):
        safe(prop, lambda: str(gp(asset, prop))[:2000])

# ---------------------------------------------------------------- ABP / variables
sect("ABP SANDBOX CHARACTER")
try:
    cls = unreal.load_class(None, "/Game/Blueprints/ABP_SandboxCharacter.ABP_SandboxCharacter_C")
    if cls:
        w("members: %s" % [n for n in dir(cls) if not n.startswith("_")])
    else:
        w("class not found")
except Exception as e:
    w("<ERROR> %s" % e)

# ---------------------------------------------------------------------- write
try:
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    unreal.log("[StairsInspect] report written to %s" % OUT)
except Exception:
    unreal.log_error("[StairsInspect] write failed: %s" % traceback.format_exc())

unreal.log("[StairsInspect] done")
