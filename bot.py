import runpy
from pathlib import Path

base_dir = Path(__file__).resolve().parent
core_bot_path = base_dir / "core" / "bot.py"
runpy.run_path(str(core_bot_path))
