"""
Entry point for the GentelmeN@CorE Telegram bot.

The bot logic has been refactored into the core/ package:
  core/bot.py         - Bot initialisation and polling loop
  core/commands.py    - Command and message handlers
  core/database.py    - Database setup and queries
  core/helpers.py     - Shared utility functions
  core/integrations.py - External API integrations (KuCoin, Brave, HuggingFace)
"""
import runpy
from pathlib import Path

base_dir = Path(__file__).resolve().parent
runpy.run_path(str(base_dir / "core" / "bot.py"))
