# SPDX-FileCopyrightText: 2026 The French Monkey
# SPDX-License-Identifier: GPL-3.0-or-later

"""Proves settings fail closed when an addon's panel source cannot be read. No Blender.

    python tests/test_security_settings.py

inside.py imports bpy and mathutils, so both are stubbed before it loads.
"""

import contextlib
import importlib.util
import pathlib
import sys
import tempfile
import types

HERE = pathlib.Path(__file__).resolve().parent
INSIDE = HERE.parent / "src" / "tfmstyle_agent_tools" / "inside.py"

bpy = types.ModuleType("bpy")
bpy.context = types.SimpleNamespace(temp_override=lambda **kw: contextlib.nullcontext())
bpy.app = types.SimpleNamespace(background=True)
bpy.types = types.SimpleNamespace(bpy_prop_collection=list)
mathutils = types.ModuleType("mathutils")
mathutils.Vector = tuple
sys.modules.update(bpy=bpy, mathutils=mathutils)

spec = importlib.util.spec_from_file_location("inside", INSIDE)
inside = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inside)

failed = []


def check(label, passed, detail=""):
    print("  ok  " if passed else "  FAIL", label, "" if passed else detail)
    if not passed:
        failed.append(label)


def prop(identifier, kind="FLOAT"):
    return types.SimpleNamespace(identifier=identifier, type=kind, is_readonly=False, is_hidden=False)


RNA = types.SimpleNamespace(properties=[prop("rna_type", "POINTER"), prop("name", "STRING"), prop("size"), prop("seed", "INT"), prop("is_running", "BOOLEAN"), prop("cache_key", "STRING")])
PANEL = '''
def draw(self, context):
    layout.prop(s, "size")
    layout.prop(s, 'seed')
    layout.prop(s, "show_advanced")
'''


def addon_at(path):
    return dict(module=types.SimpleNamespace(__file__=str(path)))


with tempfile.TemporaryDirectory() as folder:
    folder = pathlib.Path(folder)
    normal = folder / "normal.py"
    normal.write_text(PANEL, encoding="utf-8")
    bare = folder / "bare.py"
    bare.write_text("def draw(self, context):\n    layout.label(text='hi')\n", encoding="utf-8")

    print("public_names")
    check("normal source lists drawn settings, show_* left out", inside.public_names(addon_at(normal)) == {"size", "seed"}, inside.public_names(addon_at(normal)))
    check("unreadable path gives an empty set, not None", inside.public_names(addon_at(folder / "missing.py")) == set())
    check("module with no __file__ gives an empty set", inside.public_names(dict(module=types.SimpleNamespace(__file__=None))) == set())
    check("source with no .prop( gives an empty set, not None", inside.public_names(addon_at(bare)) == set())

print("settable")
names = lambda public: [p.identifier for p in inside.settable(RNA, public)]
check("public set filters to what the panel draws", names({"size", "seed"}) == ["size", "seed"], names({"size", "seed"}))
check("empty set refuses every setting, private state included", names(set()) == [], names(set()))
check("private state is never settable", "is_running" not in names({"size", "seed"}) and "cache_key" not in names({"size", "seed"}))

print("run_addon and describe_addon with an unreadable panel")


class Make:
    bl_label = "Make"


group = types.SimpleNamespace(bl_rna=RNA, size=1.0, seed=0, is_running=False, cache_key="")
inside.installed = lambda: {"rock": dict(module=types.SimpleNamespace(__file__=None, __name__="rock"), name="Rock", version="1.0", installed_as="separate")}
inside.space_of = lambda info: "VIEW_3D"
inside.window_for = lambda space: {}
inside.groups_of = lambda info: [group]
inside.actions_of = lambda info: {"rock.make": Make}
inside.lists_of = lambda g: []
inside.drawn_now = lambda info, groups: None
inside.snapshot = lambda: {}

reply = inside.run_addon("rock", settings={"is_running": True})
check("settings refused with the locked message", reply.get("ok") is False and reply.get("refused") == ["cannot read rock's panel source, settings are locked"], reply)
check("nothing was written to private state", group.is_running is False)
reply = inside.run_addon("rock", action="rock.make", settings={"size": 2.0})
check("action plus settings is refused whole", reply.get("ok") is False and group.size == 1.0, reply)

ran = []
bpy.ops = types.SimpleNamespace(rock=types.SimpleNamespace(make=lambda mode: ran.append(mode) or {"FINISHED"}))
reply = inside.run_addon("rock", action="rock.make")
check("an action alone still runs", ran == ["EXEC_DEFAULT"] and reply.get("result") == ["FINISHED"], reply)

reply = inside.describe_addon("rock")
check("describe shows no settings and says why", reply["settings"] == [] and reply.get("settings_locked") == "cannot read rock's panel source, settings are locked", reply)
check("describe still lists the actions", [a["id"] for a in reply["actions"]] == ["rock.make"], reply["actions"])

print()
print(f"{len(failed)} failed" if failed else "all passed")
sys.exit(1 if failed else 0)
