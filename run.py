"""Development launcher: python run.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from pixelforge.main import run  # noqa: E402

if __name__ == "__main__":
    run()
