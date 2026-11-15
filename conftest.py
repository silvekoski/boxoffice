"""pytest: make `aaltonomous` (upstream/, fetched by scripts/fetch_upstream.sh) and `sorter` importable."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (HERE, HERE / "upstream"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
