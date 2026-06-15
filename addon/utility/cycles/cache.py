"""Material backup/restore for the in-place bake pipeline.

The in-place build (``build.prepare_build`` / ``manage_build``) edits live
materials and relies on these helpers to put the originals back afterwards.

The nondestructive GLB export path (``export.py``) works on a throwaway scene
copy instead, so it does NOT use any of this — that's the intended way out of
the backup/restore tangle.
"""

import bpy


def backup_material_copy(slot):
    """Stash a fake-user copy of a material as '.<name>_Original'."""
    material = slot.material
    dup = material.copy()
    dup.name = "." + material.name + "_Original"
    dup.use_fake_user = True


def backup_material_restore(obj):
    """Restore an object's slots from their '.<name>_Original' backups, using
    the slot order recorded in TLM_PrevMatArray."""
    if "TLM_PrevMatArray" not in obj:
        return

    prev_mat_array = obj["TLM_PrevMatArray"]
    for idx, slot in enumerate(obj.material_slots):
        if slot.material is None:
            continue
        try:
            original = prev_mat_array[idx]
        except IndexError:
            continue
        backup = "." + original + "_Original"
        if backup in bpy.data.materials:
            slot.material = bpy.data.materials[backup]
            slot.material.use_fake_user = False


def backup_material_rename(obj):
    """Rename restored '.<name>_Original' backups back to their real names and
    drop the bookkeeping property."""
    if "TLM_PrevMatArray" not in obj:
        return

    for slot in obj.material_slots:
        if slot.material is not None and slot.material.name.endswith("_Original"):
            slot.material.name = slot.material.name[1:-9]

    del obj["TLM_PrevMatArray"]
