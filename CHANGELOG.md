# Changelog

## 0.2.0

- describe_addon now leaves out private settings, marks which settings apply, shows Graph's settings on an empty scene, and adds a short guide per addon
- run_addon now reports size, vertices, lowest point and keyframes for what changed
- Warns about huge meshes and about runs that changed nothing
- Refuses private settings, and refuses to start something already running
- Replies no longer carry an addon's debug text

## 0.1.0

- First prototype, with three tools: list_addons, describe_addon and run_addon
- Covers Rock, Orbiter and Graph, installed separately or through the Addon Collection
- Reads settings and ranges from Blender at the moment of the call
- Refuses anything that is not an addon's own action, and any value out of range
