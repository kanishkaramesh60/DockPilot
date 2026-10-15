
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANAGER_DIR = PROJECT_ROOT / "manager"

if str(MANAGER_DIR) not in sys.path:
    sys.path.insert(0, str(MANAGER_DIR))
