#!/bin/sh
# Run both phases, and preserve failure from either one.
export PATH="/app/.venv/bin:$PATH"
status=0
updateloop run || status=1
updateloop run --archive || status=1
exit "$status"
