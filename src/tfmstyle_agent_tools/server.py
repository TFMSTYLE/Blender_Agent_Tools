# SPDX-FileCopyrightText: 2026 The French Monkey
# SPDX-License-Identifier: GPL-3.0-or-later

"""The MCP server. Three tools, so an agent loads three descriptions rather than one
for every action of every addon, and asks for an addon's details when it needs them."""

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import bridge
from .guides import GUIDES

CODE = Path(__file__).with_name("inside.py").read_text(encoding="utf-8")

mcp = FastMCP(
    "tfmstyle-blender-agent-tools",
    instructions=(
        "Uses the TFMSTYLE addons in a running Blender. Start with list_addons, then "
        "describe_addon before the first run_addon of an addon, and follow its guide: "
        "settings and ranges are read from Blender and can differ between versions. "
        "These tools only run the addons. Use Blender's own tools to delete or move "
        "objects, set keyframes, or change the frame."
    ),
)


def call(function, **kwargs):
    return bridge.run(f"{CODE}\nresult = {function}(**json.loads({json.dumps(kwargs)!r}))")


@mcp.tool(annotations=ToolAnnotations(title="List TFMSTYLE addons", readOnlyHint=True))
def list_addons() -> dict:
    """List the TFMSTYLE addons running in Blender, with their versions."""
    return call("list_addons")


@mcp.tool(annotations=ToolAnnotations(title="Describe a TFMSTYLE addon", readOnlyHint=True))
def describe_addon(addon: str) -> dict:
    """Show one addon's actions and settings, with current values, ranges and a guide.

    `applies` says whether a setting does anything for the current choices.
    Settings kept per item appear under `lists`, for example one set per saved graph.
    Set those with the name list[index].setting.
    """
    reply = call("describe_addon", addon=addon)
    guide = GUIDES.get(addon)
    if guide and "actions" in reply:
        for action in reply["actions"]:
            action["description"] = action["description"] or guide["actions"].get(action["id"], "")
        reply["guide"] = guide["notes"]
    return reply


@mcp.tool(annotations=ToolAnnotations(title="Run a TFMSTYLE addon", destructiveHint=True))
def run_addon(addon: str, action: str = "", settings: dict | None = None, confirm: bool = False) -> dict:
    """Apply settings to an addon, run one of its actions, or both.

    Everything is checked first: one bad value refuses the whole call and changes
    nothing. An action that clears or resets something needs confirm=true.
    Settings stay as set, the same as if a person had moved the slider.

    The reply measures what changed: size, vertices, lowest_z and keyframes under
    new_objects and changed_objects. ok only says the action ran, so read those and
    any warnings to judge the result.
    """
    return call("run_addon", addon=addon, action=action, settings=settings, confirm=confirm)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
