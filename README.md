# Blender Agent Tools

One MCP toolbox that lets any agent use the TFMSTYLE Blender addons inside a running Blender.

This is a prototype. It covers **Rock, Orbiter and Graph**. The other addons join as they pass the same test.

## The three tools

| Tool | What it does |
|---|---|
| `list_addons` | The TFMSTYLE addons running in Blender, with their versions |
| `describe_addon` | One addon's actions and settings, with current values and allowed ranges |
| `run_addon` | Applies settings, runs an action, or both |

Settings and ranges are read from Blender at the moment of the call. Nothing is installed in Blender, and the addons themselves do not change.

`describe_addon` leaves out the addon's private state, marks which settings apply to the current choices, and adds a short guide. The guides in `guides.py` are the one part kept by hand, so check them when an addon changes.

`run_addon` checks everything first, and one bad value refuses the whole call. It only runs an addon's own actions. It leaves out anything that imports, exports, opens a file or goes online, an action that clears or resets something needs `confirm=true`, and starting something already running is refused.

`ok` only says the action ran. The reply also measures what changed: size, vertices, lowest point and keyframes, with a warning for a huge mesh or a run that changed nothing.

These tools only run the addons. Use Blender's own MCP tools to delete or move objects, set keyframes, or change the frame.

## What you need

- Blender 5.1 or newer, with the TFMSTYLE addons you want enabled, separately or through the Addon Collection
- The [MCP add-on from Blender Lab](https://www.blender.org/lab/mcp-server/), enabled with its server started
- Python 3.10 or newer

Blender Lab warns that its server runs agent written code with no guards. The checks here cover these three tools only. They do not limit what an agent can do through Blender Lab's own tools.

## Install

```bash
pip install git+https://github.com/TFMSTYLE/Blender_Agent_Tools.git
```

Then add it to your MCP client. For most clients:

```json
{
  "mcpServers": {
    "tfmstyle-blender-tools": {
      "command": "tfmstyle-blender-agent-tools"
    }
  }
}
```

It uses the same `BLENDER_MCP_HOST` and `BLENDER_MCP_PORT` settings as Blender Lab's server, and both can run at once.

## With no window

Background Blender works too, with `blender --background --online-mode --command blender_mcp`. Actions that keep running, like Orbiter's orbit, are refused there because they need an open window.

## Test

```bash
python tests/live_test.py <folder with the three zips> <collection zip>
```

It starts throwaway Blenders with their own settings folder and port, and drives them through a real MCP connection. A Blender you have open is left alone.

## License

GPL 3.0 or later.
