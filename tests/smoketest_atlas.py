import bpy, os, tempfile, json, traceback

def main():
    work = tempfile.mkdtemp(prefix="tlm_atlas_")
    blend = os.path.join(work, "scene.blend")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.preferences.addon_enable(module='thelightmapper')

    scene = bpy.context.scene

    # Two cubes sharing one atlas + a sun
    bpy.ops.mesh.primitive_cube_add(size=2, location=(-2, 0, 1))
    a = bpy.context.active_object
    bpy.ops.mesh.primitive_cube_add(size=2, location=(2, 0, 1))
    b = bpy.context.active_object
    bpy.ops.object.light_add(type='SUN', location=(4, 4, 8))

    # Register an atlas group
    atlas = scene.TLM_AtlasList.add()
    atlas.name = "AtlasA"
    atlas.tlm_atlas_lightmap_resolution = "128"
    atlas.tlm_atlas_lightmap_unwrap_mode = "SmartProject"

    for ob in (a, b):
        mat = bpy.data.materials.new(ob.name + "_mat")
        mat.use_nodes = True
        ob.data.materials.append(mat)
        op = ob.TLM_ObjectProperties
        op.tlm_mesh_lightmap_use = True
        op.tlm_mesh_lightmap_unwrap_mode = "AtlasGroupA"
        op.tlm_atlas_pointer = "AtlasA"

    eng = scene.TLM_EngineProperties
    eng.tlm_lighting_mode = "combined"
    eng.tlm_quality = "0"
    eng.tlm_resolution_scale = "1"
    eng.tlm_setting_supersample = "2x"
    eng.tlm_mode = "CPU"

    sp = scene.TLM_SceneProperties
    glb = os.path.join(work, "out", "world.glb")
    sp.tlm_export_glb_path = glb

    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("OPERATOR_RESULT:", bpy.ops.tlm.export_glb())

    out_dir = os.path.dirname(glb)
    manifest_path = os.path.splitext(glb)[0] + ".lightmaps.json"
    ok = True

    with open(manifest_path) as f:
        man = json.load(f)
    print("manifest:", json.dumps(man["lightmaps"]))

    lm = man["lightmaps"]
    if list(lm.keys()) == ["AtlasA"] and lm["AtlasA"]["atlas"] is True:
        print("OK: single shared atlas entry")
    else:
        print("FAIL: expected one shared 'AtlasA' atlas entry"); ok = False

    exrs = [f for f in os.listdir(out_dir) if f.endswith(".exr")]
    if exrs == ["AtlasA_lightmap.exr"]:
        print("OK: exactly one shared sidecar:", exrs)
    else:
        print("FAIL: expected one AtlasA_lightmap.exr, got", exrs); ok = False

    if os.path.isfile(glb):
        print("OK: GLB", os.path.getsize(glb), "bytes")
    else:
        print("FAIL: no GLB"); ok = False

    print("SMOKETEST_RESULT:", "PASS" if ok else "FAIL")

try:
    main()
except Exception:
    traceback.print_exc()
    print("SMOKETEST_RESULT: EXCEPTION")
