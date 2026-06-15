import bpy, traceback

def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.preferences.addon_enable(module='thelightmapper')

    # good: cube with material
    bpy.ops.mesh.primitive_cube_add()
    good = bpy.context.active_object
    good.name = "GoodCube"
    m = bpy.data.materials.new("m"); m.use_nodes = True
    good.data.materials.append(m)

    # bad: cube with no material
    bpy.ops.mesh.primitive_cube_add()
    nomat = bpy.context.active_object
    nomat.name = "NoMatCube"
    nomat.data.materials.clear()

    # bad: zero-poly mesh
    bpy.ops.object.add(type='MESH')
    zero = bpy.context.active_object
    zero.name = "ZeroPolyMesh"

    bpy.context.scene.TLM_SceneProperties.tlm_utility_set = "Scene"
    bpy.context.scene.TLM_SceneProperties.tlm_mesh_lightmap_unwrap_mode = "SmartProject"
    print("ENABLE_RESULT:", bpy.ops.tlm.enable_set())

    ok = True
    checks = {
        "GoodCube": True,    # should be enabled
        "NoMatCube": False,  # should be skipped (disabled)
        "ZeroPolyMesh": False,
    }
    for name, expected in checks.items():
        actual = bpy.data.objects[name].TLM_ObjectProperties.tlm_mesh_lightmap_use
        if actual == expected:
            print("OK: %s enabled=%s" % (name, actual))
        else:
            print("FAIL: %s enabled=%s, expected %s" % (name, actual, expected)); ok = False

    print("SMOKETEST_RESULT:", "PASS" if ok else "FAIL")

try:
    main()
except Exception:
    traceback.print_exc()
    print("SMOKETEST_RESULT: EXCEPTION")
