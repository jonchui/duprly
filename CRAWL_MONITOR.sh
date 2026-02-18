#!/bin/bash
# Monitor crawl progress

echo "=========================================="
echo "CRAWL PROGRESS MONITOR"
echo "=========================================="
echo ""

if [ -f crawl_5000_matches.log ]; then
    echo "Latest log entries:"
    echo "---"
    tail -20 crawl_5000_matches.log | grep -E "\[|BATCH|Progress|Found|Stored|reliability|FINISH|STATS" | tail -10
    echo "---"
    echo ""
    echo "Total log lines: $(wc -l < crawl_5000_matches.log)"
    echo ""
    echo "To watch live: tail -f crawl_5000_matches.log"
else
    echo "Log file not found - crawl may not have started yet"
fi

echo ""
echo "Process status:"
ps aux | grep -E "crawl_club_matches" | grep -v grep || echo "No crawl process found"
