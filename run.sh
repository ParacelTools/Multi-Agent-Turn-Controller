#!/bin/bash
echo "== Parachat launcher =="

# Create .venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "-- Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install req if not installed
pip install -r requirements.txt

# Run app.py
echo "-- Launching app.py ..."
python3 app.py
