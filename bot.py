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

runpy.run_path('core/bot.py')
