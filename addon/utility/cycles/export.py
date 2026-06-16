"""Nondestructive GLB export pipeline.

This is the "Needle-style" export path: instead of editing the live scene in
place (and relying on the fragile material backup/restore machinery in
``cache.py``), it makes a throwaway full copy of the scene, does all of its
unwrapping / baking / material edits there, exports, and deletes the copy.

Pipeline (matches the agreed steps 1, 2, 5, 6):
    1. Full-copy the scene (the originals are never touched).
    2. On the copy: lightmap-unwrap each target, bake lighting with Cycles
       (reusing ``lightmap.bake``), including shared pre-pack atlas groups.
    5. Write per-object/atlas HDR lightmap sidecars (float EXR) + a manifest,
       and export a .glb whose lightmap UV travels as TEXCOORD_1 (carried via
       the glTF occlusion slot).
    6. Delete the copy and purge the orphaned datablocks.

Material *merging* and albedo/roughness baking (steps 3 and 4) are deliberately
out of scope here and will be layered on later.
"""

import bpy
import os
import re
import json
import math
from time import time

from . import lightmap, prepare
from .. import console

TEMP_SCENE_NAME = "__TLM_Export_Temp"
LM_UV = "UVMap_Lightmap"
GLTF_GROUP = "glTF Material Output"

# Lighting modes that bake in a single Cycles pass. The two-pass *+AO modes use
# global driver state and a recursive build; they are not supported by this
# self-contained path yet.
SINGLE_PASS = {"combined", "combinedneutral", "indirect", "ao", "complete"}

_SUFFIX_RE = re.compile(r"^(.*)\.\d{3}$")


def _log(msg):
    """Coarse progress logging (always on) so the long, UI-blocking export is
    legible in the System Console. flush=True so a line printed right before a
    long blocking op (pack/bake) shows up immediately instead of being buffered
    until the op returns."""
    print("[TLM Export] " + msg, flush=True)


def _prune_unexported(temp, vl):
    """Strip from the temp scene everything that shouldn't ship, for ANY object
    type (mesh / empty / light / curve / ...), so it never reaches the GLB:

      * objects in a view-layer-excluded collection (the unchecked box in the
        outliner) -- these are in ``scene.objects`` but not ``view_layer.objects``;
      * objects disabled for render (the object's camera icon, ``hide_render``);
      * objects in a collection disabled for render (collection ``hide_render``).

    Runs before targets are gathered, so a render-disabled mesh isn't even baked.
    Safe to remove outright: temp is a FULL_COPY, so these are throwaway dupes.
    Returns the removed objects (for logging)."""
    vl_objs = set(vl.objects)
    to_remove = []
    for obj in list(temp.objects):
        drop = obj not in vl_objs or obj.hide_render
        if not drop:
            for coll in obj.users_collection:
                if coll.hide_render:
                    drop = True
                    break
        if drop:
            to_remove.append(obj)
    for obj in to_remove:
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception as e:
            _log("could not prune '%s': %s" % (obj.name, e))
    return to_remove


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def export_glb(operator, context):
    console.ensure_console_visible()   # pop the System Console so the long bake is visible
    console.disable_quick_edit()       # ...and a stray click in it can't freeze the bake
    scene0 = context.scene
    eng = scene0.TLM_EngineProperties
    sp = scene0.TLM_SceneProperties

    if not bpy.data.is_saved:
        operator.report({'ERROR'}, "Save the .blend before exporting.")
        return {'CANCELLED'}

    # The scene default is the manifest's top-level mode; individual atlas
    # groups may override it (effective_lighting_mode). Validate every mode that
    # will actually be baked -- the self-contained export path only supports
    # single-pass modes, whether they come from the scene or an atlas.
    lighting_mode = eng.tlm_lighting_mode
    used_modes = {
        lightmap.effective_lighting_mode(scene0, o)
        for o in scene0.objects
        if o.type == 'MESH' and o.TLM_ObjectProperties.tlm_mesh_lightmap_use
    }
    bad = sorted(used_modes - SINGLE_PASS)
    if bad:
        operator.report(
            {'ERROR'},
            "Export supports single-pass lighting modes (Combined / Indirect / "
            "AO / Complete). In use but multi-pass: %s. Fix the scene Lighting "
            "Mode or the offending atlas group(s)." % ", ".join(bad))
        return {'CANCELLED'}

    glb_path = bpy.path.abspath(sp.tlm_export_glb_path)
    if not glb_path.lower().endswith(".glb"):
        glb_path = os.path.join(glb_path, "world.glb")
    out_dir = os.path.dirname(glb_path)
    savedir = os.path.join(os.path.dirname(bpy.data.filepath),
                           eng.tlm_lightmap_savedir)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(savedir, exist_ok=True)

    # 1) Nondestructive duplicate -------------------------------------------
    t_start = time()
    _log("Duplicating scene (full copy)...")
    before = set(bpy.data.scenes)
    bpy.ops.scene.new(type='FULL_COPY')
    new = set(bpy.data.scenes) - before
    temp = new.pop() if new else _active_scene(context)
    temp.name = TEMP_SCENE_NAME
    vl = temp.view_layers[0]
    _log("Scene duplicated in %.1fs" % (time() - t_start))

    # Changing window.scene inside a running operator does NOT refresh
    # bpy.context.view_layer, so the copies aren't reachable through the stale
    # context. Override scene + view_layer explicitly (and crucially WITHOUT a
    # window -- passing a window makes Blender re-derive the view layer from it,
    # shadowing our override and making selection fail intermittently). On top
    # of that, every select_set below is given `vl` directly so selection never
    # depends on the ambient context at all.
    try:
        with bpy.context.temp_override(scene=temp, view_layer=vl):
            pruned = _prune_unexported(temp, vl)
            if pruned:
                _log("Excluded %d non-rendered / unchecked-collection object(s) from export"
                     % len(pruned))

            targets = [o for o in vl.objects
                       if o.type == 'MESH'
                       and o.TLM_ObjectProperties.tlm_mesh_lightmap_use]
            if not targets:
                operator.report({'ERROR'}, "No lightmap-enabled objects are in the active view layer.")
                return {'CANCELLED'}

            targets, skipped = _prepare_targets(targets, vl)
            if not targets:
                operator.report({'ERROR'}, "No bakeable lightmap objects (all skipped: no material/geometry).")
                return {'CANCELLED'}

            # 2) Unwrap + bake on the copy ----------------------------------
            prepare.set_settings()                     # reuse Cycles config
            _log("Unwrapping + packing %d target(s)..." % len(targets))
            t0 = time()
            lm_for_obj = _setup_targets(temp, targets, savedir, vl)
            _log("Unwrap + pack complete in %.1fs - starting bake" % (time() - t0))

            bpy.app.driver_namespace["tlm_start_time"] = time()
            t0 = time()
            lightmap.bake()                            # reuse the real bake
            _log("Bake complete in %.1fs" % (time() - t0))

            # 4b) Denoise baked lightmaps with Blender's bundled compositor
            #     denoiser (OpenImageDenoise). Best-effort: a denoise failure
            #     must never sink an otherwise-good bake.
            if sp.tlm_denoise_use:
                t0 = time()
                try:
                    n = _denoise_lightmaps(temp, lm_for_obj, savedir)
                    _log("Denoised %d lightmap(s) in %.1fs" % (n, time() - t0))
                except Exception as e:
                    _log("Denoise skipped (%s: %s)" % (type(e).__name__, e))

            # 5) Sidecars + UV-carrying occlusion + manifest ----------------
            _log("Writing lightmap sidecars + exporting GLB...")
            t0 = time()
            group = (_ensure_gltf_group()
                     if temp.TLM_SceneProperties.tlm_export_embed_occlusion
                     else None)
            manifest = _finalize(temp, targets, lm_for_obj, savedir, out_dir, group)
            _export_gltf(glb_path)
            _write_manifest(out_dir, glb_path, manifest, lighting_mode)
            _log("Export written in %.1fs (total %.1fs)"
                 % (time() - t0, time() - t_start))

        if skipped:
            preview = ", ".join("%s (%s)" % (n, r) for n, r in skipped[:8])
            if len(skipped) > 8:
                preview += ", ..."
            operator.report(
                {'WARNING'},
                "Exported %d object(s) -> %s | skipped %d not eligible: %s"
                % (len(targets), glb_path, len(skipped), preview))
            print("TLM export - skipped: " + preview)
        else:
            operator.report(
                {'INFO'},
                "Exported %d object(s) -> %s" % (len(targets), glb_path))
        return {'FINISHED'}

    except Exception as e:
        print("TLM export error: %s at line %s" %
              (type(e).__name__, getattr(e.__traceback__, "tb_lineno", "?")))
        operator.report({'ERROR'}, "Export failed: %s" % e)
        return {'CANCELLED'}

    finally:
        # 6) Cleanup --------------------------------------------------------
        _cleanup(scene0, temp)


# --------------------------------------------------------------------------- #
# 1) Duplicate helpers
# --------------------------------------------------------------------------- #

def _active_scene(context):
    """The scene that scene.new just made active, robust to headless windows."""
    if context.window:
        return context.window.scene
    return bpy.context.scene


def _set_scene(scene):
    if bpy.context.window:
        bpy.context.window.scene = scene
    else:
        for w in bpy.context.window_manager.windows:
            w.scene = scene


def _prepare_targets(targets, vl):
    """Localize each eligible target's mesh + materials and skip ineligible ones
    (no geometry / no material) rather than silently fabricating data for them.
    Returns (kept, skipped) where skipped is a list of (display_name, reason).

    Localizing gives each target its own datablocks so our edits never reach the
    originals, and so per-object lightmaps don't fight over a shared material's
    single image node.
    """
    kept, skipped = [], []
    for o in targets:
        if len(o.data.polygons) == 0:
            o.TLM_ObjectProperties.tlm_mesh_lightmap_use = False  # skip in bake loop
            skipped.append((_strip_suffix(o.name), "no geometry"))
            continue
        if not any(s.material for s in o.material_slots):
            o.TLM_ObjectProperties.tlm_mesh_lightmap_use = False
            skipped.append((_strip_suffix(o.name), "no material"))
            continue

        o.hide_set(False, view_layer=vl)
        o.hide_viewport = False
        o.hide_render = False
        if o.data.users > 1:
            o.data = o.data.copy()
        # Repair invalid mesh data on the copy. A corrupt mesh (out-of-range
        # indices / bad customdata) makes modifier evaluation read out of bounds
        # and HARD-CRASH Blender (EXCEPTION_ACCESS_VIOLATION) — most notably the
        # "Smooth by Angle" geometry-nodes modifier's edge_angle field, which
        # glTF export evaluates via export_apply=True. validate() runs on the
        # throwaway copy, so the user's original mesh is never touched.
        try:
            if o.data.validate(verbose=False):
                print("[TLM Export] repaired invalid mesh on '%s'" % o.name)
        except Exception as e:
            print("[TLM Export] mesh validate failed on '%s': %s" % (o.name, e))
        for slot in o.material_slots:
            if slot.material is not None:
                slot.material = slot.material.copy()    # localize
                slot.material.use_nodes = True

        kept.append(o)
    return kept, skipped


def _strip_suffix(name):
    m = _SUFFIX_RE.match(name)
    return m.group(1) if m else name


# --------------------------------------------------------------------------- #
# 2) Unwrap + bake setup
# --------------------------------------------------------------------------- #

def _setup_targets(temp, targets, savedir, vl):
    """Unwrap targets, create float bake images, and bind them as the active
    image node on every material slot. Returns obj.name -> (id, bake_base,
    is_atlas)."""
    eng = temp.TLM_EngineProperties
    res_scale = int(eng.tlm_resolution_scale)
    ss = {"2x": 2, "4x": 4}.get(eng.tlm_setting_supersample, 1)

    # Deterministic UV selection so average/pack act on all islands.
    temp.tool_settings.use_uv_select_sync = False

    lm_for_obj = {}
    used_ids = set()

    atlas_groups = {}    # atlas_name -> [objs]
    plain = []
    for o in targets:
        op = o.TLM_ObjectProperties
        if op.tlm_mesh_lightmap_unwrap_mode == "AtlasGroupA" and op.tlm_atlas_pointer:
            atlas_groups.setdefault(op.tlm_atlas_pointer, []).append(o)
        else:
            plain.append(o)

    # Resolve atlas groups up front; demote any whose atlas definition is missing
    # to per-object baking *before* the plain loop runs, so those objects still
    # get a lightmap entry (otherwise _finalize KeyErrors on them at the end).
    valid_atlas = {}     # atlas_name -> (agroup, members)
    for atlas_name, members in atlas_groups.items():
        agroup = temp.TLM_AtlasList.get(atlas_name)
        if agroup is None:
            _log("atlas '%s' not in atlas list - baking %d member(s) per-object"
                 % (atlas_name, len(members)))
            plain.extend(members)
        else:
            valid_atlas[atlas_name] = (agroup, members)

    _log("%d atlas group(s), %d per-object target(s)" % (len(valid_atlas), len(plain)))

    # --- plain (per-object) -------------------------------------------------
    for o in plain:
        _ensure_lm_uv(o)
        _unwrap_object(o, vl)
        res = _res(int(o.TLM_ObjectProperties.tlm_mesh_lightmap_resolution),
                   res_scale, ss)
        bake_base = o.name + "_baked"
        img = _new_float_image(bake_base, res, savedir)
        _bind_bake_image(o, img)
        ident = _make_id(o.name, used_ids)
        lm_for_obj[o.name] = (ident, bake_base, False)

    # --- shared pre-pack atlas groups --------------------------------------
    for atlas_name, (agroup, members) in valid_atlas.items():
        res = _res(int(agroup.tlm_atlas_lightmap_resolution), res_scale, ss)
        bake_base = atlas_name + "_baked"
        img = _new_float_image(bake_base, res, savedir)
        for o in members:
            _ensure_lm_uv(o)
        _unwrap_atlas(members, agroup, vl)
        for o in members:
            _bind_bake_image(o, img)
            lm_for_obj[o.name] = (atlas_name, bake_base, True)
        used_ids.add(atlas_name)

    return lm_for_obj


def _res(base, scale, supersample):
    return max(1, int(base / max(1, scale) * supersample))


def _ensure_lm_uv(o):
    uvs = o.data.uv_layers
    lm = uvs.get(LM_UV)
    if lm is None:
        lm = uvs.new(name=LM_UV)
    uvs.active = lm
    return lm


def _unwrap_object(o, vl):
    mode = o.TLM_ObjectProperties.tlm_mesh_lightmap_unwrap_mode
    margin = o.TLM_ObjectProperties.tlm_mesh_unwrap_margin
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True, view_layer=vl)
    vl.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    if mode == "Lightmap":
        bpy.ops.uv.lightmap_pack('EXEC_SCREEN', PREF_CONTEXT='ALL_FACES',
                                 PREF_MARGIN_DIV=margin)
    else:   # SmartProject (also the fallback for Copy/Xatlas in this path)
        bpy.ops.uv.smart_project(angle_limit=math.radians(45.0),
                                 island_margin=margin, area_weight=1.0,
                                 correct_aspect=True, scale_to_bounds=False)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')


def _unwrap_atlas(members, agroup, vl):
    """Unwrap all members into one shared 0..1 UV space (the shared atlas)."""
    tris = sum(len(o.data.polygons) for o in members)
    _log("Atlas '%s': %d object(s), %d face(s), unwrap=%s"
         % (agroup.name, len(members), tris, agroup.tlm_atlas_lightmap_unwrap_mode))

    bpy.ops.object.select_all(action='DESELECT')
    for o in members:
        o.select_set(True, view_layer=vl)
    vl.objects.active = members[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')

    t0 = time()
    if agroup.tlm_atlas_lightmap_unwrap_mode == "Lightmap":
        bpy.ops.uv.lightmap_pack('EXEC_SCREEN', PREF_CONTEXT='ALL_FACES',
                                 PREF_MARGIN_DIV=agroup.tlm_atlas_unwrap_margin)
    else:
        bpy.ops.uv.smart_project(angle_limit=math.radians(45.0),
                                 island_margin=agroup.tlm_atlas_unwrap_margin,
                                 area_weight=1.0, correct_aspect=True,
                                 scale_to_bounds=False)
    _log("  unwrap done in %.1fs" % (time() - t0))

    # Equalize texel density across all members, then tightly repack so the
    # shared atlas uses as much space as possible (Smart Project's own packing
    # leaves a lot of empty room).
    if getattr(agroup, "tlm_atlas_repack", True):
        _average_and_pack(_pack_margin_for(agroup, bpy.context.scene),
                          getattr(agroup, "tlm_atlas_pack_shape", "AABB"))

    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')


def _pack_margin_for(agroup, scene):
    """UV-space pack margin for an atlas. When auto, derive it from the bake
    dilation: each baked island bleeds D px outward, so two neighbours need >= 2D
    px between them or their dilations overlap (light bleed). With pack
    margin_method='FRACTION' the margin is a per-island BORDER, so the gap between
    two islands is 2*margin (measured) -> setting margin = D/R gives a gap of
    2D px exactly. Clamped so an extreme dilation / tiny atlas can't ask for a
    nonsensical margin. Falls back to the manual value when auto is off."""
    if not getattr(agroup, "tlm_atlas_pack_margin_auto", True):
        return agroup.tlm_atlas_pack_margin
    res = int(agroup.tlm_atlas_lightmap_resolution)
    if not res:
        return agroup.tlm_atlas_pack_margin
    d = scene.TLM_EngineProperties.tlm_dilation_margin
    return min(float(d) / res, 0.2)


def _average_and_pack(margin, shape):
    """In multi-object edit mode: give every island uniform texel density, then
    pack all islands into 0..1. shape='AABB' is fast; 'CONCAVE' packs tighter but
    can be very slow on atlases with many islands."""
    bpy.ops.uv.select_all(action='SELECT')

    t0 = time()
    bpy.ops.uv.average_islands_scale()
    _log("  average islands scale done in %.1fs" % (time() - t0))

    t0 = time()
    _log("  packing islands (shape=%s, margin=%.4f)..." % (shape, margin))
    # margin_method='FRACTION' makes `margin` a literal fraction of the unit
    # square (the inter-island gap), so the auto margin (2*dilation/res) maps to
    # an exact pixel gap; the default 'SCALED' would rescale it by island size.
    # Degrade gracefully across Blender versions that lack either kwarg.
    for kwargs in (dict(rotate=True, margin=margin, margin_method='FRACTION', shape_method=shape),
                   dict(rotate=True, margin=margin, margin_method='FRACTION'),
                   dict(rotate=True, margin=margin, shape_method=shape),
                   dict(rotate=True, margin=margin)):
        try:
            bpy.ops.uv.pack_islands(**kwargs)
            break
        except TypeError:
            continue
    _log("  pack done in %.1fs" % (time() - t0))


def _new_float_image(name, res, savedir):
    img = bpy.data.images.new(name, res, res, alpha=True, float_buffer=True)
    img.filepath_raw = os.path.join(savedir, name + ".hdr")
    img.file_format = "HDR"
    img.save()                       # lightmap.bake re-saves into this file
    return img


def _bind_bake_image(o, img):
    """Add (or reuse) a TLM_Lightmap image node on each slot and make it the
    active bake target."""
    for slot in o.material_slots:
        mat = slot.material
        if mat is None:
            continue
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        node = nodes.get("TLM_Lightmap")
        if node is None:
            node = nodes.new("ShaderNodeTexImage")
            node.name = "TLM_Lightmap"
            node.label = "TLM_Lightmap"
            node.location = (-900, 400)
        node.image = img
        node.select = True
        nodes.active = node


# --------------------------------------------------------------------------- #
# 4b) Denoise
# --------------------------------------------------------------------------- #

def _denoise_lightmaps(temp, lm_for_obj, savedir):
    """Denoise each unique baked lightmap HDR in place using Blender's built-in
    Compositor Denoise node (OpenImageDenoise). Needs no external binary/path.

    The compositor only runs as a post-process of bpy.ops.render.render, which
    requires a camera and renders the (here unused) 3D view layer. We force a
    throwaway camera and a 1-sample render so that pass is near-instant; the
    saved file comes solely from the Image -> Denoise -> Composite chain. The
    temp scene is discarded in _cleanup, so none of these mutations are restored.
    Returns the number of lightmaps denoised.
    """
    bases, seen = [], set()
    for _ident, bake_base, _is_atlas in lm_for_obj.values():
        if bake_base not in seen:
            seen.add(bake_base)
            bases.append(bake_base)

    if temp.camera is None:                      # FULL_COPY usually carries one
        cam = bpy.data.objects.new("TLM_DenoiseCam",
                                   bpy.data.cameras.new("TLM_DenoiseCam"))
        temp.collection.objects.link(cam)
        temp.camera = cam

    try:
        temp.cycles.samples = 1                  # 3D layer is unused; keep it cheap
    except AttributeError:
        pass

    # Compositor node tree. Blender 4.x embeds it as scene.node_tree (via
    # use_nodes); Blender 5.x moved it to a shared CompositorNodeTree datablock
    # at scene.compositing_node_group, dropped scene.node_tree AND the Composite
    # output node (output is now the node group's output). Getting this wrong is
    # exactly why denoise silently no-op'd on 5.x: the old code hit
    # AttributeError on scene.node_tree and the caller swallowed it.
    owned_ng = None
    if hasattr(temp, "compositing_node_group"):          # Blender 5.x
        tree = bpy.data.node_groups.new("TLM_Denoise_Comp", 'CompositorNodeTree')
        temp.compositing_node_group = tree
        owned_ng = tree
    else:                                                # Blender 4.x
        temp.use_nodes = True
        tree = temp.node_tree
        for n in list(tree.nodes):
            tree.nodes.remove(n)

    img_node = tree.nodes.new('CompositorNodeImage')
    dn_node = tree.nodes.new('CompositorNodeDenoise')
    if hasattr(dn_node, "use_hdr"):              # 4.x had this toggle; 5.x dropped it
        dn_node.use_hdr = True
    tree.links.new(img_node.outputs[0], dn_node.inputs[0])

    if owned_ng is not None:                     # 5.x: feed the node group's output
        tree.interface.new_socket(name="Image", in_out='OUTPUT', socket_type='NodeSocketColor')
        out_node = tree.nodes.new('NodeGroupOutput')
    else:                                        # 4.x: classic Composite output
        out_node = tree.nodes.new('CompositorNodeComposite')
    tree.links.new(dn_node.outputs[0], out_node.inputs[0])

    rs = temp.render
    rs.use_compositing = True
    rs.use_sequencer = False
    rs.image_settings.file_format = 'HDR'
    try:                                         # keep lightmap data linear
        temp.view_settings.view_transform = 'Raw'
    except TypeError:
        temp.view_settings.view_transform = 'Standard'

    done = 0
    try:
        for base in bases:
            src = os.path.join(savedir, base + ".hdr")
            if not os.path.isfile(src):
                _log("  denoise: missing %s" % src)
                continue
            img = bpy.data.images.load(src, check_existing=False)
            img_node.image = img
            rs.resolution_x, rs.resolution_y = img.size[0], img.size[1]
            rs.resolution_percentage = 100
            dst = os.path.join(savedir, base + "_dn.hdr")
            rs.filepath = dst
            bpy.ops.render.render(write_still=True)
            bpy.data.images.remove(img)
            if os.path.isfile(dst):
                os.replace(dst, src)             # denoised data flows into the EXR sidecar
                done += 1
            else:
                _log("  denoise: no output written for %s" % base)
    finally:
        if owned_ng is not None:                 # don't leak the throwaway node group
            try:
                temp.compositing_node_group = None
                bpy.data.node_groups.remove(owned_ng)
            except Exception:
                pass
    return done


# --------------------------------------------------------------------------- #
# 5) Sidecars, occlusion wiring, manifest, export
# --------------------------------------------------------------------------- #

def _finalize(temp, targets, lm_for_obj, savedir, out_dir, group):
    # Raw view transform so the EXR carries linear lightmap data 1:1.
    try:
        temp.view_settings.view_transform = 'Raw'
    except TypeError:
        temp.view_settings.view_transform = 'Standard'

    manifest = {}
    converted = {}     # bake_base -> sidecar filename (dedupes atlas members)

    for o in targets:
        entry = lm_for_obj.get(o.name)
        if entry is None:
            print("[TLM Export] WARNING: no lightmap baked for '%s' - omitting from manifest" % o.name)
            continue
        ident, bake_base, is_atlas = entry
        if bake_base not in converted:
            src = os.path.join(savedir, bake_base + ".hdr")
            sidecar = ident + "_lightmap.exr"
            _hdr_to_exr(src, os.path.join(out_dir, sidecar), temp)
            converted[bake_base] = sidecar

        if group is not None:
            _wire_occlusion(o, group)

        # Both travel to the GLB node.extras (export_extras=True). The UV index
        # MUST be per-object: atlas members can have different numbers of UV
        # layers, so the lightmap UV lands at a different TEXCOORD per object
        # (e.g. a rock with no original UV -> TEXCOORD_0, one with an original
        # UV -> TEXCOORD_1). The manifest is keyed by atlas ident (shared), so
        # it CANNOT carry a per-object uv -- read tlm_lightmap_uv off the node.
        uv = _lm_uv_index(o)
        o["tlm_lightmap_id"] = ident
        o["tlm_lightmap_uv"] = uv
        manifest[ident] = {
            "file": converted[bake_base],
            # NOTE: per-atlas fallback only (last member wins). The authoritative
            # per-object value is node.extras.tlm_lightmap_uv -- prefer it.
            "uv": uv,
            "atlas": is_atlas,
            # Per-lightmap mode so the runtime knows how to apply it: lighting-
            # only modes (combined/indirect/ao) multiply against base color;
            # 'complete' is the full baked-down look, applied unlit.
            "lighting_mode": lightmap.effective_lighting_mode(temp, o),
        }
    return manifest


def _hdr_to_exr(src, dst, scene):
    if not os.path.isfile(src):
        print("TLM export: missing bake %s" % src)
        return
    img = bpy.data.images.load(src, check_existing=False)
    s = scene.render.image_settings
    s.file_format = 'OPEN_EXR'
    s.color_mode = 'RGB'
    s.color_depth = '32'
    s.exr_codec = 'ZIP'
    img.save_render(dst, scene=scene)
    bpy.data.images.remove(img)


def _lm_uv_index(o):
    for i, layer in enumerate(o.data.uv_layers):
        if layer.name == LM_UV:
            return i
    return 0


def _ensure_gltf_group():
    group = bpy.data.node_groups.get(GLTF_GROUP)
    if group is None:
        group = bpy.data.node_groups.new(GLTF_GROUP, 'ShaderNodeTree')
    if not _group_has_input(group, "Occlusion"):
        if hasattr(group, "interface"):
            group.interface.new_socket(name="Occlusion", in_out='INPUT')
        else:
            group.inputs.new('NodeSocketFloat', "Occlusion")
    return group


def _group_has_input(group, name):
    if hasattr(group, "interface"):
        return any(getattr(it, "in_out", None) == 'INPUT' and it.name == name
                   for it in group.interface.items_tree)
    return name in group.inputs


def _wire_occlusion(o, group):
    """Drive the glTF occlusion slot with the baked lightmap. This is what makes
    the exporter keep the lightmap UV (as TEXCOORD_1) and gives an LDR baseline
    (three.js aoMap) alongside the HDR sidecar."""
    for slot in o.material_slots:
        mat = slot.material
        if mat is None or not mat.node_tree:
            continue
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        lm = nodes.get("TLM_Lightmap")
        if lm is None:
            continue
        uv = nodes.get("TLM_Lightmap_UV")
        if uv is None:
            uv = nodes.new("ShaderNodeUVMap")
            uv.name = "TLM_Lightmap_UV"
            uv.location = (-1200, 400)
        uv.uv_map = LM_UV
        links.new(uv.outputs[0], lm.inputs[0])
        g = nodes.get(GLTF_GROUP)
        if g is None:
            g = nodes.new("ShaderNodeGroup")
            g.name = GLTF_GROUP
            g.node_tree = group
            g.location = (-300, 500)
        links.new(lm.outputs[0], g.inputs[0])


def _export_gltf(glb_path):
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format='GLB',
        use_active_scene=True,
        use_selection=False,
        export_apply=True,          # apply modifiers (on the copy)
        export_extras=True,         # carry tlm_lightmap_id -> node.extras
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_materials='EXPORT',
    )


def _write_manifest(out_dir, glb_path, manifest, lighting_mode):
    data = {
        "format": "tlm-export/1",
        "glb": os.path.basename(glb_path),
        "lighting_mode": lighting_mode,
        "uv_layer": LM_UV,
        "lightmaps": manifest,
    }
    path = os.path.splitext(glb_path)[0] + ".lightmaps.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print("TLM export: wrote manifest %s" % path)


# --------------------------------------------------------------------------- #
# 6) Cleanup
# --------------------------------------------------------------------------- #

def _cleanup(scene0, temp):
    _set_scene(scene0)
    if temp is None or temp.name not in bpy.data.scenes:
        return

    # Collect exactly what the copy owns *before* unlinking the scene, so we
    # remove only our duplicates (never the user's other orphan data).
    objs = list(temp.objects)
    try:
        colls = list(temp.collection.children_recursive)
    except AttributeError:
        colls = list(temp.collection.children)
    meshes = {o.data for o in objs if o.type == 'MESH' and o.data}
    mats = {s.material for o in objs for s in o.material_slots if s.material}
    imgs = set()
    for m in mats:
        if m.node_tree:
            for n in m.node_tree.nodes:
                if getattr(n, "image", None):
                    imgs.add(n.image)

    try:
        bpy.data.scenes.remove(temp, do_unlink=True)
    except Exception as e:
        print("TLM export: temp scene removal failed: %s" % e)

    for o in objs:
        try:
            bpy.data.objects.remove(o, do_unlink=True)
        except Exception:
            pass
    for c in colls:
        try:
            bpy.data.collections.remove(c)
        except Exception:
            pass
    for me in meshes:
        if me.users == 0:
            try:
                bpy.data.meshes.remove(me)
            except Exception:
                pass
    for ma in mats:
        if ma.users == 0:
            try:
                bpy.data.materials.remove(ma)
            except Exception:
                pass
    for im in imgs:
        if im.users == 0:
            try:
                bpy.data.images.remove(im)
            except Exception:
                pass


# --------------------------------------------------------------------------- #
# misc
# --------------------------------------------------------------------------- #

def _make_id(copy_name, used):
    """Strip Blender's '.001' copy suffix to get a stable lightmap id, keeping
    it unique within this export."""
    m = _SUFFIX_RE.match(copy_name)
    base = m.group(1) if m else copy_name
    cand = base
    i = 1
    while cand in used:
        cand = "%s_%d" % (base, i)
        i += 1
    used.add(cand)
    return cand
