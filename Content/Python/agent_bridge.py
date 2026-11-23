# -*- coding: utf-8 -*-
"""Agent bridge: let an external assistant run Python inside the running editor.

Start once per editor session (Output Log, Python mode):
    import agent_bridge

How it works
------------
Every ~0.25 s (on the Slate post-tick callback, i.e. the game thread) it checks
    Saved/AgentBridge/cmd.py
When the content of that file changes, it executes it and writes stdout +
exception traceback to
    Saved/AgentBridge/result.txt
then moves the executed file to
    Saved/AgentBridge/last_cmd.py
A heartbeat is written to Saved/AgentBridge/heartbeat.txt.

Stop it with:
    import agent_bridge; agent_bridge.stop()

Nothing runs unless a command file is written. Safe to leave running for a
session; it does not touch the project on its own.
"""

import unreal
import os
import io
import sys
import time
import builtins
import contextlib
import traceback

BASE = os.path.join(unreal.Paths.project_dir(), "Saved", "AgentBridge")
CMD = os.path.join(BASE, "cmd.py")
RESULT = os.path.join(BASE, "result.txt")
LAST = os.path.join(BASE, "last_cmd.py")
HEART = os.path.join(BASE, "heartbeat.txt")

os.makedirs(BASE, exist_ok=True)

_state = {"hash": None, "last_beat": 0.0}


def _atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    for _ in range(5):
        try:
            os.replace(tmp, path)
            return
        except Exception:
            time.sleep(0.05)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _run_command(src):
    buf = io.StringIO()
    started = time.time()
    status = "OK"
    try:
        code = compile(src, CMD, "exec")
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            exec(code, {"__name__": "__agent_cmd__", "__file__": CMD,
                        "unreal": unreal, "os": os})
    except Exception:
        buf.write("\n" + traceback.format_exc())
        status = "ERROR"
    out = buf.getvalue()
    _atomic_write(RESULT, "STATUS: %s\nELAPSED: %.2fs\n\n%s\n"
                  % (status, time.time() - started, out))
    try:
        os.replace(CMD, LAST)
    except Exception:
        try:
            os.remove(CMD)
        except Exception:
            pass
    unreal.log("[AgentBridge] command %s (%.2fs)" % (status, time.time() - started))


def _tick(delta_seconds):
    try:
        now = time.time()
        if now - _state["last_beat"] > 2.0:
            _state["last_beat"] = now
            _atomic_write(HEART, "alive %.3f\n" % now)
        if not os.path.exists(CMD):
            return
        with open(CMD, "r", encoding="utf-8") as f:
            src = f.read()
        h = hash(src)
        if h == _state["hash"] or not src.strip():
            return
        _state["hash"] = h
        _run_command(src)
    except Exception:
        try:
            _atomic_write(RESULT, "BRIDGE FAILURE\n\n" + traceback.format_exc())
        except Exception:
            pass


def start():
    if getattr(builtins, "_AGENT_BRIDGE_HANDLE", None) is not None:
        unreal.log("[AgentBridge] already running")
        return
    builtins._AGENT_BRIDGE_HANDLE = unreal.register_slate_post_tick_callback(_tick)
    unreal.log("[AgentBridge] started, watching %s" % CMD)


def stop():
    handle = getattr(builtins, "_AGENT_BRIDGE_HANDLE", None)
    if handle is not None:
        unreal.unregister_slate_post_tick_callback(handle)
        builtins._AGENT_BRIDGE_HANDLE = None
        unreal.log("[AgentBridge] stopped")


start()
