# DUPR Score Monitor & iMessage Notifier

A Python script that monitors Trevor, Jared, and Jon's DUPR scores every 60 seconds and sends iMessage notifications when scores change, with special focus on tracking when the combined score drops below 11.3 for the MILP tournament registration.

## Features

- **Real-time Monitoring**: Checks DUPR scores every 60 seconds
- **Change Detection**: Notifies when any player's score changes
- **Target Tracking**: Monitors when combined score drops below 11.3
- **Match Processing**: Tracks specific match (QPENOLOGN) for processing status
- **Rating Estimation**: Predicts rating changes based on match results
- **iMessage Integration**: Sends notifications to multiple phone numbers
- **Smart Notifications**: Context-aware messages with gap analysis

## Current Status

**Players Being Monitored:**
- Trevor Jin (PKQX0G): 4.049
- Jared FuelBerth (W6YQXG): 3.757  
- Jon Chui (0YVNWN): 3.891
- **Combined Score: 11.697** (over by 0.397)

**Target:** 11.3 (for MILP tournament registration)

## Files

- `dupr_monitor.py` - Main monitoring script with iMessage integration
- `dupr_monitor_test.py` - Test version that logs to console (no iMessage)
- `imessage_client.py` - iMessage MCP server client wrapper
- `com.duprly.monitor.plist` - macOS launchd configuration for auto-start

## Setup

### Prerequisites

1. **DUPR API Credentials**: Set up `.env` file with:
   ```bash
   DUPR_USERNAME=your_email@example.com
   DUPR_PASSWORD=your_password
   ```

2. **iMessage MCP Server**: Running on localhost:3000
   - API Key: `imessage-mcp-2024-secure-key`
   - Recipients: `+16504507174`, `+14242412484`

### Installation

1. **Install Dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Test the System**:
   ```bash
   # Test version (no iMessage, limited iterations)
   python3 dupr_monitor_test.py
   
   # Full version (with iMessage, continuous)
   python3 dupr_monitor.py
   ```

## Usage

### Running the Monitor

**Test Mode** (recommended for initial testing):
```bash
python3 dupr_monitor_test.py
```
- Runs 3 monitoring cycles
- Logs notifications to console
- No iMessage dependency

**Production Mode**:
```bash
python3 dupr_monitor.py
```
- Runs continuously
- Sends iMessage notifications
- Requires iMessage MCP server

### macOS Auto-Start (Future)

For deployment on iMac that stays on:

1. **Copy plist file**:
   ```bash
   sudo cp com.duprly.monitor.plist /Library/LaunchDaemons/
   ```

2. **Load the service**:
   ```bash
   sudo launchctl load /Library/LaunchDaemons/com.duprly.monitor.plist
   ```

3. **Check status**:
   ```bash
   sudo launchctl list | grep duprly
   ```

## Notification Examples

**Score Change Notification:**
```
🏓 DUPR Update!
Trevor: 4.049 → 4.012 (-0.037)
Jared: 3.757 → 3.720 (-0.037)
Jon: 3.891 → 3.925 (+0.034)
Combined: 11.697 → 11.657
Gap to 11.3: +0.357 (still over)
Uncounted matches: 1
Estimated changes when processed:
  Jon: +0.035
  Jared: -0.045
  Trevor: -0.045
```

**Target Reached Notification:**
```
🎯 TARGET REACHED!
Combined DUPR: 11.28
You're now 0.02 UNDER 11.3!
Register NOW: go.picklr.site/milp

Current scores:
Trevor: 4.012
Jared: 3.720
Jon: 3.925
```

## Match Tracking

The system tracks match `QPENOLOGN` (Jon & Blair vs Jared/Trevor):
- **Result**: Jon & Blair won 11-7, 11-6
- **Status**: Not yet processed by DUPR
- **Estimated Impact**: 
  - Jon: +0.035 (beat higher rated)
  - Jared: -0.045 (lost as expected)
  - Trevor: -0.045 (lost as expected)
- **New Estimated Sum**: ~11.63-11.66 (still over by 0.33-0.36)

## Technical Details

- **Polling Interval**: 60 seconds
- **API Endpoints**: DUPR API v1.0
- **Player IDs**: Uses numeric IDs (not short codes)
- **Change Detection**: Floating point precision (0.001 threshold)
- **Logging**: Rotating daily logs with 7-day retention
- **Error Handling**: Continues monitoring on API errors

## Troubleshooting

**iMessage Not Working:**
- Ensure Messages.app is running
- Check iMessage MCP server is running on localhost:3000
- Verify phone numbers are in correct format (+1XXXXXXXXXX)
- Use test version for debugging

**DUPR API Issues:**
- Check `.env` file has correct credentials
- Verify internet connection
- Check DUPR API status

**Permission Issues:**
- Ensure Python has network access
- Check file permissions for log files
- Verify launchd permissions for auto-start

## Future Enhancements

- **Web Dashboard**: Real-time score display
- **Multiple Teams**: Monitor different player combinations
- **Custom Thresholds**: Set different target scores
- **Historical Tracking**: Store score change history
- **Push Notifications**: Alternative to iMessage
- **Tournament Integration**: Direct registration links
