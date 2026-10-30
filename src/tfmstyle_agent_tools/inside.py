# SPDX-FileCopyrightText: 2026 The French Monkey
# SPDX-License-Identifier: GPL-3.0-or-later

"""Runs inside Blender. server.py sends this file whole with one call on the end, so
nothing is installed in Blender. Names, settings and ranges are read from Blender at
that moment: nothing about any addon is hand kept here."""

import contextlib
import io
import json
import re
import sys
import tomllib
from pathlib import Path

import bpy

OURS = ("The French Monkey", "TFMSTYLE")
# The addons proven so far. The rest join as they pass tests/live_test.py.
TESTED = ("rock", "orbiter", "graph")
# These reach outside Blender or open a dialog that nobody is there to answer.
NEVER = re.compile(r"import|export|browse|url|link|open|file", re.I)
# These take work away, so the caller has to ask for it twice.
CONFIRM = re.compile(r"delete|clear|reset|remove", re.I)
SETTABLE = ("BOOLEAN", "INT", "FLOAT", "STRING", "ENUM")
SHOWN_ITEMS = 20


def key_of(addon_id):
    return re.sub(r"^tfmstyle_|_generator$", "", addon_id)


def installed():
    """Every addon of ours that is running, on its own or inside the collection."""
    found = {}
    for name in [a.module for a in bpy.context.preferences.addons]:
        module = sys.modules.get(name)
        path = getattr(module, "__file__", None)
        manifest = Path(path).with_name("blender_manifest.toml") if path else None
        if not manifest or not manifest.is_file():
            continue
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
        if data.get("maintainer") not in OURS:
            continue
        if hasattr(module, "LOADED"):
            for entry in module.ADDONS:
                if entry["key"] in module.LOADED:
                    found[entry["key"]] = dict(module=module.LOADED[entry["key"]], name=entry["label"], version=entry.get("running", entry["version"]), installed_as="collection")
        else:
            found[key_of(data["id"])] = dict(module=module, name=data["name"], version=data["version"], installed_as="separate")
    return {key: value for key, value in found.items() if key in TESTED}


def space_of(addon):
    """The editor its panel lives in, which is where its actions expect to run."""
    name = addon["module"].__name__
    return next((c.bl_space_type for c in bpy.types.Panel.__subclasses__() if c.__module__ == name), "VIEW_3D")


def window_for(space):
    """Requests arrive on a timer, where Blender has no window in context."""
    windows = bpy.context.window_manager.windows
    if not windows:
        return {}
    window = windows[0]
    for area in window.screen.areas:
        if area.type == space:
            return dict(window=window, area=area, region=next((r for r in area.regions if r.type == "WINDOW"), None))
    return dict(window=window)


def groups_of(addon):
    """The addon's settings groups on the scene."""
    name = addon["module"].__name__
    ours = {c.__name__ for c in bpy.types.PropertyGroup.__subclasses__() if c.__module__ == name}
    scene = bpy.context.scene
    return [getattr(scene, p.identifier) for p in bpy.types.Scene.bl_rna.properties if p.type == "POINTER" and p.fixed_type.identifier in ours]


def actions_of(addon):
    name = addon["module"].__name__
    found = {}
    for cls in bpy.types.Operator.__subclasses__():
        if cls.__module__ != name or not cls.is_registered or not hasattr(cls, "execute"):
            continue
        if NEVER.search(cls.bl_idname) or "filepath" in cls.bl_rna.properties:
            continue
        found[cls.bl_idname] = cls
    return found


def settable(group):
    return [p for p in group.bl_rna.properties if p.identifier not in ("rna_type", "name") and p.type in SETTABLE and not p.is_readonly and not p.is_hidden]


def lists_of(group):
    return [p for p in group.bl_rna.properties if p.type == "COLLECTION" and p.identifier != "rna_type"]


def enum_values(group, prop):
    values = [i.identifier for i in prop.enum_items]
    if values:
        return values
    try:  # a callback fills this one, and the refusal lists what it allows
        setattr(group, prop.identifier, "__none__")
    except TypeError as e:
        return re.findall(r"'([^']+)'", str(e).split("not found in", 1)[-1])
    return []


def value_of(group, prop):
    value = getattr(group, prop.identifier)
    if prop.type == "ENUM" and prop.is_enum_flag:
        return sorted(value)
    return list(value) if getattr(prop, "array_length", 0) else value


def field(group, prop):
    item = dict(name=prop.identifier, label=prop.name, type=prop.type.lower(), value=value_of(group, prop))
    if prop.description:
        item["description"] = prop.description
    if prop.type in ("INT", "FLOAT"):
        item.update(min=prop.soft_min, max=prop.soft_max)
    if prop.type == "ENUM":
        item["options"] = enum_values(group, prop)
    return item


def number_problem(prop, value):
    whole = prop.type == "INT"
    if isinstance(value, bool) or not isinstance(value, int if whole else (int, float)):
        return "must be a whole number" if whole else "must be a number"
    if not prop.soft_min <= value <= prop.soft_max:
        return f"must be between {prop.soft_min} and {prop.soft_max}"
    return None


def problem(group, prop, value):
    if prop.type == "BOOLEAN":
        return None if isinstance(value, bool) else "must be true or false"
    if prop.type == "STRING":
        return None if isinstance(value, str) else "must be text"
    if prop.type == "ENUM":
        options = enum_values(group, prop)
        chosen = value if prop.is_enum_flag and isinstance(value, list) else [value]
        return None if all(v in options for v in chosen) else f"must be one of {options}"
    if not prop.array_length:
        return number_problem(prop, value)
    if not isinstance(value, list) or len(value) != prop.array_length:
        return f"must be a list of {prop.array_length} numbers"
    return next(filter(None, (number_problem(prop, v) for v in value)), None)


def resolve(groups, key):
    """A plain name, or list[index].name for settings kept per item, like Graph's."""
    match = re.fullmatch(r"(\w+)\[(\d+)\]\.(\w+)", key)
    for group in groups:
        holder, name = group, key
        if match:
            items = getattr(group, match[1], None)
            if not isinstance(items, bpy.types.bpy_prop_collection) or int(match[2]) >= len(items):
                continue
            holder, name = items[int(match[2])], match[3]
        prop = next((p for p in settable(holder) if p.identifier == name), None)
        if prop:
            return holder, prop
    return None, None


def unknown(key, found):
    return dict(ok=False, refused=[f"{key} is not one of: {sorted(found)}"])


def list_addons():
    found = installed()
    rows = [dict(addon=k, name=v["name"], version=v["version"], installed_as=v["installed_as"], editor=space_of(v)) for k, v in sorted(found.items())]
    # Not windows: background Blender keeps a window it never draws.
    return dict(addons=rows, not_running=[k for k in TESTED if k not in found], has_window=not bpy.app.background)


def describe_addon(addon):
    found = installed()
    if addon not in found:
        return unknown(addon, found)
    info = found[addon]
    space = space_of(info)
    with bpy.context.temp_override(**window_for(space)):
        groups = groups_of(info)
        settings = [field(g, p) for g in groups for p in settable(g)]
        lists = []
        for group in groups:
            for prop in lists_of(group):
                items = getattr(group, prop.identifier)
                shape = settable(items[0]) if len(items) else []
                lists.append(dict(name=prop.identifier, label=prop.name, count=len(items), fields=[field(items[0], p) for p in shape],
                                  items=[{p.identifier: value_of(i, p) for p in shape} for i in items[:SHOWN_ITEMS]]))
    actions = [dict(id=i, label=c.bl_label, description=getattr(c, "bl_description", ""), needs_confirm=bool(CONFIRM.search(i))) for i, c in sorted(actions_of(info).items())]
    return dict(addon=addon, name=info["name"], version=info["version"], installed_as=info["installed_as"], editor=space, actions=actions, settings=settings, lists=lists)


def run_addon(addon, action="", settings=None, confirm=False):
    found = installed()
    if addon not in found:
        return unknown(addon, found)
    info = found[addon]
    with bpy.context.temp_override(**window_for(space_of(info))):
        groups = groups_of(info)
        plan, refused = [], []
        for key, value in (settings or {}).items():
            holder, prop = resolve(groups, key)
            why = "is not a setting of this addon" if prop is None else problem(holder, prop, value)
            if why:
                refused.append(f"{key} {why}")
            else:
                plan.append((holder, prop.identifier, value))
        actions = actions_of(info)
        if action and action not in actions:
            refused.append(f"{action} is not one of: {sorted(actions)}")
        elif action and CONFIRM.search(action) and not confirm:
            refused.append(f"{action} takes work away: pass confirm=true if that is what you want")
        elif action and bpy.app.background and hasattr(actions[action], "modal"):
            # It would start, say it was running, and never get another tick.
            refused.append(f"{action} keeps running, which needs an open Blender window")
        if refused or not (plan or action):
            return dict(ok=False, refused=refused or ["Nothing to do: pass an action, settings or both"])

        before = {o.name_full for o in bpy.data.objects}
        log = io.StringIO()
        status = []
        try:
            with contextlib.redirect_stdout(log):
                for holder, name, value in plan:
                    setattr(holder, name, set(value) if isinstance(value, list) and holder.bl_rna.properties[name].type == "ENUM" else value)
                if action:
                    group, name = action.split(".", 1)
                    status = sorted(getattr(getattr(bpy.ops, group), name)("EXEC_DEFAULT"))
        except Exception as e:
            return dict(ok=False, error=str(e)[-800:], settings_set=[n for _, n, _ in plan], messages=log.getvalue().strip().splitlines())
        made = [o for o in bpy.data.objects if o.name_full not in before]
        return dict(
            ok=not action or bool({"FINISHED", "RUNNING_MODAL"} & set(status)),
            result=status,
            new_objects=[dict(name=o.name_full, type=o.type, vertices=len(o.data.vertices) if o.type == "MESH" else None) for o in made],
            removed_objects=sorted(before - {o.name_full for o in bpy.data.objects}),
            messages=log.getvalue().strip().splitlines(),
        )
