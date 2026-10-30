# SPDX-FileCopyrightText: 2026 The French Monkey
# SPDX-License-Identifier: GPL-3.0-or-later

"""Talks to Blender through the local socket that Blender Lab's MCP add-on opens.

It reads the same two settings as Blender Lab's server, so both can share one Blender.
"""

import json
import os
import socket

# Blender Lab's server allows the same. A big generate holds the reply until it ends.
TIMEOUT = 300.0


def run(code):
    """Run Python inside Blender and return its `result` dict."""
    host = os.environ.get("BLENDER_MCP_HOST", "localhost")
    port = int(os.environ.get("BLENDER_MCP_PORT", "9876"))
    request = json.dumps({"type": "execute", "code": code, "strict_json": True}) + "\0"
    buf = bytearray()
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT) as sock:
            sock.sendall(request.encode("utf-8"))
            while b"\0" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf.extend(chunk)
    except OSError as e:
        raise ConnectionError(
            f"Could not reach Blender at {host}:{port} ({e}). Blender must be open, with "
            "the MCP add-on from Blender Lab enabled and its server started."
        ) from e
    if not buf:
        raise ConnectionError("Blender closed the connection without replying")
    reply = json.loads(buf.partition(b"\0")[0].decode("utf-8"))
    if reply.get("status") != "ok":
        raise RuntimeError(reply.get("message", "Blender reported an error"))
    return reply["result"]
