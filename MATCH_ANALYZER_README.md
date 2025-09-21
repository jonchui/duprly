# 🏆 DUPR Match Analyzer

A powerful tool to analyze pickleball matches and predict expected scores using the DUPR API.

## 🚀 Quick Start

### 1. Create a Match Template
```bash
python3 match_analyzer.py create-template
```
This creates `match_template.json` with sample matches.

### 2. Edit the Match File
Edit `match_template.json` with your actual matches:
```json
{
  "matches": [
    {
      "round": "Round 1",
      "team1": ["Player1", "Player2"],
      "team2": ["Player3", "Player4"]
    },
    {
      "round": "Round 2",
      "team1": ["Player5", "Player6"],
      "team2": ["Player7", "Player8"]
    }
  ]
}
```

### 3. Analyze Matches
```bash
python3 match_analyzer.py your_matches.json
```

## 📊 What You Get

For each match, the analyzer provides:

- **Expected Scores**: DUPR's official prediction
- **Predicted Winner**: Based on expected scores
- **Rating Analysis**: Average team ratings
- **Rating Improvement Targets**: What scores to beat for rating gains
- **Strategic Insights**: Whether teams are favored or underdogs

## 🎯 Example Output

```
Round 1
--------------------------------------------------
Team 1: Milos Koprivica & Robert Kuseski
Team 2: Jonathan Chui & Kirk White
  Team 1 Avg Rating: 4.131
  Team 2 Avg Rating: 4.188

📊 Expected Scores:
  Milos Koprivica & Robert Kuseski: 4.5
  Jonathan Chui & Kirk White: 11
🏆 Predicted Winner: Jonathan Chui & Kirk White
   Margin: +6.5 points
   💡 Team 2 favored - win by 6.5+ for max rating gain
```

## 👥 Supported Players

The analyzer includes a database of known players with their DUPR IDs and ratings:

- Jonathan Chui (3.734)
- Kirk White (4.642)
- Milos Koprivica (4.163)
- Robert Kuseski (4.100)
- Thomas Noonan (4.151)
- Michael Fox (4.625)
- Leo Alvarez (3.532)
- Nick Segura (3.816)
- Matthew Stephens (4.488)
- Mike Hedges (4.049)
- Sean Tansey (3.995)
- John Marcelia (4.011)

## 🔧 Adding New Players

To add new players, edit `match_analyzer.py` and add them to the `player_db` and `numeric_ids` dictionaries.

## 📈 Rating Improvement Strategy

- **Beat higher-rated opponents**: Big rating gains
- **Win by larger margins**: Maximize rating improvement
- **Underdog wins**: Significant rating boosts
- **Favored wins**: Modest rating gains

## 🎮 Usage Examples

### Analyze Tournament Matches
```bash
python3 match_analyzer.py tournament_matches.json
```

### Analyze League Matches
```bash
python3 match_analyzer.py league_matches.json
```

### Create Custom Match File
```bash
python3 match_analyzer.py create-template
# Edit match_template.json
python3 match_analyzer.py match_template.json
```

## 🏆 Perfect for:

- Tournament planning
- League match analysis
- Rating improvement tracking
- Match strategy development
- Player development insights

## 📝 Notes

- Requires valid DUPR credentials in `.env` file
- Uses DUPR's official expected score algorithm
- Provides both API-based and rating-based predictions
- Handles unknown players with default ratings

## 🎉 **MATCH ANALYZER COMPLETE!**

I've created a comprehensive match analysis system for you! Here's what you now have:

### ** New Files Created:**
1. **`match_analyzer.py`** - Standalone match analysis tool
2. **`match_template.json`** - Template for creating match files
3. **`upcoming_matches.json`** - Your actual upcoming matches
4. **`MATCH_ANALYZER_README.md`** - Complete documentation

### **🚀 How to Use:**

#### **1. Create Match Files:**
```bash
python3 match_analyzer.py create-template
```

#### **2. Analyze Any Matches:**
```bash
python3 match_analyzer.py upcoming_matches.json
```

### **🎯 What It Does:**
- **Analyzes any set of matches** from a JSON file
- **Gets expected scores** from DUPR's official API
- **Shows rating improvement targets** for each match
- **Provides strategic insights** (favored vs underdog)
- **Handles unknown players** with default ratings

### **📊 Example Output:**
```
Round 1
Team 1: Milos Koprivica & Robert Kuseski (4.131 avg)
Team 2: Jonathan Chui & Kirk White (4.188 avg)

📊 Expected Scores:
  Milos Koprivica & Robert Kuseski: 4.5
  Jonathan Chui & Kirk White: 11
🏆 Predicted Winner: Jonathan Chui & Kirk White
   Margin: +6.5 points
   💡 Team 2 favored - win by 6.5+ for max rating gain
```

### **🏆 Perfect For:**
- **Tournament planning** - analyze all upcoming matches
- **League analysis** - track rating improvement opportunities  
- **Match strategy** - know which matches to focus on
- **Player development** - understand rating implications

### ** Key Features:**
- **Uses your correct DUPR ID (0YVNWN)** and rating (3.734)
- **Includes all your player pool** with current ratings
- **Provides both API and rating-based predictions**
- **Easy to extend** with new players
- **Comprehensive documentation**

Now you can easily analyze any set of matches by creating a JSON file and running the analyzer! 🚀
