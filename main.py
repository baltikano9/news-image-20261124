"""Copy the pre-rendered entry.png byte-for-byte into $MAKEFUN_OUTPUT_DIR (default: out).

Standard library only; no network. The image itself is drawn by render.py.
"""
import os
import sys


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "out"
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(here, "entry.png"), "rb") as f:
        data = f.read()
    with open(os.path.join(out_dir, "entry.png"), "wb") as f:
        f.write(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
