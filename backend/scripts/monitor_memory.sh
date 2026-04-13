#!/bin/bash
LOG_FILE="${1:-/Users/paulaaron/Miro Fish/MiroFish/backend/logs/memory_monitor.log}"
INTERVAL="${2:-5}"

echo "Memory monitor started at $(date)" > "$LOG_FILE"
echo "Interval: ${INTERVAL}s" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

while true; do
  TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
  
  # Get memory pressure from vm_stat
  VM_STAT=$(vm_stat 2>/dev/null)
  PAGE_SIZE=16384
  
  FREE=$(echo "$VM_STAT" | awk '/Pages free/ {gsub(/\./,"",$3); print $3}')
  ACTIVE=$(echo "$VM_STAT" | awk '/Pages active/ {gsub(/\./,"",$3); print $3}')
  INACTIVE=$(echo "$VM_STAT" | awk '/Pages inactive/ {gsub(/\./,"",$3); print $3}')
  WIRED=$(echo "$VM_STAT" | awk '/Pages wired/ {gsub(/\./,"",$3); print $3}')
  COMPRESSED=$(echo "$VM_STAT" | awk '/Pages occupied by compressor/ {gsub(/\./,"",$6); print $6}')
  SWAPINS=$(echo "$VM_STAT" | awk '/Swapins/ {gsub(/\./,"",$2); print $2}')
  SWAPOUTS=$(echo "$VM_STAT" | awk '/Swapouts/ {gsub(/\./,"",$2); print $2}')
  
  FREE_GB=$(echo "scale=2; $FREE * $PAGE_SIZE / 1073741824" | bc 2>/dev/null || echo "?")
  ACTIVE_GB=$(echo "scale=2; $ACTIVE * $PAGE_SIZE / 1073741824" | bc 2>/dev/null || echo "?")
  WIRED_GB=$(echo "scale=2; $WIRED * $PAGE_SIZE / 1073741824" | bc 2>/dev/null || echo "?")
  COMPRESSED_GB=$(echo "scale=2; $COMPRESSED * $PAGE_SIZE / 1073741824" | bc 2>/dev/null || echo "?")
  
  # Memory pressure
  PRESSURE=$(memory_pressure 2>/dev/null | grep "System-wide" | head -1 || echo "N/A")
  
  # Python processes
  PYTHON_MEM=$(ps aux | grep -E 'python3?\.?1?2?' | grep -v grep | awk '{sum+=$6} END {printf "%.0f", sum/1024}')
  
  echo "[$TIMESTAMP] free=${FREE_GB}GB active=${ACTIVE_GB}GB wired=${WIRED_GB}GB compressed=${COMPRESSED_GB}GB swapins=$SWAPINS swapouts=$SWAPOUTS python_rss=${PYTHON_MEM}MB | $PRESSURE" >> "$LOG_FILE"
  
  sleep "$INTERVAL"
done
