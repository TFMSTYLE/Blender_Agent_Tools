"""Runs once in a headless throwaway Blender, from live_test.py: enables the addons
and sets the MCP add-on to start on its own, on a port that leaves a real Blender alone."""

import json
import sys

import addon_utils
import bpy

port, names, out = sys.argv[sys.argv.index("--") + 1 :]
names = names.split(",")
for name in names:
    addon_utils._addon_ensure(name)
addon_utils.enable("bl_ext.user_default.mcp", default_set=True)
prefs = bpy.context.preferences.addons["bl_ext.user_default.mcp"].preferences
prefs.port = int(port)
prefs.use_autostart = True
prefs.autostart_delay = 0.5
bpy.ops.wm.save_userpref()
with open(out, "w", encoding="utf-8") as f:
    json.dump([a.module for a in bpy.context.preferences.addons], f)
