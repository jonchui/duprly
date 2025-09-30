/**
 * DUPR Club Manager - Google Apps Script (Updated with Username/Password Auth)
 * Automatically searches DUPR players and adds them to Picklr Thornton club
 *
 * Setup Instructions:
 * 1. Open Google Sheets with your player data
 * 2. Go to Extensions > Apps Script
 * 3. Replace the default code with this script
 * 4. Update the configuration section below
 * 5. Run the setup function first to configure authentication
 */

// ===== CONFIGURATION =====
const CONFIG = {
  // Your DUPR API credentials (username/password like duprly.py)
  DUPR_USERNAME: "YOUR_DUPR_USERNAME_HERE", // Replace with your DUPR email
  DUPR_PASSWORD: "YOUR_DUPR_PASSWORD_HERE", // Replace with your DUPR password

  // Your club information
  CLUB_ID: "5996780750", // Picklr Thornton club ID

  // Google Sheets configuration
  SHEET_NAME: "Sheet1", // Change to your sheet name
  DATA_START_ROW: 2, // Row where your data starts (skip header)

  // Column mappings (actual sheet structure)
  COLUMNS: {
    FIRST_NAME: "A", // First Name
    LAST_NAME: "B", // Last Name
    DOUBLES_DUPR: "C", // Doubles DUPR (existing)
    EMAIL: "D", // Email
    PHONE: "E", // Phone
    ADDRESS: "F", // Address
    MEMBERSHIP_PLAN: "G", // Membership Plan
    FULL_NAME: "H", // Full Name
    NOTES: "I", // Notes column (new)
    DUPR_ID: "J", // DUPR ID (new)
    DUPR_RATING: "K", // DUPR Rating (new)
    STATUS: "L", // Status (new)
    TIMESTAMP: "M", // Timestamp (new)
  },

  // Sheet names
  SHEETS: {
    MAIN: "Sheet1", // Main data sheet
    HISTORICAL: "DUPR_History", // Historical DUPR tracking
  },
};

// ===== MAIN FUNCTIONS =====

/**
 * Setup function - run this first to configure authentication
 */
function setup() {
  console.log("DUPR Club Manager Setup");
  console.log(
    "Please configure your DUPR username/password in the CONFIG section"
  );

  // Test the sheet connection
  const mainSheet = SpreadsheetApp.getActiveSheet();
  console.log("Connected to main sheet:", mainSheet.getName());

  // Add headers if they don't exist
  setupHeaders(mainSheet);

  // Create historical sheet
  createHistoricalSheet();

  // Test authentication
  const token = authenticateDUPR();
  if (token) {
    console.log("✅ DUPR authentication successful!");
    PropertiesService.getScriptProperties().setProperty("DUPR_TOKEN", token);
  } else {
    console.log(
      "❌ DUPR authentication failed. Please check your credentials."
    );
  }
}

/**
 * Main function to process all players in the sheet
 */
function processAllPlayers() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const lastRow = sheet.getLastRow();

  if (lastRow < CONFIG.DATA_START_ROW) {
    console.log("No data found in sheet");
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
      updateCell(sheet, row, CONFIG.COLUMNS.STATUS, "ERROR: " + error.message);
    }
  }

  console.log("Processing complete!");
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
    updateCell(sheet, row, CONFIG.COLUMNS.STATUS, "SKIP: Missing name");
    return;
  }

  console.log(`Processing: ${firstName} ${lastName}`);

  // Search for player in DUPR
  const searchResults = searchDUPRPlayer(firstName, lastName);

  if (!searchResults || searchResults.length === 0) {
    updateCell(sheet, row, CONFIG.COLUMNS.STATUS, "NOT FOUND");
    return;
  }

  // Find best match by email or phone
  const bestMatch = findBestMatch(searchResults, email, phone);

  if (!bestMatch) {
    updateCell(
      sheet,
      row,
      CONFIG.COLUMNS.STATUS,
      "NO MATCH: Email/phone mismatch"
    );
    return;
  }

  // Update sheet with DUPR data
  updatePlayerData(sheet, row, bestMatch);

  // Add player to club
  const addResult = addPlayerToClub(bestMatch.id);

  if (addResult) {
    updateCell(sheet, row, CONFIG.COLUMNS.STATUS, "ADDED TO CLUB");
  } else {
    updateCell(sheet, row, CONFIG.COLUMNS.STATUS, "FOUND BUT NOT ADDED");
  }
}

// ===== DUPR API FUNCTIONS =====

/**
 * Authenticate with DUPR using username/password (like duprly.py)
 */
function authenticateDUPR() {
  const url = `${
    CONFIG.DUPR_API_URL || "https://api.dupr.gg"
  }/auth/v1.0/login/`;

  const payload = {
    email: CONFIG.DUPR_USERNAME,
    password: CONFIG.DUPR_PASSWORD,
  };

  try {
    const response = UrlFetchApp.fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      payload: JSON.stringify(payload),
    });

    if (response.getResponseCode() === 200) {
      const data = JSON.parse(response.getContentText());
      const token = data.result?.accessToken;
      if (token) {
        console.log("Authentication successful");
        return token;
      }
    } else {
      console.error(
        "DUPR authentication failed:",
        response.getResponseCode(),
        response.getContentText()
      );
    }
  } catch (error) {
    console.error("Error authenticating with DUPR:", error);
  }

  return null;
}

/**
 * Get DUPR authentication token
 */
function getDUPRToken() {
  let token = PropertiesService.getScriptProperties().getProperty("DUPR_TOKEN");
  if (!token) {
    // Try to authenticate if no token exists
    token = authenticateDUPR();
    if (token) {
      PropertiesService.getScriptProperties().setProperty("DUPR_TOKEN", token);
    }
  }

  if (!token) {
    throw new Error(
      "DUPR authentication failed. Please check your credentials in CONFIG."
    );
  }
  return token;
}

/**
 * Search for a player in DUPR
 */
function searchDUPRPlayer(firstName, lastName) {
  const query = `${firstName} ${lastName}`;
  const url = `${
    CONFIG.DUPR_API_URL || "https://api.dupr.gg"
  }/player/v1.0/search`;

  const payload = {
    filter: {
      radiusInMeters: 16093400000, // ~10,000 miles
      lat: 39.977763,
      lng: -105.1319296,
    },
    includeUnclaimedPlayers: true,
    address: {
      latitude: 39.977763,
      longitude: -105.1319296,
    },
    offset: 0,
    limit: 25,
    query: query,
  };

  try {
    const response = UrlFetchApp.fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${getDUPRToken()}`,
        "Content-Type": "application/json",
      },
      payload: JSON.stringify(payload),
    });

    if (response.getResponseCode() === 200) {
      const data = JSON.parse(response.getContentText());
      return data.result?.hits || [];
    } else {
      console.error(
        "DUPR search failed:",
        response.getResponseCode(),
        response.getContentText()
      );
      return null;
    }
  } catch (error) {
    console.error("Error searching DUPR:", error);
    return null;
  }
}

/**
 * Add a player to the club
 */
function addPlayerToClub(playerId) {
  const url = `${CONFIG.DUPR_API_URL || "https://api.dupr.gg"}/club/${
    CONFIG.CLUB_ID
  }/members/v1.0/invite`;

  const payload = {
    playerIds: [playerId],
  };

  try {
    const response = UrlFetchApp.fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${getDUPRToken()}`,
        "Content-Type": "application/json",
      },
      payload: JSON.stringify(payload),
    });

    if (response.getResponseCode() === 200) {
      console.log(`Successfully added player ${playerId} to club`);
      return true;
    } else {
      console.error(
        "Failed to add player to club:",
        response.getResponseCode(),
        response.getContentText()
      );
      return false;
    }
  } catch (error) {
    console.error("Error adding player to club:", error);
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
    const emailMatch = searchResults.find(
      (player) =>
        player.email && player.email.toLowerCase() === email.toLowerCase()
    );
    if (emailMatch) return emailMatch;
  }

  // Then try to match by phone
  if (phone) {
    const phoneMatch = searchResults.find(
      (player) =>
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
  return phone.replace(/\D/g, "");
}

/**
 * Update player data in the sheet
 */
function updatePlayerData(sheet, row, playerData) {
  const duprId = playerData.duprId || playerData.id;
  const ratings = playerData.ratings || {};
  const doublesRating = ratings.doubles || "NR";

  updateCell(sheet, row, CONFIG.COLUMNS.DUPR_ID, duprId);
  updateCell(sheet, row, CONFIG.COLUMNS.DUPR_RATING, doublesRating);
  updateCell(sheet, row, CONFIG.COLUMNS.TIMESTAMP, new Date());
}

/**
 * Setup headers in the sheet
 */
function setupHeaders(sheet) {
  const headers = [
    "First Name",
    "Last Name",
    "Email",
    "Phone",
    "DUPR ID",
    "DUPR Rating",
    "Status",
    "Timestamp",
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
    return "";
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
    console.log("✅ Authentication successful!");
    console.log("Token:", token.substring(0, 20) + "...");
    PropertiesService.getScriptProperties().setProperty("DUPR_TOKEN", token);
  } else {
    console.log("❌ Authentication failed");
  }
}

/**
 * Test function to search for a single player
 */
function testSearch() {
  const results = searchDUPRPlayer("Sarah", "Tripp");
  console.log("Search results:", JSON.stringify(results, null, 2));
}

/**
 * Test function to add a player to club
 */
function testAddToClub() {
  const playerId = "7307629401"; // Sarah Tripp's ID
  const result = addPlayerToClub(playerId);
  console.log("Add to club result:", result);
}

/**
 * Quick test with your sample data
 */
function quickTest() {
  console.log("Running quick test with sample data...");

  // Test authentication
  console.log("1. Testing authentication...");
  testAuth();

  // Test search
  console.log("2. Testing player search...");
  testSearch();

  console.log("Quick test complete!");
}
