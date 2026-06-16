"""Smoke test: the export denoise step actually reduces noise.

This guards the Blender 4.x -> 5.x compositor API change (scene.node_tree +
Composite node -> scene.compositing_node_group + node-group output) that once
made _denoise_lightmaps silently no-op on 5.x. Exercises the REAL function.

Run: blender --background --python tests/smoketest_denoise.py
"""
import bpy, os, tempfile
import numpy as np


def result(ok, msg):
    print(("OK: " if ok else "FAIL: ") + msg)
    print("SMOKETEST_RESULT " + ("PASS" if ok else "FAIL"))


try:
    bpy.ops.preferences.addon_enable(module='thelightmapper')
    import thelightmapper.addon.utility.cycles.export as ex
except Exception as e:
    result(False, "could not load addon export module: %r" % e)
    raise SystemExit

W = H = 256

# Synthetic noisy lightmap: a smooth ramp + heavy grain, saved as HDR.
rng = np.random.default_rng(0)
xx = np.mgrid[0:H, 0:W][1]
lum = np.clip((0.3 + 0.5 * (xx / W)).astype(np.float32)
              + rng.normal(0, 0.25, (H, W)).astype(np.float32), 0, None)
rgba = np.ones((H, W, 4), np.float32)
rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = lum

savedir = tempfile.mkdtemp(prefix="tlm_dn_")
bake_base = "Probe_baked"
src = os.path.join(savedir, bake_base + ".hdr")

img = bpy.data.images.new("probe", W, H, alpha=True, float_buffer=True)
img.pixels.foreach_set(rgba.ravel())
img.filepath_raw = src
img.file_format = 'HDR'
img.save()
bpy.data.images.remove(img)


def noise_metric(path):
    im = bpy.data.images.load(path, check_existing=False)
    a = np.array(im.pixels[:], np.float32).reshape(H, W, 4)[..., 0]
    bpy.data.images.remove(im)
    lap = np.abs(4 * a[1:-1, 1:-1] - a[:-2, 1:-1] - a[2:, 1:-1]
                 - a[1:-1, :-2] - a[1:-1, 2:])
    return float(lap.mean())


before = noise_metric(src)
n = ex._denoise_lightmaps(bpy.context.scene, {"obj": ("id", bake_base, True)}, savedir)
after = noise_metric(src)

ok = (n == 1) and before > 0 and (after < before * 0.7)
result(ok, "denoised=%d  noise %.4f -> %.4f (%.0f%% reduction)"
       % (n, before, after, (1 - after / before) * 100 if before else 0))
