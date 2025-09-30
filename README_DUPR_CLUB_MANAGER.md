# DUPR Club Manager

A comprehensive Google Apps Script solution for automatically managing DUPR (Dynamic Universal Pickleball Rating) club members. This tool searches for players in DUPR, verifies their identity, tracks historical ratings, and automatically adds them to your club.

## 🎯 Features

- **🔍 Automatic Player Search**: Searches DUPR by first/last name with location-based filtering
- **✅ Identity Verification**: Matches players by email/phone to ensure accuracy
- **📊 Historical Tracking**: Maintains complete DUPR rating history with vlookup functionality
- **📝 Detailed Logging**: Timestamped notes for every action and error
- **🏆 Club Management**: Automatically adds verified players to your DUPR club
- **🧪 Testing Tools**: Built-in functions to test first/last entries
- **🛡️ Error Handling**: Comprehensive error logging with full API response details

## 📋 Prerequisites

- Google Sheets account
- DUPR account with club admin/edit rights
- Access to Google Apps Script

## 🚀 Quick Start

### 1. Setup Your Environment

```bash
# Copy the environment template
cp env.example .env

# Edit .env with your DUPR credentials
nano .env
```

Update the `.env` file with your actual DUPR credentials:
```env
DUPR_USERNAME=your_email@example.com
DUPR_PASSWORD=your_password_here
DUPR_CLUB_ID=YOUR_CLUB_ID_HERE
```

### 2. Google Apps Script Setup

1. **Open your Google Sheet** with player data
2. **Go to Extensions > Apps Script**
3. **Replace the default code** with the content from `dupr_club_manager_fixed.gs`
4. **Update the CONFIG section** with your credentials:

```javascript
const CONFIG = {
  DUPR_USERNAME: 'your_email@example.com',
  DUPR_PASSWORD: 'your_password_here',
  CLUB_ID: 'YOUR_CLUB_ID_HERE', // Your club ID
  // ... rest of config
};
```

### 3. Sheet Structure

Your Google Sheet should have the following columns:

| A | B | C | D | E | F | G | H | I | J | K | L | M |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| First Name | Last Name | Doubles DUPR | Email | Phone | Address | Membership Plan | Full Name | Notes | DUPR ID | DUPR Rating | Status | Timestamp |

**Note**: Columns I-M are automatically populated by the script.

## 🔧 Usage

### Initial Setup

```javascript
// Run this first to configure authentication and create historical sheet
setup()
```

### Testing Functions

```javascript
// Test authentication
testAuth()

// Test player search
testSearch()

// Test club addition
testAddToClub()

// Test first entry in your sheet
testFirstEntry()

// Test last entry in your sheet
testLastEntry()

// Run all tests
quickTest()
```

### Processing Players

```javascript
// Process all players in your sheet
processAllPlayers()

// Process a specific row
processPlayer(sheet, rowNumber)
```

## 📊 Historical Tracking

The script automatically creates a `DUPR_History` sheet that tracks:

- **Timestamp**: When the lookup was performed
- **Player Info**: Name, DUPR ID, ratings, contact info
- **Complete Records**: Every lookup creates a historical entry

### Using Historical Data

You can use vlookup formulas to get the latest DUPR information:

```excel
=VLOOKUP(A2,DUPR_History!B:M,3,FALSE)  // Get latest DUPR ID
=VLOOKUP(A2,DUPR_History!B:M,5,FALSE)  // Get latest doubles rating
```

## 📝 Notes System

The Notes column (I) automatically logs:

- **Format**: `[9/28/25 @ 7:16] - [action description]`
- **Actions**: Processing start, search results, success/failure
- **Errors**: Detailed error messages with timestamps
- **Cumulative**: Notes append to existing entries

## 🛠️ Configuration

### Column Mappings

The script expects specific column positions. Update `CONFIG.COLUMNS` if your sheet structure differs:

```javascript
COLUMNS: {
  FIRST_NAME: 'A',      // First Name
  LAST_NAME: 'B',       // Last Name  
  DOUBLES_DUPR: 'C',    // Doubles DUPR (existing)
  EMAIL: 'D',           // Email
  PHONE: 'E',          // Phone
  ADDRESS: 'F',         // Address
  MEMBERSHIP_PLAN: 'G', // Membership Plan
  FULL_NAME: 'H',       // Full Name
  NOTES: 'I',           // Notes column (new)
  DUPR_ID: 'J',         // DUPR ID (new)
  DUPR_RATING: 'K',     // DUPR Rating (new)
  STATUS: 'L',          // Status (new)
  TIMESTAMP: 'M'        // Timestamp (new)
}
```

### API Configuration

```javascript
const CONFIG = {
  DUPR_USERNAME: 'your_email@example.com',
  DUPR_PASSWORD: 'your_password_here',
  CLUB_ID: 'YOUR_CLUB_ID_HERE',
  DATA_START_ROW: 2, // Row where your data starts (skip header)
  SHEETS: {
    MAIN: 'Sheet1',
    HISTORICAL: 'DUPR_History'
  }
};
```

## 🔍 How It Works

1. **Authentication**: Uses DUPR username/password (same as `duprly.py`)
2. **Player Search**: Searches DUPR by name with location-based filtering
3. **Identity Verification**: Matches by email/phone to ensure correct player
4. **Data Population**: Fills in DUPR ID, rating, and timestamp
5. **Historical Tracking**: Adds entry to `DUPR_History` sheet
6. **Club Addition**: Automatically adds verified players to your club
7. **Logging**: Records all actions with timestamps in Notes column

## 🐛 Troubleshooting

### Common Issues

**Authentication Failed**
- Check your DUPR username/password in CONFIG
- Ensure your DUPR account is active
- Run `testAuth()` to verify credentials

**Player Not Found**
- Check spelling of first/last name
- Verify player exists in DUPR
- Try different name variations

**Club Addition Failed**
- Verify you have admin rights to the club
- Check club ID is correct
- Review error logs in Notes column

**API Errors**
- The script uses `muteHttpExceptions: true` for detailed error logging
- Check console logs for full API response
- Verify DUPR API is accessible

### Debug Functions

```javascript
// Test authentication
testAuth()

// Test search with specific player
searchDUPRPlayer('John', 'Doe')

// Test club addition with specific player ID
addPlayerToClub('1234567890')
```

## 📈 Example Workflow

1. **Setup**: Run `setup()` to initialize
2. **Test**: Run `testFirstEntry()` to verify functionality
3. **Process**: Run `processAllPlayers()` to process all data
4. **Review**: Check Notes column for detailed logs
5. **Historical**: Use `DUPR_History` sheet for vlookup formulas

## 🔒 Security Notes

- **Credentials**: Store DUPR credentials securely in CONFIG section
- **Permissions**: Only share with trusted users who have club admin rights
- **API Limits**: Script includes rate limiting to avoid API throttling

## 📚 Related Files

- `dupr_club_manager_fixed.gs` - Main Google Apps Script
- `env.example` - Environment configuration template
- `duprly.py` - Python reference implementation
- `dupr_client.py` - DUPR API client library

## 🤝 Contributing

This script is designed for DUPR club management. To adapt for your club:

1. Update `CLUB_ID` in CONFIG
2. Modify column mappings if needed
3. Adjust location coordinates for player search
4. Test with your specific data structure

## 📞 Support

For issues or questions:
1. Check the Notes column for detailed error logs
2. Run test functions to isolate problems
3. Review console logs for API response details
4. Verify DUPR account permissions and club access

---

**Happy Pickleballing! 🏓**
