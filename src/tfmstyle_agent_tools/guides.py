# SPDX-FileCopyrightText: 2026 The French Monkey
# SPDX-License-Identifier: GPL-3.0-or-later

"""What a person learns by looking at an addon's panel, written down for an agent.

Settings and ranges come live from Blender. This is the one part that is kept by hand,
because Blender cannot say how an addon is meant to be used, so check it against the
addon when the addon changes. A note about a fault says what happens today.
"""

GUIDES = {
    "rock": {
        "actions": {
            "rock.generate": "Makes a new rock, or updates the rock that is selected",
            "rock.randomize_seed": "Picks a new random seed",
            "rock.reset_settings": "Puts every setting back to its default",
        },
        "notes": [
            "The rock's origin is its centre. Use lowest_z in the reply to rest it on the ground, with Blender's own tools.",
            "base_shape CUBE chips well. SPHERE barely chips at usual settings and can come back as a smooth ball.",
            "size is the edge length on CUBE and the radius on SPHERE, so SPHERE comes out about twice as wide.",
            "Start with adaptive_subdiv off, whatever its description says. With it on, raising chip_layers from 30 to 48 took one rock from about 11,000 vertices to well over 100,000.",
            "chip_radius works the other way round from its description: a lower value cuts less.",
            "Read size and vertices in the reply after every run, because a run can succeed and still not look like what was asked for.",
        ],
    },
    "orbiter": {
        "actions": {
            "view3d.orbiter": "Starts orbiting the view around the active object, and keeps running",
            "view3d.center_object": "Frames the active object in the view",
            "view3d.toggle_fullscreen": "Turns full screen on or off",
        },
        "notes": [
            "Select the object first: it orbits the active object.",
            "To stop it, set is_running to false. Starting it again while it runs is refused.",
            "speed 0.1 is about 6 degrees a second, one turn a minute.",
            "recenter_distance is how far away the view sits when it starts. Set it larger than the object or the view starts inside it.",
            "It centres on where the object is when it starts, and does not follow an object that moves afterwards.",
        ],
    },
    "graph": {
        "actions": {
            "graph.save_selected_points": "Saves the selected keyframes as the two ends of a graph",
            "graph.generate_curve": "Fills in keyframes between the saved ends, using that graph's settings",
            "graph.clear_generated_points": "Removes the generated keyframes and leaves the saved ends",
            "graph.clear_saved_points": "Deletes the selected saved graph",
            "graph.clear_all_saved_graphs": "Deletes every saved graph",
        },
        "notes": [
            "Graph works on keyframes that already exist, and this toolbox cannot make them. Use Blender's own tools for the first step.",
            "Step 1: on the active object, insert keyframes at the two ends and select them (select_control_point on each point). Step 2: graph.save_selected_points. Step 3: graph.generate_curve, which creates entry 0 in graph_configs. Step 4: set its settings by name, like graph_configs[0].preset, and run graph.generate_curve again.",
            "strength starts at 0, which adds no visible motion. Raise it.",
            "Only settings with applies true do anything for the chosen preset. The Bounce preset uses bounce_amount: bounce_count belongs to Spring.",
            "The Bounce preset has rounded dips and sharp peaks, and only the last frame reaches the end value. It looks like a wobble settling, so say so if asked for a hard impact.",
            "Bounce can overshoot the end value: with 3 bounces, strength above about 1.2 goes past it. Check lowest and highest under keyframes in the reply.",
            "ease-out-bounce under the Preset source is one overshoot, not a bounce.",
            "With Live Update on, changing a setting regenerates straight away.",
        ],
    },
}
