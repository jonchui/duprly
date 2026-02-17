#!/usr/bin/env python3
"""Visualize DUPR rating distribution for Picklr club members"""

import re
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

# Read the club members data
data_file = "/Users/jonchui/.cursor/projects/Users-jonchui-Documents-Documents-Jon-s-MacBook-Pro-4-GitHub-duprly/agent-tools/42efc4d8-0ee0-4383-b2a7-898c4812f982.txt"

ratings = []
with open(data_file, 'r') as f:
    content = f.read()
    # Extract doubles ratings using regex: "Doubles: X.XXX"
    pattern = r'Doubles: ([\d.]+)'
    matches = re.findall(pattern, content)
    for match in matches:
        try:
            rating = float(match)
            if rating > 0:  # Filter out invalid ratings
                ratings.append(rating)
        except ValueError:
            pass

print(f"Found {len(ratings)} members with valid doubles ratings")

# Create bins every 0.1 from min to max
min_rating = min(ratings)
max_rating = max(ratings)
# Round to nearest 0.1 for cleaner bins
min_bin = np.floor(min_rating * 10) / 10
max_bin = np.ceil(max_rating * 10) / 10
bins = np.arange(min_bin, max_bin + 0.1, 0.1)

# Create histogram
plt.figure(figsize=(14, 8))
counts, edges, patches = plt.hist(ratings, bins=bins, edgecolor='black', alpha=0.7, color='steelblue')

# Customize the plot
plt.xlabel('DUPR Doubles Rating', fontsize=12, fontweight='bold')
plt.ylabel('Number of Members', fontsize=12, fontweight='bold')
plt.title(f'Picklr Club DUPR Rating Distribution\n({len(ratings)} members with ratings)', fontsize=14, fontweight='bold')
plt.grid(axis='y', alpha=0.3, linestyle='--')

# Add value labels on top of bars
for i, (count, edge) in enumerate(zip(counts, edges[:-1])):
    if count > 0:
        plt.text(edge + 0.05, count + 0.5, str(int(count)), 
                ha='center', va='bottom', fontsize=8)

# Rotate x-axis labels for readability
plt.xticks(bins[::2], rotation=45, ha='right')  # Show every other bin label

# Add statistics text box
mean_rating = np.mean(ratings)
median_rating = np.median(ratings)
std_rating = np.std(ratings)
stats_text = f'Mean: {mean_rating:.2f}\nMedian: {median_rating:.2f}\nStd Dev: {std_rating:.2f}'
plt.text(0.02, 0.98, stats_text, transform=plt.gca().transAxes,
         fontsize=10, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()
output_file = 'picklr_club_rating_distribution.png'
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\nChart saved to: {output_file}")
print(f"\nStatistics:")
print(f"  Total members with ratings: {len(ratings)}")
print(f"  Mean rating: {mean_rating:.2f}")
print(f"  Median rating: {median_rating:.2f}")
print(f"  Standard deviation: {std_rating:.2f}")
print(f"  Min rating: {min_rating:.2f}")
print(f"  Max rating: {max_rating:.2f}")

plt.show()
