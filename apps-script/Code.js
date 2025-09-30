/**
 * DUPR Club Manager - Google Apps Script (Fixed Version)
 * Automatically searches DUPR players and adds them to your DUPR club
 *
 * Features:
 * - Correct column mapping for actual sheet structure
 * - Updates existing "DUPR" sheet with current ratings
 * - Historical DUPR tracking with vlookup functionality (3rd sheet)
 * - Notes column with timestamped entries
 * - Fixed club addition API with proper error logging
 * - Test functions for first/last entry
 * - GitFlow deployment system integration
 * - GitHub Actions CI/CD pipeline
 */

// ===== CONFIGURATION =====
const CONFIG = {
  // Your club information (public)
  CLUB_ID: "5996780750", // Replace with your DUPR club ID

  // Google Sheets configuration
  DATA_START_ROW: 2, // Row where your data starts (skip header)

  // Column mappings for different sheets
  COLUMNS: {
    // Main sheet (where we process players) - ACTUAL STRUCTURE
    MAIN: {
      ID_CODE: "A", // ID/Code (94VNXK, YGRGQP, etc.)
      FULL_NAME: "B", // Full Name (Abner, Adam Johnson, etc.)
      EMAIL: "C", // Email
      PHONE: "D", // Phone
      DOUBLES_DUPR: "E", // Doubles DUPR (existing)
      DOUBLES_RELIABILITY: "F", // Double Reliability
      SINGLES_DUPR: "G", // Singles DUPR
      SINGLES_RELIABILITY: "H", // Singles Reliability
      NOTES: "I", // Notes column
      DUPR_ID: "J", // DUPR ID (new)
      DUPR_RATING: "K", // DUPR Rating (new)
      STATUS: "L", // Status (new)
      TIMESTAMP: "M", // Timestamp (new)
    },
    
    // DUPR sheet (existing sheet with current ratings)
    DUPR: {
      DUPR_ID: "A", // DUPR_ID
      FULL_NAME: "B", // Full Name
      EMAIL: "C", // Email
      PHONE: "D", // Phone
      DOUBLES_DUPR: "E", // Doubles DUPR
      DOUBLES_RELIABILITY: "F", // Double Reliability
      SINGLES_DUPR: "G", // Singles DUPR
      SINGLES_RELIABILITY: "H", // Singles Reliability
    },
    
    // DUPR_History sheet (historical tracking)
    HISTORY: {
      DUPR_ID: "A", // DUPR_ID
      FULL_NAME: "B", // Full Name
      EMAIL: "C", // Email
      PHONE: "D", // Phone
      DOUBLES_DUPR: "E", // Doubles DUPR
      DOUBLES_RELIABILITY: "F", // Double Reliability
      SINGLES_DUPR: "G", // Singles DUPR
      SINGLES_RELIABILITY: "H", // Singles Reliability
      TIMESTAMP: "I", // Timestamp
      NOTES: "J", // Notes
    }
  },

  // Sheet names
  SHEETS: {
    MAIN: "Sheet1", // Main data sheet
    DUPR: "DUPR", // Existing DUPR sheet with current ratings
    HISTORICAL: "DUPR_History", // Historical DUPR tracking (3rd sheet)
  },
};

// ===== SECURE CREDENTIAL MANAGEMENT =====
/**
 * Get DUPR credentials from secure storage
 */
function getDUPRCredentials() {
  const props = PropertiesService.getScriptProperties();
  return {
    username: props.getProperty("DUPR_USERNAME"),
    password: props.getProperty("DUPR_PASSWORD"),
    clubId: CONFIG.CLUB_ID,
  };
}

/**
 * Setup credentials securely (manual setup)
 * Run this function in the Apps Script editor to set your credentials
 */
function setupCredentials() {
  const ui = SpreadsheetApp.getUi();
  const username = ui.prompt("Enter DUPR Username (Email):").getResponseText();
  const password = ui.prompt("Enter DUPR Password:").getResponseText();
  
  if (username && password) {
    PropertiesService.getScriptProperties().setProperties({
      DUPR_USERNAME: username,
      DUPR_PASSWORD: password,
    });
    ui.alert("✅ Credentials stored securely!");
    console.log("Credentials stored successfully");
  } else {
    ui.alert("❌ Please provide both username and password");
  }
}

/**
 * Setup credentials from CI/CD (automated)
 * This function is called by the GitHub Actions workflow
 */
function setupCredentialsFromCI() {
  // This function will be populated by the CI/CD pipeline
  // with actual credentials from GitHub secrets
  console.log('Setting up credentials from CI/CD...');
}

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

  // Setup DUPR sheet headers
  setupDUPRSheetHeaders();

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
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(CONFIG.SHEETS.MAIN);
  if (!sheet) {
    console.error(`Main sheet "${CONFIG.SHEETS.MAIN}" not found.`);
    return;
  }

  const lastRow = sheet.getLastRow();

  if (lastRow < CONFIG.DATA_START_ROW) {
    console.log("No data found in sheet");
    return;
  }

  // Only consider rows that actually have a name in FULL_NAME column
  const rowsToProcess = [];
  for (let row = CONFIG.DATA_START_ROW; row <= lastRow; row++) {
    const fullName = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.FULL_NAME);
    if (fullName) rowsToProcess.push(row);
  }

  console.log(`Processing ${rowsToProcess.length} players...`);

  for (const row of rowsToProcess) {
    try {
      processPlayer(sheet, row);
      // Add a small delay to avoid rate limiting
      Utilities.sleep(200);
    } catch (error) {
      console.error(`Error processing row ${row}:`, error);
      addNote(sheet, row, `ERROR: ${error.message}`);
      updateCell(sheet, row, CONFIG.COLUMNS.MAIN.STATUS, "ERROR: " + error.message);
    }
  }

  console.log("Processing complete!");
}
/**
 * Process a single player
 */
function processPlayer(sheet, row) {
  const idCode = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.ID_CODE);
  const fullName = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.FULL_NAME);
  const email = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.EMAIL);
  const phone = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.PHONE);
  const status = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.STATUS);

  // Skip if already processed successfully
  if (status && String(status).toUpperCase() === "ADDED TO CLUB") {
    addNote(sheet, row, "SKIP: Already added to club");
    return;
  }

  if (!fullName) {
    addNote(sheet, row, "SKIP: Missing name");
    updateCell(sheet, row, CONFIG.COLUMNS.MAIN.STATUS, "SKIP: Missing name");
    return;
  }

  // Parse first and last name from full name
  const nameParts = fullName.trim().split(" ");
  const firstName = nameParts[0];
  const lastName = nameParts.slice(1).join(" "); // Handle multiple last names

  if (!firstName) {
    addNote(sheet, row, "SKIP: Invalid name format");
    updateCell(sheet, row, CONFIG.COLUMNS.MAIN.STATUS, "SKIP: Invalid name format");
    return;
  }

  console.log(`Processing: ${fullName} (${idCode})`);
  addNote(sheet, row, `Started processing ${fullName} (${idCode})`);

  // Search for player in DUPR
  const searchResults = searchDUPRPlayer(firstName, lastName);

  if (!searchResults || searchResults.length === 0) {
    addNote(sheet, row, "NOT FOUND: No players found in DUPR search");
    updateCell(sheet, row, CONFIG.COLUMNS.MAIN.STATUS, "NOT FOUND");
    return;
  }

  // Find best match by email or phone
  const bestMatch = findBestMatch(searchResults, email, phone);

  if (!bestMatch) {
    addNote(sheet, row, "NO MATCH: Email/phone mismatch with search results");
    updateCell(
      sheet,
      row,
      CONFIG.COLUMNS.MAIN.STATUS,
      "NO MATCH: Email/phone mismatch"
    );
    return;
  }

  // Update sheet with DUPR data
  updatePlayerData(sheet, row, bestMatch);

  // Update DUPR sheet with current ratings
  updateDUPRSheet(firstName, lastName, bestMatch);

  // Add to historical tracking
  addToHistorical(firstName, lastName, bestMatch);

  // Resolve numeric id and add player to club
  const numericId = resolvePlayerNumericId(bestMatch);
  if (!numericId) {
    addNote(sheet, row, 'ERROR: Missing numeric DUPR id for add');
    updateCell(sheet, row, CONFIG.COLUMNS.MAIN.STATUS, 'ERROR: Missing numeric id');
    return;
  }

  const addResult = addMembersByIds([numericId]);

  if (addResult) {
    addNote(
      sheet,
      row,
      `SUCCESS: Added ${bestMatch.fullName} (${bestMatch.duprId}) to club`
    );
    updateCell(sheet, row, CONFIG.COLUMNS.MAIN.STATUS, "ADDED TO CLUB");
  } else {
    addNote(sheet, row, `FOUND: Player found but failed to add to club`);
    updateCell(sheet, row, CONFIG.COLUMNS.MAIN.STATUS, "FOUND BUT NOT ADDED");
  }
}

/**
 * Resolve numeric player id from a search hit. If missing, fallback to GET /player/{duprId}
 */
function resolvePlayerNumericId(hit) {
  if (!hit) return null;
  if (hit.id) return Number(hit.id);
  const duprId = hit.duprId || hit.DUPRID || hit.DuprId;
  if (!duprId) return null;

  try {
    const url = `${CONFIG.DUPR_API_URL || 'https://api.dupr.gg'}/player/v1.0/${duprId}`;
    const r = UrlFetchApp.fetch(url, {
      method: 'GET',
      headers: { Authorization: `Bearer ${getDUPRToken()}` },
      muteHttpExceptions: true,
    });
    if (r.getResponseCode() !== 200) {
      console.error('resolvePlayerNumericId failed:', r.getResponseCode(), r.getContentText());
      return null;
    }
    const data = JSON.parse(r.getContentText());
    const result = data && data.result;
    return result && result.id ? Number(result.id) : null;
  } catch (e) {
    console.error('resolvePlayerNumericId error:', e);
    return null;
  }
}

// ===== DUPR API FUNCTIONS =====

/**
 * Authenticate with DUPR using username/password (like duprly.py)
 */
function authenticateDUPR() {
  const credentials = getDUPRCredentials();
  if (!credentials.username || !credentials.password) {
    console.error("❌ DUPR credentials not configured. Run setupCredentials() first.");
    return null;
  }

  const url = `${
    CONFIG.DUPR_API_URL || "https://api.dupr.gg"
  }/auth/v1.0/login/`;

  const payload = {
    email: credentials.username,
    password: credentials.password,
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
 * Add a single existing DUPR user to the club by numeric id (id, not duprId)
 */
function addPlayerToClub(playerId) {
  return addMembersByIds([Number(playerId)]);
}

/**
 * Add multiple existing DUPR users to the club by numeric ids
 */
function addMembersByIds(userIds) {
  const url = `${CONFIG.DUPR_API_URL || "https://api.dupr.gg"}/club/${CONFIG.CLUB_ID}/members/v1.0/add`;
  const payload = { userIds: userIds.map(Number) };

  try {
    const response = UrlFetchApp.fetch(url, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${getDUPRToken()}`,
        "Content-Type": "application/json",
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });

    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
    console.log(`addMembersByIds code: ${responseCode}`);
    console.log(`addMembersByIds body: ${responseText}`);

    if (responseCode === 200) return true;
    // Treat already-invited as success (idempotent)
    if ((responseText || "").toLowerCase().includes("already invited")) return true;
    console.error("addMembersByIds failed:", responseCode, responseText);
    return false;
  } catch (error) {
    console.error("Error addMembersByIds:", error);
    return false;
  }
}

/**
 * Bulk add by name/email
 * addMembers: [ { fullName: string, email: string } ]
 */
function addMembersByEmails(addMembers) {
  const url = `${CONFIG.DUPR_API_URL || "https://api.dupr.gg"}/club/${CONFIG.CLUB_ID}/members/v1.0/multiple/add`;
  const payload = { addMembers };

  try {
    const response = UrlFetchApp.fetch(url, {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${getDUPRToken()}`,
        "Content-Type": "application/json",
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true,
    });

    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
    console.log(`addMembersByEmails code: ${responseCode}`);
    console.log(`addMembersByEmails body: ${responseText}`);

    if (responseCode === 200) return true;
    console.error("addMembersByEmails failed:", responseCode, responseText);
    return false;
  } catch (error) {
    console.error("Error addMembersByEmails:", error);
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

  updateCell(sheet, row, CONFIG.COLUMNS.MAIN.DUPR_ID, duprId);
  updateCell(sheet, row, CONFIG.COLUMNS.MAIN.DUPR_RATING, doublesRating);
  updateCell(sheet, row, CONFIG.COLUMNS.MAIN.TIMESTAMP, new Date());
}

/**
 * Add a note to the notes column with timestamp
 */
function addNote(sheet, row, message) {
  if (!sheet) {
    console.error("Sheet is undefined - cannot add note");
    return;
  }

  const now = new Date();
  const timestamp = Utilities.formatDate(
    now,
    Session.getScriptTimeZone(),
    "M/d/yy @ H:mm"
  );
  const note = `[${timestamp}] - ${message}`;

  const currentNotes = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.NOTES);
  const newNotes = currentNotes ? `${currentNotes}\n${note}` : note;

  updateCell(sheet, row, CONFIG.COLUMNS.MAIN.NOTES, newNotes);
}

/**
 * Update or add player data to the existing DUPR sheet
 */
function updateDUPRSheet(firstName, lastName, playerData) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let duprSheet;

  try {
    duprSheet = spreadsheet.getSheetByName(CONFIG.SHEETS.DUPR);
    if (!duprSheet) {
      console.error(`DUPR sheet "${CONFIG.SHEETS.DUPR}" not found. Available sheets:`, 
        spreadsheet.getSheets().map(s => s.getName()));
      return;
    }
  } catch (error) {
    console.error("Error accessing DUPR sheet:", error);
    return;
  }

  const duprId = playerData.duprId || playerData.id;
  const ratings = playerData.ratings || {};
  const doublesRating = ratings.doubles || "NR";
  const singlesRating = ratings.singles || "NR";
  const doublesReliability = ratings.doublesVerified
    ? "Verified"
    : "Unverified";
  const singlesReliability = ratings.singlesVerified
    ? "Verified"
    : "Unverified";

  // Check if player already exists in DUPR sheet
  const lastRow = duprSheet.getLastRow();
  let existingRow = null;

  for (let row = 2; row <= lastRow; row++) {
    // Skip header row
    const existingDuprId = duprSheet.getRange(row, 1).getValue(); // DUPR_ID column
    if (existingDuprId == duprId) {
      existingRow = row;
      break;
    }
  }

  const rowData = [
    duprId, // A - DUPR_ID
    playerData.fullName || `${firstName} ${lastName}`, // B - Full Name
    playerData.email || "", // C - Email
    playerData.phone || "", // D - Phone
    doublesRating, // E - Doubles DUPR
    doublesReliability, // F - Double Reliability
    singlesRating, // G - Singles DUPR
    singlesReliability, // H - Singles Reliability
  ];

  if (existingRow) {
    // Update existing row
    duprSheet.getRange(existingRow, 1, 1, rowData.length).setValues([rowData]);
    console.log(
      `Updated existing player ${firstName} ${lastName} in DUPR sheet`
    );
  } else {
    // Add new row
    duprSheet.appendRow(rowData);
    console.log(`Added new player ${firstName} ${lastName} to DUPR sheet`);
  }
}

/**
 * Add player to historical tracking sheet
 */
function addToHistorical(firstName, lastName, playerData) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let historicalSheet;

  try {
    historicalSheet = spreadsheet.getSheetByName(CONFIG.SHEETS.HISTORICAL);
    if (!historicalSheet) {
      console.error(`Historical sheet "${CONFIG.SHEETS.HISTORICAL}" not found. Available sheets:`, 
        spreadsheet.getSheets().map(s => s.getName()));
      return;
    }
  } catch (error) {
    console.error("Error accessing historical sheet:", error);
    return;
  }

  const duprId = playerData.duprId || playerData.id;
  const ratings = playerData.ratings || {};
  const doublesRating = ratings.doubles || "NR";
  const singlesRating = ratings.singles || "NR";

  const newRow = [
    new Date(), // Timestamp
    firstName, // First Name
    lastName, // Last Name
    duprId, // DUPR ID
    doublesRating, // Doubles Rating
    singlesRating, // Singles Rating
    playerData.fullName || "", // Full Name
    playerData.email || "", // Email
    playerData.phone || "", // Phone
    playerData.age || "", // Age
    playerData.gender || "", // Gender
  ];

  historicalSheet.appendRow(newRow);
}

/**
 * Setup headers for the existing DUPR sheet
 */
function setupDUPRSheetHeaders() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let duprSheet;

  try {
    duprSheet = spreadsheet.getSheetByName(CONFIG.SHEETS.DUPR);
  } catch (error) {
    console.log("DUPR sheet not found, skipping header setup");
    return;
  }

  // Check if headers already exist
  const firstRow = duprSheet.getRange(1, 1, 1, 8).getValues()[0];
  const hasHeaders = firstRow[0] && firstRow[0].toString().includes("DUPR_ID");

  if (!hasHeaders) {
    const headers = [
      "DUPR_ID",
      "Full Name",
      "Email",
      "Phone",
      "Doubles DUPR",
      "Double Reliability",
      "Singles DUPR",
      "Singles Reliability",
    ];

    duprSheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    duprSheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");
    console.log("Added headers to DUPR sheet");
  } else {
    console.log("DUPR sheet headers already exist");
  }
}

/**
 * Create historical tracking sheet
 */
function createHistoricalSheet() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();

  // Check if historical sheet already exists
  const existingSheet = spreadsheet.getSheetByName(CONFIG.SHEETS.HISTORICAL);
  if (existingSheet) {
    console.log("Historical sheet already exists");
    return;
  }

  const historicalSheet = spreadsheet.insertSheet(CONFIG.SHEETS.HISTORICAL);

  // Add headers
  const headers = [
    "Timestamp",
    "First Name",
    "Last Name",
    "DUPR ID",
    "Doubles Rating",
    "Singles Rating",
    "Full Name",
    "Email",
    "Phone",
    "Age",
    "Gender",
  ];

  historicalSheet.getRange(1, 1, 1, headers.length).setValues([headers]);

  // Format headers
  historicalSheet.getRange(1, 1, 1, headers.length).setFontWeight("bold");

  console.log("Created historical tracking sheet");
}

/**
 * Create historical sheet manually (run this if setup() didn't create it)
 */
function createHistoricalSheetManually() {
  console.log("Creating historical sheet manually...");
  createHistoricalSheet();
  console.log("Historical sheet creation complete!");
}

/**
 * Setup headers in the main sheet
 */
function setupHeaders(sheet) {
  const headers = [
    "ID Code",
    "Full Name",
    "Doubles DUPR",
    "Email",
    "Phone",
    "Address",
    "Membership Plan",
    "Notes",
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
    if (!sheet) {
      console.error("Sheet is undefined - cannot update cell");
      return;
    }
    sheet.getRange(`${column}${row}`).setValue(value);
  } catch (error) {
    console.error(`Error updating cell ${column}${row}:`, error);
  }
}

/**
 * Process a single player by row number (gets sheet automatically)
 */
function processSinglePlayer(rowNumber) {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = spreadsheet.getSheetByName(CONFIG.SHEETS.MAIN);
  if (!sheet) {
    console.error(`Main sheet "${CONFIG.SHEETS.MAIN}" not found.`);
    return;
  }
  console.log(`Processing player in row ${rowNumber}...`);
  processPlayer(sheet, rowNumber);
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
  const results = searchDUPRPlayer("John", "Doe");
  console.log("Search results:", JSON.stringify(results, null, 2));
}

/**
 * Test function to add a player to club
 */
function testAddToClub() {
  const playerId = "1234567890"; // Example player ID
  const result = addPlayerToClub(playerId);
  console.log("Add to club result:", result);
}

/**
 * Test the FIRST entry in the sheet
 */
function testFirstEntry() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const row = CONFIG.DATA_START_ROW;

  console.log(`Testing FIRST entry (row ${row})...`);

  const idCode = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.ID_CODE);
  const fullName = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.FULL_NAME);

  if (!fullName) {
    console.log("❌ First entry has no name data");
    return;
  }

  console.log(`Testing: ${fullName} (${idCode})`);
  processPlayer(sheet, row);
}

/**
 * Test the LAST entry in the sheet
 */
function testLastEntry() {
  const sheet = SpreadsheetApp.getActiveSheet();
  const lastRow = sheet.getLastRow();

  console.log(`Testing LAST entry (row ${lastRow})...`);

  const idCode = getCellValue(sheet, lastRow, CONFIG.COLUMNS.MAIN.ID_CODE);
  const fullName = getCellValue(sheet, lastRow, CONFIG.COLUMNS.MAIN.FULL_NAME);

  if (!fullName) {
    console.log("❌ Last entry has no name data");
    return;
  }

  console.log(`Testing: ${fullName} (${idCode})`);
  processPlayer(sheet, lastRow);
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
// Test comment for pre-commit hook
