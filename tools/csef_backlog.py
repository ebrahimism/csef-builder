"""Launch the canonical controller shipped in the local CSEF build plugin."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "plugins" /
                       "csef-builder" / "skills" / "csef-build" / "scripts" /
                       "backlog.py"), run_name="__main__")
