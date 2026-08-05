#!/usr/bin/env bash
set -e
python3 -m venv venv 2>/dev/null || true
source venv/bin/activate
pip install -U pip
pip install -r requirements.txt
python3 bot.py
