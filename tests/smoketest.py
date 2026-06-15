import bpy, os, tempfile, json, traceback

def main():
    work = tempfile.mkdtemp(prefix="tlm_smoke_")
    blend = os.path.join(work, "scene.blend")

    # Clean scene first (resets prefs), then enable the addon
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.preferences.addon_enable(module='thelightmapper')

    # Geometry: a ground plane + a cube + a sun
    bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
    plane = bpy.context.active_object
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
    cube = bpy.context.active_object
    bpy.ops.object.light_add(type='SUN', location=(4, 4, 8))

    # Give them materials
    for ob in (plane, cube):
        mat = bpy.data.materials.new(ob.name + "_mat")
        mat.use_nodes = True
        ob.data.materials.append(mat)
        op = ob.TLM_ObjectProperties
        op.tlm_mesh_lightmap_use = True
        op.tlm_mesh_lightmap_unwrap_mode = "SmartProject"
        op.tlm_mesh_lightmap_resolution = "64"

    # Robustness: an object with NO material, and a zero-poly object. The batch
    # "enable for set" sweeps these in; export must not crash on them.
    bpy.ops.mesh.primitive_cube_add(size=1, location=(3, 0, 1))
    nomat = bpy.context.active_object
    nomat.name = "NoMat"
    nomat.data.materials.clear()
    bpy.ops.object.add(type='MESH', location=(0, 3, 0))  # empty mesh = zero polys
    zero = bpy.context.active_object
    zero.name = "ZeroPoly"
    for ob in (nomat, zero):
        op = ob.TLM_ObjectProperties
        op.tlm_mesh_lightmap_use = True
        op.tlm_mesh_lightmap_unwrap_mode = "SmartProject"
        op.tlm_mesh_lightmap_resolution = "64"

    # Engine settings: cheap + single pass
    eng = bpy.context.scene.TLM_EngineProperties
    eng.tlm_lighting_mode = "combined"
    eng.tlm_quality = "0"
    eng.tlm_resolution_scale = "1"
    eng.tlm_setting_supersample = "2x"
    eng.tlm_mode = "CPU"

    sp = bpy.context.scene.TLM_SceneProperties
    glb = os.path.join(work, "out", "world.glb")
    sp.tlm_export_glb_path = glb
    sp.tlm_export_embed_occlusion = True

    # Must be saved (lightmaps are written relative to the .blend)
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    scenes_before = len(bpy.data.scenes)
    result = bpy.ops.tlm.export_glb()
    print("OPERATOR_RESULT:", result)

    # ---- assertions ----
    manifest_path = os.path.splitext(glb)[0] + ".lightmaps.json"
    out_dir = os.path.dirname(glb)
    ok = True

    if not os.path.isfile(glb):
        print("FAIL: no GLB at", glb); ok = False
    else:
        print("OK: GLB", os.path.getsize(glb), "bytes")

    if not os.path.isfile(manifest_path):
        print("FAIL: no manifest"); ok = False
    else:
        with open(manifest_path) as f:
            man = json.load(f)
        print("OK: manifest:", json.dumps(man))
        for ident, entry in man["lightmaps"].items():
            exr = os.path.join(out_dir, entry["file"])
            if os.path.isfile(exr):
                print("OK: sidecar", entry["file"], os.path.getsize(exr), "bytes")
            else:
                print("FAIL: missing sidecar", exr); ok = False

        # Ineligible objects must be skipped (not fabricated), not in manifest
        for bad in ("NoMat", "ZeroPoly"):
            if bad in man["lightmaps"]:
                print("FAIL: ineligible '%s' was baked instead of skipped" % bad); ok = False
            else:
                print("OK: '%s' correctly skipped" % bad)

    # nondestructive: temp scene gone, original scene intact, originals untouched
    if len(bpy.data.scenes) != scenes_before:
        print("FAIL: scene count changed", scenes_before, "->", len(bpy.data.scenes)); ok = False
    else:
        print("OK: scene count stable at", scenes_before)

    if any(s.name == "__TLM_Export_Temp" for s in bpy.data.scenes):
        print("FAIL: temp scene left behind"); ok = False
    else:
        print("OK: temp scene cleaned up")

    # original cube material must NOT have a TLM_Lightmap node injected
    leaked = False
    for ob in (plane, cube):
        for slot in ob.material_slots:
            if slot.material and slot.material.node_tree and slot.material.node_tree.nodes.get("TLM_Lightmap"):
                leaked = True
    if leaked:
        print("FAIL: original materials were modified (TLM_Lightmap leaked)"); ok = False
    else:
        print("OK: original materials untouched")

    print("SMOKETEST_RESULT:", "PASS" if ok else "FAIL")

try:
    main()
except Exception:
    traceback.print_exc()
    print("SMOKETEST_RESULT: EXCEPTION")
