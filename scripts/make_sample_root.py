"""Create a runnable demo TEMPLATES_ROOT at ./sample_root.

Lets you test the whole app without the OneDrive templates:
    python scripts/make_sample_root.py
    # then set TEMPLATES_ROOT=./sample_root in .env (the default)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.fixtures import build_sample_root  # noqa: E402

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent / "sample_root"
    build_sample_root(root)
    print(f"Sample template root created at: {root}")
