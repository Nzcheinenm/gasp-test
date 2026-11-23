# -*- coding: utf-8 -*-
"""Final rollout for the stairs integration.

Run from the editor (or via agent_bridge cmd.py):
    exec(open(r"<project>/Content/Python/gasp_stairs_rollout.py", encoding="utf-8").read())

What it does
------------
1. For every retargeted clip (RootMotion + Slot2) forces a compressed-data rebuild
   with the project's ACL compression settings:
   - set ACL bone/curve compression settings,
   - invalidate by removing a bone track and re-adding it with the same keys,
   - save.
2. Points CBP_SandboxCharacter.StairsAnimWalkUp/RunUp at the in-place clips.
3. Restores the UpdateStairsAnim call in CalculateMaxSpeed (it is bypassed
   during debugging).
4. Compiles and saves the character blueprint.
"""

import unreal

EL = unreal.EditorAssetLibrary
AL = unreal.AnimationLibrary
BEL = unreal.BlueprintEditorLibrary
GPE = unreal.BlueprintGraphEditor
PINS = unreal.BlueprintGraphPinLibrary
OPTS = unreal.AnimPoseEvaluationOptions()

ACL = EL.load_asset("/ACLPlugin/ACLAnimBoneCompressionSettings.ACLAnimBoneCompressionSettings")
CURVE = EL.load_asset("/Game/Misc/SandboxAnimCurveCompressionSettings.SandboxAnimCurveCompressionSettings")


def rebuild(anim):
    """Force compressed data rebuild for one AnimSequence. Returns bool."""
    names = [str(n) for n in AL.get_animation_track_names(anim)]
    if not names:
        return False
    bone = "attach" if "attach" in names else names[-1]
    nkeys = AL.get_num_keys(anim)
    frames = [anim.get_anim_pose_at_frame(i, OPTS) for i in range(nkeys)]
    V, Q = unreal.Vector, unreal.Quat
    pos, rot, scl = [], [], []
    for p in frames:
        tr = unreal.AnimPoseExtensions.get_bone_pose(p, bone, unreal.AnimPoseSpaces.LOCAL)
        pos.append(V(tr.translation.x, tr.translation.y, tr.translation.z))
        q = tr.rotation
        rot.append(Q(q.x, q.y, q.z, q.w))
        scl.append(V(tr.scale3d.x, tr.scale3d.y, tr.scale3d.z))
    c = anim.controller
    if ACL:
        AL.set_bone_compression_settings(anim, ACL)
    if CURVE:
        AL.set_curve_compression_settings(anim, CURVE)
    c.remove_bone_track(unreal.Name(bone), True)
    c.add_bone_track(unreal.Name(bone), True)
    c.set_bone_track_keys(unreal.Name(bone), pos, rot, scl, True)
    anim.modify(True)
    return EL.save_loaded_asset(anim)


def rebuild_all(roots):
    total = 0
    for root in roots:
        for path in EL.list_assets(root, recursive=True, include_folder=False):
            a = EL.load_asset(path)
            if a and a.get_class().get_name() == "AnimSequence":
                ok = rebuild(a)
                total += 1 if ok else 0
                print("rebuilt %-45s %s" % (a.get_name(), ok))
    print("rebuilt total:", total)


def rewiring_and_defaults():
    bp = EL.load_asset("/Game/Blueprints/CBP_SandboxCharacter.CBP_SandboxCharacter")
    BEL.compile_blueprint(bp)
    cdo = unreal.get_default_object(
        unreal.load_class(None, "/Game/Blueprints/CBP_SandboxCharacter.CBP_SandboxCharacter_C"))
    walk = EL.load_asset("/Game/StairsSet/Retargeted/Slot2/A_INP_Stairs_WalkFwd_Up_Loop.A_INP_Stairs_WalkFwd_Up_Loop")
    run = EL.load_asset("/Game/StairsSet/Retargeted/Slot2/A_INP_Stairs_JogFwd_Up_Loop.A_INP_Stairs_JogFwd_Up_Loop")
    cdo.set_editor_property("StairsAnimWalkUp", walk)
    cdo.set_editor_property("StairsAnimRunUp", run)
    print("defaults:", cdo.get_editor_property("StairsAnimWalkUp"), cdo.get_editor_property("StairsAnimRunUp"))

    ed = GPE.get_graph_editor_by_name(bp, "CalculateMaxSpeed")

    def in_pin(node, name):
        for p in BEL.list_input_pins(node):
            if str(PINS.get_pin_name(p)).lower() == name.lower():
                return p
        return None

    def out_pin(node, name):
        for p in BEL.list_output_pins(node):
            if str(PINS.get_pin_name(p)).lower() == name.lower():
                return p
        return None

    nodes = ed.list_all_nodes()
    call = next((n for n in nodes if BEL.get_node_title(n) == "UpdateStairsAnim"), None)
    if call is None:
        print("call node missing - nothing to restore")
        return
    has_prev = [c for p in BEL.list_input_pins(call) if str(PINS.get_pin_name(p)) == "execute"
                for c in PINS.list_connected_pins(p)]
    if has_prev:
        print("call already wired")
    else:
        trc = [n for n in nodes if BEL.get_node_title(n) == "Line Trace By Channel"]
        trc2 = next((n for n in trc if any(BEL.get_node_title(PINS.get_owning_node(c)) == "Line Trace By Channel"
                                           for c in PINS.list_connected_pins(in_pin(n, "execute")))), None)
        trc1 = next((n for n in trc if n is not trc2), None)
        gt = next((n for n in nodes if BEL.get_node_title(n) == "float > float"
                   and PINS.get_pin_value(in_pin(n, "B")) == "400.0"), None)
        outer = next((n for n in nodes if BEL.get_node_title(n) == "SelectFloat"
                      and any(BEL.get_node_title(PINS.get_owning_node(c)) == "OR Boolean"
                              for c in PINS.list_connected_pins(in_pin(n, "bPickA")))), None)
        # speed pin may be named Speed1
        speed_pin = in_pin(call, "Speed1") or in_pin(call, "Speed")
        if trc1 and call:
            PINS.try_create_connection(out_pin(trc1, "ReturnValue"), in_pin(call, "bAscending"))
        if gt:
            PINS.try_create_connection(out_pin(gt, "ReturnValue"), in_pin(call, "bRun"))
        if outer and speed_pin:
            PINS.try_create_connection(out_pin(outer, "ReturnValue"), speed_pin)
        # find the node the call used to feed: originally Set StrafeSpeedMap
        nxt = next((n for n in nodes if BEL.get_node_title(n) == "Set StrafeSpeedMap"), None)
        if trc2:
            PINS.try_create_connection(out_pin(trc2, "then"), in_pin(call, "execute"))
        if nxt:
            PINS.try_create_connection(out_pin(call, "then"), in_pin(nxt, "execute"))
        print("call restored")

    print("compile:", BEL.compile_blueprint(bp))
    print("errors:", [BEL.get_node_title(n) for n in ed.list_nodes_with_errors()])
    print("save:", EL.save_loaded_asset(bp))


if __name__ == "__main__" or True:
    rebuild_all(["/Game/StairsSet/Retargeted/RootMotion", "/Game/StairsSet/Retargeted/Slot2"])
    rewiring_and_defaults()
