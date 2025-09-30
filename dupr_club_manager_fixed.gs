/**
 * DUPR Club Manager - Google Apps Script (Fixed Version)
 * Automatically searches DUPR players and adds them to Picklr Thornton club
 * 
 * Features:
 * - Correct column mapping for actual sheet structure
 * - Historical DUPR tracking with vlookup functionality
 * - Notes column with timestamped entries
 * - Fixed club addition API with proper error logging
 * - Test functions for first/last entry
 */

// ===== CONFIGURATION =====
const CONFIG = {
  // Your DUPR API credentials (username/password like duprly.py)
  DUPR_USERNAME: 'YOUR_DUPR_USERNAME_HERE', // Replace with your DUPR email
  DUPR_PASSWORD: 'YOUR_DUPR_PASSWORD_HERE', // Replace with your DUPR password
  
  // Your club information
  CLUB_ID: '5996780750', // Picklr Thornton club ID
  
  // Google Sheets configuration
  DATA_START_ROW: 2, // Row where your data starts (skip header)
  
  // Column mappings (actual sheet structure)
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
  },
  
  // Sheet names
  SHEETS: {
    MAIN: 'Sheet1',           // Main data sheet
    HISTORICAL: 'DUPR_History' // Historical DUPR tracking
  }
};

// ===== MAIN FUNCTIONS =====

/**
 * Setup function - run this first to configure authentication
 */
function setup() {
  console.log('DUPR Club Manager Setup');
  console.log('Please configure your DUPR username/password in the CONFIG section');
  
  // Test the sheet connection
  const mainSheet = SpreadsheetApp.getActiveSheet();
  console.log('Connected to main sheet:', mainSheet.getName());
  
  // Add headers if they don't exist
  setupHeaders(mainSheet);
  
  // Create historical sheet
  createHistoricalSheet();
  
  // Test authentication
  const token = authenticateDUPR();
  if (token) {
    console.log('✅ DUPR authentication successful!');
    PropertiesService.getScriptProperties().setProperty('DUPR_TOKEN', token);
  } else {
    console.log('❌ DUPR authentication failed. Please check your credentials.');
  }
}

/**
 * Main function to process all players in the sheet
 */
function processAllPlayers() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const lastRow = sheet.getLastRow();
  
  if (lastRow < CONFIG.DATA_START_ROW) {
    console.log('No data found in sheet');
    return;
  }
  
  console.log(`Processing ${lastRow - CONFIG.DATA_START_ROW + 1} players...`);
  
  for (let row = CONFIG.DATA_START_ROW; row <= lastRow; row++) {
    try {
      processPlayer(sheet, row);
      // Add a small delay to avoid rate limiting
      Utilities.sleep(1000);
    } catch (error) {
      console.error(`Error processing row ${row}:`, error);
      addNote(sheet, row, `ERROR: ${error.message}`);
      updateCell(sheet, row, CONFIG.COLUMNS.STATUS, 'ERROR: ' + error.message);
    }
  }
  
  console.log('Processing complete!');
}

/**
 * Process a single player
 */
function processPlayer(sheet, row) {
  const firstName = getCellValue(sheet, row, CONFIG.COLUMNS.FIRST_NAME);
  const lastName = getCellValue(sheet, row, CONFIG.COLUMNS.LAST_NAME);
  const email = getCellValue(sheet, row, CONFIG.COLUMNS.EMAIL);
  const phone = getCellValue(sheet, row, CONFIG.COLUMNS.PHONE);
  
  if (!firstName || !lastName) {
    addNote(sheet, row, 'SKIP: Missing name');
    updateCell(sheet, row, CONFIG.COLUMNS.STATUS, 'SKIP: Missing name');
    return;
  }
  
  console.log(`Processing: ${firstName} ${lastName}`);
  addNote(sheet, row, `Started processing ${firstName} ${lastName}`);
  
  // Search for player in DUPR
  const searchResults = searchDUPRPlayer(firstName, lastName);
  
  if (!searchResults || searchResults.length === 0) {
    addNote(sheet, row, 'NOT FOUND: No players found in DUPR search');
    updateCell(sheet, row, CONFIG.COLUMNS.STATUS, 'NOT FOUND');
    return;
  }
  
  // Find best match by email or phone
  const bestMatch = findBestMatch(searchResults, email, phone);
  
  if (!bestMatch) {
    addNote(sheet, row, 'NO MATCH: Email/phone mismatch with search results');
    updateCell(sheet, row, CONFIG.COLUMNS.STATUS, 'NO MATCH: Email/phone mismatch');
    return;
  }
  
  // Update sheet with DUPR data
  updatePlayerData(sheet, row, bestMatch);
  
  // Add to historical tracking
  addToHistorical(firstName, lastName, bestMatch);
  
  // Add player to club
  const addResult = addPlayerToClub(bestMatch.id);
  
  if (addResult) {
    addNote(sheet, row, `SUCCESS: Added ${bestMatch.fullName} (${bestMatch.duprId}) to club`);
    updateCell(sheet, row, CONFIG.COLUMNS.STATUS, 'ADDED TO CLUB');
  } else {
    addNote(sheet, row, `FOUND: Player found but failed to add to club`);
    updateCell(sheet, row, CONFIG.COLUMNS.STATUS, 'FOUND BUT NOT ADDED');
  }
}

// ===== DUPR API FUNCTIONS =====

/**
 * Authenticate with DUPR using username/password (like duprly.py)
 */
function authenticateDUPR() {
  const url = `${CONFIG.DUPR_API_URL || 'https://api.dupr.gg'}/auth/v1.0/login/`;
  
  const payload = {
    email: CONFIG.DUPR_USERNAME,
    password: CONFIG.DUPR_PASSWORD
  };
  
  try {
    const response = UrlFetchApp.fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      payload: JSON.stringify(payload)
    });
    
    if (response.getResponseCode() === 200) {
      const data = JSON.parse(response.getContentText());
      const token = data.result?.accessToken;
      if (token) {
        console.log('Authentication successful');
        return token;
      }
    } else {
      console.error('DUPR authentication failed:', response.getResponseCode(), response.getContentText());
    }
  } catch (error) {
    console.error('Error authenticating with DUPR:', error);
  }
  
  return null;
}

/**
 * Get DUPR authentication token
 */
function getDUPRToken() {
  let token = PropertiesService.getScriptProperties().getProperty('DUPR_TOKEN');
  if (!token) {
    // Try to authenticate if no token exists
    token = authenticateDUPR();
    if (token) {
      PropertiesService.getScriptProperties().setProperty('DUPR_TOKEN', token);
    }
  }
  
  if (!token) {
    throw new Error('DUPR authentication failed. Please check your credentials in CONFIG.');
  }
  return token;
}

/**
 * Search for a player in DUPR
 */
function searchDUPRPlayer(firstName, lastName) {
  const query = `${firstName} ${lastName}`;
  const url = `${CONFIG.DUPR_API_URL || 'https://api.dupr.gg'}/player/v1.0/search`;
  
  const payload = {
    filter: {
      radiusInMeters: 16093400000, // ~10,000 miles
      lat: 39.977763,
      lng: -105.1319296
    },
    includeUnclaimedPlayers: true,
    address: {
      latitude: 39.977763,
      longitude: -105.1319296
    },
    offset: 0,
    limit: 25,
    query: query
  };
  
  try {
    const response = UrlFetchApp.fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getDUPRToken()}`,
        'Content-Type': 'application/json'
      },
      payload: JSON.stringify(payload)
    });
    
    if (response.getResponseCode() === 200) {
      const data = JSON.parse(response.getContentText());
      return data.result?.hits || [];
    } else {
      console.error('DUPR search failed:', response.getResponseCode(), response.getContentText());
      return null;
    }
  } catch (error) {
    console.error('Error searching DUPR:', error);
    return null;
  }
}

/**
 * Add a player to the club (FIXED VERSION)
 */
function addPlayerToClub(playerId) {
  const url = `${CONFIG.DUPR_API_URL || 'https://api.dupr.gg'}/club/${CONFIG.CLUB_ID}/members/v1.0/invite`;
  
  const payload = {
    playerIds: [playerId]
  };
  
  try {
    const response = UrlFetchApp.fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getDUPRToken()}`,
        'Content-Type': 'application/json'
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true // This will prevent exceptions and let us examine the full response
    });
    
    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
    
    console.log(`Club addition response code: ${responseCode}`);
    console.log(`Club addition response: ${responseText}`);
    
    if (responseCode === 200) {
      console.log(`Successfully added player ${playerId} to club`);
      return true;
    } else {
      console.error('Failed to add player to club:', responseCode, responseText);
      return false;
    }
  } catch (error) {
    console.error('Error adding player to club:', error);
    return false;
  }
}

// ===== UTILITY FUNCTIONS =====

/**
 * Find the best matching player from search results
 */
function findBestMatch(searchResults, email, phone) {
  // First, try to match by email
  if (email) {
    const emailMatch = searchResults.find(player => 
      player.email && player.email.toLowerCase() === email.toLowerCase()
    );
    if (emailMatch) return emailMatch;
  }
  
  // Then try to match by phone
  if (phone) {
    const phoneMatch = searchResults.find(player => 
      player.phone && normalizePhone(player.phone) === normalizePhone(phone)
    );
    if (phoneMatch) return phoneMatch;
  }
  
  // If no exact match, return the first result (closest match)
  return searchResults[0];
}

/**
 * Normalize phone number for comparison
 */
function normalizePhone(phone) {
  return phone.replace(/\D/g, '');
}

/**
 * Update player data in the sheet
 */
function updatePlayerData(sheet, row, playerData) {
  const duprId = playerData.duprId || playerData.id;
  const ratings = playerData.ratings || {};
  const doublesRating = ratings.doubles || 'NR';
  
  updateCell(sheet, row, CONFIG.COLUMNS.DUPR_ID, duprId);
  updateCell(sheet, row, CONFIG.COLUMNS.DUPR_RATING, doublesRating);
  updateCell(sheet, row, CONFIG.COLUMNS.TIMESTAMP, new Date());
}

/**
 * Add a note to the notes column with timestamp
 */
function addNote(sheet, row, message) {
  const now = new Date();
  const timestamp = Utilities.formatDate(now, Session.getScriptTimeZone(), 'M/d/yy @ H:mm');
  const note = `[${timestamp}] - ${message}`;
  
  const currentNotes = getCellValue(sheet, row, CONFIG.COLUMNS.NOTES);
  const newNotes = currentNotes ? `${currentNotes}\n${note}` : note;
  
  updateCell(sheet, row, CONFIG.COLUMNS.NOTES, newNotes);
}

/**
 * Add player to historical tracking sheet
 */
function addToHistorical(firstName, lastName, playerData) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let historicalSheet;
  
  try {
    historicalSheet = spreadsheet.getSheetByName(CONFIG.SHEETS.HISTORICAL);
  } catch (error) {
    console.error('Historical sheet not found:', error);
    return;
  }
  
  const duprId = playerData.duprId || playerData.id;
  const ratings = playerData.ratings || {};
  const doublesRating = ratings.doubles || 'NR';
  const singlesRating = ratings.singles || 'NR';
  
  const newRow = [
    new Date(),                    // Timestamp
    firstName,                    // First Name
    lastName,                     // Last Name
    duprId,                       // DUPR ID
    doublesRating,                // Doubles Rating
    singlesRating,                // Singles Rating
    playerData.fullName || '',    // Full Name
    playerData.email || '',       // Email
    playerData.phone || '',       // Phone
    playerData.age || '',         // Age
    playerData.gender || ''       // Gender
  ];
  
  historicalSheet.appendRow(newRow);
}

/**
 * Create historical tracking sheet
 */
function createHistoricalSheet() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  
  // Check if historical sheet already exists
  try {
    spreadsheet.getSheetByName(CONFIG.SHEETS.HISTORICAL);
    console.log('Historical sheet already exists');
    return;
  } catch (error) {
    // Sheet doesn't exist, create it
  }
  
  const historicalSheet = spreadsheet.insertSheet(CONFIG.SHEETS.HISTORICAL);
  
  // Add headers
  const headers = [
    'Timestamp',
    'First Name',
    'Last Name', 
    'DUPR ID',
    'Doubles Rating',
    'Singles Rating',
    'Full Name',
    'Email',
    'Phone',
    'Age',
    'Gender'
  ];
  
  historicalSheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  
  // Format headers
  historicalSheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');
  
  console.log('Created historical tracking sheet');
}

/**
 * Setup headers in the main sheet
 */
function setupHeaders(sheet) {
  const headers = [
    'First Name', 'Last Name', 'Doubles DUPR', 'Email', 'Phone', 'Address', 
    'Membership Plan', 'Full Name', 'Notes', 'DUPR ID', 'DUPR Rating', 'Status', 'Timestamp'
  ];
  
  const headerRow = 1;
  headers.forEach((header, index) => {
    const column = String.fromCharCode(65 + index); // A, B, C, etc.
    const cell = sheet.getRange(`${column}${headerRow}`);
    if (!cell.getValue()) {
      cell.setValue(header);
    }
  });
}

/**
 * Get cell value safely
 */
function getCellValue(sheet, row, column) {
  try {
    return sheet.getRange(`${column}${row}`).getValue();
  } catch (error) {
    return '';
  }
}

/**
 * Update cell value safely
 */
function updateCell(sheet, row, column, value) {
  try {
    sheet.getRange(`${column}${row}`).setValue(value);
  } catch (error) {
    console.error(`Error updating cell ${column}${row}:`, error);
  }
}

// ===== TESTING FUNCTIONS =====

/**
 * Test function to authenticate with DUPR
 */
function testAuth() {
  const token = authenticateDUPR();
  if (token) {
    console.log('✅ Authentication successful!');
    console.log('Token:', token.substring(0, 20) + '...');
    PropertiesService.getScriptProperties().setProperty('DUPR_TOKEN', token);
  } else {
    console.log('❌ Authentication failed');
  }
}

/**
 * Test function to search for a single player
 */
function testSearch() {
  const results = searchDUPRPlayer('Sarah', 'Tripp');
  console.log('Search results:', JSON.stringify(results, null, 2));
}

/**
 * Test function to add a player to club
 */
function testAddToClub() {
  const playerId = '7307629401'; // Sarah Tripp's ID
  const result = addPlayerToClub(playerId);
  console.log('Add to club result:', result);
}

/**
 * Test the FIRST entry in the sheet
 */
function testFirstEntry() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const row = CONFIG.DATA_START_ROW;
  
  console.log(`Testing FIRST entry (row ${row})...`);
  
  const firstName = getCellValue(sheet, row, CONFIG.COLUMNS.FIRST_NAME);
  const lastName = getCellValue(sheet, row, CONFIG.COLUMNS.LAST_NAME);
  
  if (!firstName || !lastName) {
    console.log('❌ First entry has no name data');
    return;
  }
  
  console.log(`Testing: ${firstName} ${lastName}`);
  processPlayer(sheet, row);
}

/**
 * Test the LAST entry in the sheet
 */
function testLastEntry() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const lastRow = sheet.getLastRow();
  
  console.log(`Testing LAST entry (row ${lastRow})...`);
  
  const firstName = getCellValue(sheet, lastRow, CONFIG.COLUMNS.FIRST_NAME);
  const lastName = getCellValue(sheet, lastRow, CONFIG.COLUMNS.LAST_NAME);
  
  if (!firstName || !lastName) {
    console.log('❌ Last entry has no name data');
    return;
  }
  
  console.log(`Testing: ${firstName} ${lastName}`);
  processPlayer(sheet, lastRow);
}

/**
 * Quick test with your sample data
 */
function quickTest() {
  console.log('Running quick test with sample data...');
  
  // Test authentication
  console.log('1. Testing authentication...');
  testAuth();
  
  // Test search
  console.log('2. Testing player search...');
  testSearch();
  
  console.log('Quick test complete!');
}
