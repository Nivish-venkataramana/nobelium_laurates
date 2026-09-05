#!/usr/bin/env bash
# stop.sh — Stop all Autonomous QA Platform services
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="$ROOT/logs"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${YELLOW}Stopping Autonomous QA Platform services...${NC}"

stopped=0
for svc in backend worker frontend demo-app; do
  pidfile="$LOGS/$svc.pid"
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    if kill "$pid" 2>/dev/null; then
      echo -e "  ${GREEN}✓${NC} Stopped $svc (pid $pid)"
      ((stopped++)) || true
    else
      echo "  ⚠ $svc was not running (pid $pid)"
    fi
    rm -f "$pidfile"
  else
    echo "  – $svc: no pid file found"
  fi
done

echo ""
echo -e "${GREEN}Done — $stopped service(s) stopped.${NC}"
echo -e "PostgreSQL and Redis are still running (managed by Homebrew)."
echo -e "To stop them too: ${YELLOW}brew services stop postgresql@16 redis${NC}"
