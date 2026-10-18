"""Run publisher + listener in parallel; reload deployed source without a build.

Uses only the standard library, including when an older Brick image is cached.
"""
import hashlib
from pathlib import Path
import signal
import subprocess
import sys
import time

APP_DIRECTORY = Path(__file__).resolve().parent
stopping = False


def source_revision():
    digest = hashlib.sha256()
    for path in sorted(APP_DIRECTORY.rglob("*.py")):
        digest.update(str(path.relative_to(APP_DIRECTORY)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def request_stop(signum, frame):
    global stopping
    stopping = True


def stop_children(children):
    for child in children:
        if child.poll() is None:
            child.send_signal(signal.SIGINT)
    deadline = time.monotonic() + 5
    for child in children:
        try:
            child.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()


def main():
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    while not stopping:
        try:
            revision = source_revision()
        except OSError:
            time.sleep(0.5)  # Deployment may be replacing the directory.
            continue
        print(f"[ROS runtime] Source revision {revision}; starting publisher + listener", flush=True)
        children = []
        reload_source = False
        try:
            for script in ("ros_sensor.py", "ros_listener.py"):
                children.append(subprocess.Popen([sys.executable, "-u", str(APP_DIRECTORY / script)]))
            while not stopping:
                time.sleep(0.5)
                try:
                    changed = source_revision() != revision
                except OSError:
                    continue
                if changed:
                    # Allow a group of files to finish uploading before restarting.
                    time.sleep(1.0)
                    print("[ROS runtime] Deployed source changed; reloading", flush=True)
                    reload_source = True
                    break
                if any(child.poll() is not None for child in children):
                    print("[ROS runtime] A ROS process exited; restarting both in 2 s", flush=True)
                    break
        finally:
            stop_children(children)
        if reload_source and not stopping:
            # Also picks up changes to this supervisor itself.
            import os
            os.execv(sys.executable, [sys.executable, "-u", str(APP_DIRECTORY / "run.py")])
        if not stopping:
            time.sleep(2.0)


if __name__ == "__main__":
    main()
