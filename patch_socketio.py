"""
Run this once to patch Flask-SocketIO to work with Flask 3.x:
    python patch_socketio.py
"""
import os
import sys

# Find the flask_socketio __init__.py in the active venv
for path in sys.path:
    candidate = os.path.join(path, "flask_socketio", "__init__.py")
    if os.path.exists(candidate):
        target = candidate
        break
else:
    print("Could not find flask_socketio in sys.path")
    sys.exit(1)

print(f"Patching: {target}")

with open(target, "r", encoding="utf-8") as f:
    src = f.read()

# The broken line assigns to ctx.session which Flask 3 made read-only.
# Replace it with a direct session update instead.
broken = "ctx.session = session_obj"
fixed  = "ctx.session.update(session_obj) if hasattr(ctx, 'session') and ctx.session is not None else None"

if broken not in src:
    print("Patch target not found — may already be patched or version differs.")
    print("Trying alternative pattern...")
    # Some versions use a slightly different line
    broken2 = "            ctx.session = session_obj"
    if broken2 not in src:
        print("Could not find patch target. Check flask_socketio version manually.")
        sys.exit(1)
    src = src.replace(broken2, "            " + fixed)
else:
    src = src.replace(broken, fixed)

with open(target, "w", encoding="utf-8") as f:
    f.write(src)

print("✓ Patched successfully. Restart Flask.")
