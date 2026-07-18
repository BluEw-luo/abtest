#!/usr/bin/env bash
# abtest - convenience launcher for the AB blind comparison tool
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$HOME/.abtest-venv/bin/python3" "$DIR/abtest.py" "$@"
