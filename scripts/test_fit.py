#!/usr/bin/env python3
import csv
import numpy as np

with open('test_output.txt', 'w') as out:
    out.write("Loading CSV...\n")
    out.flush()
with open('match_rating_data.csv') as f:
    reader = csv.DictReader(f)
    data = []
    for r in reader:
        try:
            data.append({
                'r1': float(r['r1']), 'r2': float(r['r2']),
                'r3': float(r['r3']), 'r4': float(r['r4']),
                'imp1': float(r['imp1']), 'imp2': float(r['imp2']),
                'imp3': float(r['imp3']), 'imp4': float(r['imp4']),
                'games1': int(r['games1']), 'games2': int(r['games2']),
                'winner': int(r['winner']),
            })
        except:
            continue

    out.write(f"Loaded {len(data)} matches\n")
    out.write(f"Sample impact range: {min(d['imp1'] for d in data):.6f} to {max(d['imp1'] for d in data):.6f}\n")
    out.write("Test complete - data loads OK\n")
