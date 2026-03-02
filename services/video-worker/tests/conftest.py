from __future__ import annotations

import sys
from pathlib import Path

# Ensure `import video_worker` works when running from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
