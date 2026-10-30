"""Proves the toolbox against a real Blender, the way an agent uses it.

    python tests/live_test.py <folder of zips> <collection zip>

Starts throwaway Blenders with their own settings folder, on their own port, and
drives them through a real MCP connection to the server. A real Blender stays untouched.
The zips folder holds one zip each for Rock, Orbiter and Graph.
"""

import asyncio
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import zipfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from tfmstyle_agent_tools import bridge

HERE = pathlib.Path(__file__).resolve().parent
BLENDER = os.environ.get("BLENDER_EXE", r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe")
MCP_ADDON = pathlib.Path(os.environ["APPDATA"]) / "Blender Foundation" / "Blender" / "5.1" / "extensions" / "user_default" / "mcp"
PORT = 9891
os.environ["BLENDER_MCP_PORT"] = str(PORT)

failed = []


def check(label, passed, detail=""):
    print("  ok  " if passed else "  FAIL", label, "" if passed else detail)
    if not passed:
        failed.append(label)


def mcp_addon_zip(folder):
    path = pathlib.Path(folder) / "mcp.zip"
    with zipfile.ZipFile(path, "w") as z:
        for file in MCP_ADDON.iterdir():
            if file.is_file():
                z.write(file, file.name)
    return path


def prepare(home, zips, names):
    env = {**os.environ, "BLENDER_USER_RESOURCES": str(home)}
    for zip_path in [mcp_addon_zip(home), *zips]:
        subprocess.run([BLENDER, "--command", "extension", "install-file", "-r", "user_default", str(zip_path)], env=env, capture_output=True, check=True)
    out = pathlib.Path(home) / "enabled.json"
    subprocess.run([BLENDER, "-b", "--online-mode", "--python", str(HERE / "setup_blender.py"), "--", str(PORT), ",".join(names), str(out)], env=env, capture_output=True, check=True)
    return env


def wait_for_port(seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        with socket.socket() as s:
            s.settimeout(1)
            if s.connect_ex(("127.0.0.1", PORT)) == 0:
                return True
        time.sleep(0.5)
    return False


class Blender:
    def __init__(self, env, window):
        self.env, self.window = env, window

    def __enter__(self):
        flags = ["--window-geometry", "0", "0", "1280", "720", "--online-mode"] if self.window else ["-b", "--online-mode", "--command", "blender_mcp", "--port", str(PORT)]
        self.process = subprocess.Popen([BLENDER, *flags], env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not wait_for_port():
            self.process.kill()
            sys.exit("Blender never opened the MCP port")
        time.sleep(2)  # the collection and the addons finish starting on timers
        return self

    def __exit__(self, *_):
        self.process.kill()
        self.process.wait()
        time.sleep(1)


def raw(code):
    """Test setup and reading the truth back, past the toolbox."""
    return bridge.run("import bpy\n" + code)


async def tool(session, name, **args):
    reply = await session.call_tool(name, args)
    if reply.isError:
        raise RuntimeError(reply.content[0].text)
    return json.loads(reply.content[0].text)


async def rock(session):
    print("rock")
    d = await tool(session, "describe_addon", addon="rock")
    ids = [a["id"] for a in d["actions"]]
    check("finds its actions", "rock.generate" in ids, ids)
    check("hides the updater", not [i for i in ids if "update" in i], ids)
    number = next(s for s in d["settings"] if s["type"] == "int")
    choice = next(s for s in d["settings"] if s["type"] == "enum" and len(s["options"]) > 1)
    print("   ", len(d["settings"]), "settings, using", number["name"], "and", choice["name"])

    r = await tool(session, "run_addon", addon="rock", action="rock.generate", settings={number["name"]: number["max"], choice["name"]: choice["options"][-1]})
    check("generates", r["ok"] and r["new_objects"] and r["new_objects"][0]["vertices"], r)
    count = raw("result = {'n': len(bpy.data.objects)}")["n"]

    for action in ("object.delete", "wm.quit_blender", "tfmstyle_update.blender_rock"):
        r = await tool(session, "run_addon", addon="rock", action=action)
        check(f"refuses {action}", not r["ok"] and "refused" in r, r)
    r = await tool(session, "run_addon", addon="rock", action="rock.generate", settings={number["name"]: number["min"], choice["name"]: "nonsense"})
    check("one bad value refuses the whole call", not r["ok"] and "refused" in r, r)
    r = await tool(session, "run_addon", addon="rock", settings={number["name"]: number["max"] + 1})
    check("refuses out of range", not r["ok"] and "between" in r["refused"][0], r)
    r = await tool(session, "run_addon", addon="rock", settings={number["name"]: "12"})
    check("refuses the wrong type", not r["ok"], r)
    r = await tool(session, "run_addon", addon="rock", settings={number["name"]: True})
    check("refuses true for a number", not r["ok"], r)
    r = await tool(session, "run_addon", addon="rock", settings={"not_a_setting": 1})
    check("refuses an unknown setting", not r["ok"], r)
    r = await tool(session, "run_addon", addon="x'); import os; os._exit(1) #")
    check("refuses a bad addon name", not r["ok"], r)
    r = await tool(session, "run_addon", addon="rock")
    check("refuses an empty call", not r["ok"], r)
    r = await tool(session, "run_addon", addon="rock", action="rock.reset_settings")
    check("reset needs confirm", not r["ok"] and "confirm" in r["refused"][0], r)

    d = await tool(session, "describe_addon", addon="rock")
    now = {s["name"]: s["value"] for s in d["settings"]}
    check("nothing changed by any refusal", now[number["name"]] == number["max"] and now[choice["name"]] == choice["options"][-1], now)
    check("no objects made or lost", raw("result = {'n': len(bpy.data.objects)}")["n"] == count)
    r = await tool(session, "run_addon", addon="rock", action="rock.reset_settings", confirm=True)
    check("reset runs with confirm", r["ok"], r)


async def orbiter(session):
    print("orbiter")
    raw("bpy.ops.mesh.primitive_cube_add(); result = {}")
    r = await tool(session, "run_addon", addon="orbiter", action="view3d.orbiter", settings={"speed": 1.0})
    check("starts orbiting", r["ok"] and r["result"] == ["RUNNING_MODAL"], r)
    read = "s = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == 'VIEW_3D').spaces.active.region_3d\nresult = {'q': list(s.view_rotation), 'on': bpy.context.scene.orbiter_settings.is_running}"
    first = raw(read)
    time.sleep(1.5)
    second = raw(read)
    check("the view really turns", first["on"] and first["q"] != second["q"], (first, second))
    r = await tool(session, "run_addon", addon="orbiter", settings={"is_running": False})
    check("stops with a setting", r["ok"], r)
    time.sleep(0.5)
    first = raw(read)
    time.sleep(1)
    second = raw(read)
    check("the view stops turning", not first["on"] and first["q"] == second["q"], (first, second))
    r = await tool(session, "run_addon", addon="orbiter", action="view3d.center_object")
    check("centers", r["ok"], r)


GRAPH_SETUP = """
o = bpy.context.scene.objects.get('Cube') or bpy.data.objects[0]
bpy.context.view_layer.objects.active = o
o.select_set(True)
o.location.x = 0
o.keyframe_insert('location', index=0, frame=1)
o.location.x = 5
o.keyframe_insert('location', index=0, frame=40)
result = {'name': o.name}
"""
GRAPH_KEYS = """
o = bpy.data.objects[{name!r}]
action = o.animation_data.action
slot = o.animation_data.action_slot
curves = action.layers[0].strips[0].channelbag(slot).fcurves
for curve in curves:
    for point in curve.keyframe_points:
        point.select_control_point = True
result = {{'keys': sum(len(c.keyframe_points) for c in curves)}}
"""


async def graph(session):
    print("graph")
    name = raw(GRAPH_SETUP)["name"]
    keys = GRAPH_KEYS.format(name=name)
    check("two keyframes to start", raw(keys)["keys"] == 2)
    r = await tool(session, "run_addon", addon="graph", action="graph.save_selected_points")
    check("saves the keyframes with no Graph Editor open", r["ok"], r)
    r = await tool(session, "run_addon", addon="graph", action="graph.generate_curve")
    check("generates", r["ok"], r)
    d = await tool(session, "describe_addon", addon="graph")
    configs = next(l for l in d["lists"] if l["name"] == "graph_configs")
    check("shows the per graph settings", configs["count"] >= 1 and configs["fields"], configs)
    print("    editor", d["editor"], "graphs", configs["count"], "fields", len(configs["fields"]))
    r = await tool(session, "run_addon", addon="graph", action="graph.generate_curve", settings={"graph_configs[0].preset": "Bounce", "graph_configs[0].strength": 2.0, "graph_configs[0].resolution": 12})
    check("changes a saved graph and generates", r["ok"], r)
    count = raw(keys)["keys"]
    check("keyframes really appear", count > 2, count)
    print("    keyframes", count)
    r = await tool(session, "run_addon", addon="graph", settings={"graph_configs[0].strength": 99.0})
    check("refuses out of range inside a list", not r["ok"], r)
    r = await tool(session, "run_addon", addon="graph", settings={"graph_configs[7].strength": 1.0})
    check("refuses a list item that is not there", not r["ok"], r)
    r = await tool(session, "run_addon", addon="graph", action="graph.clear_generated_points", confirm=True)
    check("clears with confirm", r["ok"], r)
    check("back to two keyframes", raw(keys)["keys"] == 2, raw(keys))


async def sharing():
    print("sharing the socket")
    replies = []
    threads = [threading.Thread(target=lambda i=i: replies.append(raw(f"result = {{'i': {i}}}"))) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    check("six requests at once all answered", sorted(r["i"] for r in replies) == list(range(6)), replies)
    start = time.time()
    raw("import time; time.sleep(35); result = {}")
    check("a 35 second action still gets its answer", time.time() - start >= 35)


async def connected(run):
    params = StdioServerParameters(command=sys.executable, args=["-m", "tfmstyle_agent_tools.server"], env=dict(os.environ))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await run(session)


async def in_window(session):
    names = sorted(t.name for t in (await session.list_tools()).tools)
    check("offers three tools", names == ["describe_addon", "list_addons", "run_addon"], names)
    listed = await tool(session, "list_addons")
    print("   ", listed)
    check("lists the three", [a["addon"] for a in listed["addons"]] == ["graph", "orbiter", "rock"] and listed["has_window"], listed)
    await rock(session)
    await orbiter(session)
    await graph(session)
    await sharing()


async def in_background(session):
    listed = await tool(session, "list_addons")
    check("lists with no window", len(listed["addons"]) == 3 and not listed["has_window"], listed)
    r = await tool(session, "run_addon", addon="rock", action="rock.generate")
    check("generates with no window", r["ok"] and r["new_objects"], r)
    r = await tool(session, "run_addon", addon="orbiter", action="view3d.orbiter")
    check("orbiter refuses cleanly with no window", not r["ok"], r)
    print("   ", r)


async def in_collection(session):
    listed = await tool(session, "list_addons")
    print("   ", listed)
    check("finds them inside the collection", {a["installed_as"] for a in listed["addons"]} == {"collection"} and len(listed["addons"]) == 3, listed)
    d = await tool(session, "describe_addon", addon="rock")
    check("hides the collection's own tools", not [a for a in d["actions"] if a["id"].startswith("tfmstyle")], d["actions"])
    r = await tool(session, "run_addon", addon="rock", action="rock.generate")
    check("generates from the collection", r["ok"] and r["new_objects"], r)


def scenario(title, zips, names, window, run):
    print("==", title)
    home = tempfile.mkdtemp(prefix="tfmat")
    try:
        env = prepare(home, zips, names)
        with Blender(env, window):
            asyncio.run(connected(run))
    finally:
        shutil.rmtree(home, ignore_errors=True)


def main(zips_folder, collection):
    zips = sorted(pathlib.Path(zips_folder).glob("*.zip"))
    separate = ["bl_ext.user_default.tfmstyle_rock", "bl_ext.user_default.orbiter", "bl_ext.user_default.graph_generator"]
    scenario("three separate addons, in a window", zips, separate, True, in_window)
    scenario("three separate addons, no window", zips, separate, False, in_background)
    scenario("inside the collection", [collection], ["bl_ext.user_default.tfmstyle_addon_collection"], True, in_collection)
    print("RESULT", "all passed" if not failed else f"FAILED {failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
