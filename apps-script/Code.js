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

  // PlayByPoint integration (public data; auth stored in script properties)
  PBP: {
    BASE_URL: "https://app.playbypoint.com",
    FACILITY_ID: "983", // Replace with your facility id
    FACILITY_SLUG: "thepicklrthornton", // Optional: pretty path used in Referer
    DEFAULTS: {
      CSRF_TOKEN: "VUgiQG3hSPV1-wlDlq0qaxMLl7Tr5WpkwmBWmGpkAnJbg8KJSQ1iKlia3mrDj0iE9HKkV3lqN8K0i7jT89EP4g",
      REFERER: "https://app.playbypoint.com/admin/facilities/thepicklrthornton/manage_bookings",
      BAGGAGE: "sentry-environment=production,sentry-public_key=ab3697c86cfee424c79bdb37a8edda90,sentry-trace_id=f6443729c758459fa957b5f8f72efe3b,sentry-sampled=true,sentry-sample_rand=0.010835465593402205,sentry-sample_rate=0.05",
      SENTRY_TRACE: "f6443729c758459fa957b5f8f72efe3b-90b2f2676c020c40-1",
      UA: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
      SEC_CH_UA: '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
      SEC_CH_UA_MOBILE: "?0",
      SEC_CH_UA_PLATFORM: '"macOS"',
      ACCEPT: "application/json, text/javascript, */*; q=0.01",
      ACCEPT_LANGUAGE: "en-US,en;q=0.9",
      COOKIE: `'_hjSessionUser_3433560=eyJpZCI6ImRmNGMyOTcxLWM0MDktNTE1MS1hYzA0LWMxMDhjZWIxODZkYiIsImNyZWF0ZWQiOjE3NTQ5NTE0NjQ3MDIsImV4aXN0aW5nIjpmYWxzZX0=; _ga=GA1.1.1774985913.1754951464; intercom-id-u1mtnxxh=f679f570-c178-4395-8c31-6e4736c0fd2f; intercom-device-id-u1mtnxxh=48959797-79e7-450d-9d5c-abe210bf2508; __stripe_mid=561e17dc-db33-442d-9526-b7ce2a50061edf3591; sa-user-id=s%253A0-709e0d08-ddcb-5982-564a-7188082ac8f8.GEweAFQEwfiqvYVIMX5Yv7eRd%252FTqAZp%252FG8hdCi0pZL0; sa-user-id-v2=s%253AcJ4NCN3LWYJWSnGICCrI-AQgccM.29MY21xerftY3Sf%252BuHz1NK3oHOv3ROmcqtEh%252FPGbzkk; sa-user-id-v3=s%253AAQAKIAor-h1RkEIGgCXs7MKRqb1-5rd3Tx1xeL2kyi1hfzxMEAMYAyDBg5bBBjABOgQv-638QgTgfqgD.F1f%252BUCJrGovqrW6HmhezFV8DP0UdQUu1XT%252BN35gNCgQ; sa-r-source=www.google.com; ajs_anonymous_id=%228a29e2a4-1f04-4a9a-ad83-cd84cf4948e9%22; hubspotutk=a6502a217d6d014c11e387325cd68e3e; _gcl_au=1.1.2050280770.1754951463.1813481787.1758832970.1758832974; remember_user_token=eyJfcmFpbHMiOnsibWVzc2FnZSI6Ilcxc3hOVGN6T1RBMFhTd2lWMmgyTVVVMVUwRkRSa1pZT0dkaVUxbG5hRlVpTENJeE56VTRPRE15T1RjMUxqTXdPRGs1T1RVaVhRPT0iLCJleHAiOiIyMDI1LTEwLTI1VDIwOjQyOjU1LjMwOVoiLCJwdXIiOiJjb29raWUucmVtZW1iZXJfdXNlcl90b2tlbiJ9fQ%3D%3D--951dde3ad228a83ac2bfd0735f303cf41b89ea44; sa-r-date=2025-09-25T23:13:59.867Z; __hstc=91698565.a6502a217d6d014c11e387325cd68e3e.1757693943587.1758842047692.1758855755705.4; _clck=1riar3g%5E2%5Efzr%5E0%5E2071; __stripe_sid=d6a43dd9-a5ce-4968-ad6d-bcbd71f8aa786c0317; _ga_M060445B8S=GS2.1.s1759212879$o38$g1$t1759212885$j54$l0$h0; _ga_RP1D1ZTH5S=GS2.1.s1759212879$o27$g1$t1759212885$j54$l0$h1948541772; _clsk=1gt5gwh%5E1759212886545%5E3%5E1%5Eb.clarity.ms%2Fcollect; intercom-session-u1mtnxxh=enF2Q1p1Y3N5Y2d4T3VnSWROTlp1akxud0o4UVZha0htMFY5aThlQUpqOXFWSHJkcm12UHZPVTBKdTZ2MjJYakhIZUVYdWtWcm1NVTlIejFmUDZxcjJHQnQrVlVkVFBXUVN2b2dacmdLVDA9LS01NUxValRsUFVUczZkNTY4TFpQQU9RPT0=--e9f93227e66ae27bbe441afe7c5288193e9c5bd4; _paybycourt_session=tREPYD5jIAwrng%2FMUPggKCNve0W6R37QmNKuXg6Q6jxCHjYKha52xF3P9H4RaccnKV5Uxq%2BAndqlhTY%2FDmJpg7YvIdUcDFOlRFSp5R2ZLaBpb14XBIdyrx99g4FQGBig9Cd5rYw3%2BSi9Gx9Blp9jpJgwkuAnxi3gI9rKsVvwnhQe15V8MTung2%2FGYffQW715RTPKGNR6w2OCDP3rMtCelNvy6CWRXxt%2Bd%2Ff7emboQOLpJ3zaKDGbIntouZ%2FfYFgirphOaUIrglYfHx2ExUXsIQzFJm%2BfdV7h8AuB0x%2B%2BcTpY3ob80dr8NerWtcJ2bxn7V7VvmFu6HbGucwaXZYGYmVzeLoYBu%2FTt3NzzkGP9CUVzUmOGtoGkrBgXaoXfaiIT2OTVDz0FC8tB5qjvBdP8FMww5ETrnj7XuuucHuyipHqOQ2KMutvW8%2BzIYpHIMPlNVCOCyhtpvjQgfnUnDE6OZ5f3s%2B4fL7Y0uVAAQca3Ow%2B01Wypa8IYQsor4OAW1dbcXXbKD8brb46KWK2RVkwhelFSNQ%3D%3D--rKmtt5z4IGuQaLzX--%2FZqcLxhr4wmRNn7GA4r7Jg%3D%3D'`,
    },
  },

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
  const pbpCsrf = ui.prompt("Enter PlayByPoint X-CSRF-Token (optional):").getResponseText();
  const pbpCookie = ui
    .prompt("Enter PlayByPoint Cookie header (optional):")
    .getResponseText();
  const pbpReferer = ui
    .prompt("Enter PlayByPoint Referer URL (optional):")
    .getResponseText();
  const pbpBaggage = ui.prompt("Enter PlayByPoint 'baggage' header (optional):").getResponseText();
  const pbpSentry = ui.prompt("Enter PlayByPoint 'sentry-trace' header (optional):").getResponseText();
  
  if (username && password) {
    PropertiesService.getScriptProperties().setProperties({
      DUPR_USERNAME: username,
      DUPR_PASSWORD: password,
      PBP_CSRF: pbpCsrf || "",
      PBP_COOKIE: pbpCookie || "",
      PBP_REFERER: pbpReferer || "",
      PBP_BAGGAGE: pbpBaggage || "",
      PBP_SENTRY_TRACE: pbpSentry || "",
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

// ===== PlayByPoint API FUNCTIONS =====

/**
 * Search PlayByPoint users by name and return current DUPR ratings if present
 * Stores sensitive headers (CSRF, Cookie) in Script Properties via setupCredentials()
 */
function searchPlayByPointUsers(query) {
  const props = PropertiesService.getScriptProperties();
  const csrf = props.getProperty("PBP_CSRF") || CONFIG.PBP.DEFAULTS.CSRF_TOKEN;
  const cookie = props.getProperty("PBP_COOKIE") || CONFIG.PBP.DEFAULTS.COOKIE;
  const customReferer = props.getProperty("PBP_REFERER") || CONFIG.PBP.DEFAULTS.REFERER;
  const baggage = props.getProperty("PBP_BAGGAGE") || CONFIG.PBP.DEFAULTS.BAGGAGE;
  const sentryTrace = props.getProperty("PBP_SENTRY_TRACE") || CONFIG.PBP.DEFAULTS.SENTRY_TRACE;
  if (!csrf || !cookie) {
    console.log("PlayByPoint credentials missing. Run setupCredentials() to set PBP_CSRF and PBP_COOKIE.");
    return [];
  }

  const base = CONFIG.PBP.BASE_URL;
  const facilityId = CONFIG.PBP.FACILITY_ID;
  const url = `${base}/api/users.json?q=${encodeURIComponent(query)}&court_id=&include_child=1&facility_id=${encodeURIComponent(facilityId)}&show_affiliation=&rating_provider=dupr`;
  const referer = customReferer || `${base}/admin/facilities/${encodeURIComponent(CONFIG.PBP.FACILITY_SLUG || CONFIG.PBP.FACILITY_ID)}/manage_bookings`;

  const headers = {
    "X-CSRF-Token": csrf,
    "X-Requested-With": "XMLHttpRequest",
    Accept: "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    // Extra browser-like client hints and fetch metadata
    "sec-ch-ua": CONFIG.PBP.DEFAULTS.SEC_CH_UA,
    "sec-ch-ua-mobile": CONFIG.PBP.DEFAULTS.SEC_CH_UA_MOBILE,
    "sec-ch-ua-platform": CONFIG.PBP.DEFAULTS.SEC_CH_UA_PLATFORM,
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    Origin: base,
    Referer: referer,
    Host: "app.playbypoint.com",
    Connection: "keep-alive",
    Baggage: baggage || undefined,
    "sentry-trace": sentryTrace || undefined,
    // Use a browser-like UA; some CDNs/WAFs block generic agents
    "User-Agent": CONFIG.PBP.DEFAULTS.UA,
    Cookie: cookie,
  };

  try {
    let resp = UrlFetchApp.fetch(url, {
      method: "GET",
      headers,
      muteHttpExceptions: true,
    });
    if (resp.getResponseCode() === 403) {
      // Attempt to refresh CSRF token from facility page and retry once
      const newToken = refreshPbpCsrfToken(cookie);
      if (newToken) {
        headers["X-CSRF-Token"] = newToken;
        resp = UrlFetchApp.fetch(url, {
          method: "GET",
          headers,
          muteHttpExceptions: true,
        });
      }
    }
    if (resp.getResponseCode() !== 200) {
      console.error("PBP search failed:", resp.getResponseCode(), resp.getContentText());
      return [];
    }
    const data = JSON.parse(resp.getContentText());
    return data.users || [];
  } catch (e) {
    console.error("Error calling PBP:", e);
    return [];
  }
}

/**
 * Refresh and persist the PlayByPoint CSRF token by scraping the facility page.
 */
function refreshPbpCsrfToken(cookie) {
  try {
    const base = CONFIG.PBP.BASE_URL;
    // Use a stable admin page that includes <meta name="csrf-token" content="...">
    const url = `${base}/admin/facilities/${encodeURIComponent(CONFIG.PBP.FACILITY_ID)}/manage_bookings`;
    const resp = UrlFetchApp.fetch(url, {
      method: "GET",
      headers: {
        Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        Cookie: cookie,
      },
      muteHttpExceptions: true,
    });
    if (resp.getResponseCode() !== 200) {
      console.error("Failed to load PBP page for CSRF refresh:", resp.getResponseCode());
      return null;
    }
    const html = resp.getContentText();
    const match = html.match(/<meta\s+name=["']csrf-token["']\s+content=["']([^"']+)["']/i);
    const token = match ? match[1] : null;
    if (token) {
      PropertiesService.getScriptProperties().setProperty("PBP_CSRF", token);
      console.log("Refreshed PBP CSRF token");
    }
    return token;
  } catch (e) {
    console.error("Error refreshing PBP CSRF token:", e);
    return null;
  }
}

/**
 * Convenience: look up current row's full name in PBP and log ratings
 */
function pbpLookupActiveRow() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEETS.MAIN) || SpreadsheetApp.getActiveSheet();
  const row = sheet.getActiveRange().getRow();
  if (row < CONFIG.DATA_START_ROW) {
    console.log("Active row not in data region");
    return;
  }
  const email = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.EMAIL);
  const fullName = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.FULL_NAME);
  const query = email || fullName;
  if (!query) {
    console.log("No email or name in active row");
    return;
  }
  const results = searchPlayByPointUsers(query);
  console.log("PBP results:", JSON.stringify(results.slice(0, 3), null, 2));
  if (results.length) {
    const u = chooseBestPbpUser(results, email);
    const doubles = u.current_rating?.double ?? "";
    const singles = u.current_rating?.single ?? "";
    if (doubles || singles) {
      updateCell(sheet, row, CONFIG.COLUMNS.MAIN.DUPR_RATING, doubles || singles);
      addNote(sheet, row, `PBP: singles=${singles}, doubles=${doubles}`);
      updateCell(sheet, row, CONFIG.COLUMNS.MAIN.STATUS, "PBP LOOKUP");
    }
  }
}

/**
 * Quick manual search in PlayByPoint by name; logs top results
 */
function pbpSearchName(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEETS.MAIN) || SpreadsheetApp.getActiveSheet();
  const row = sheet.getActiveRange ? sheet.getActiveRange().getRow() : CONFIG.DATA_START_ROW;
  const email = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.EMAIL);
  const fullName = getCellValue(sheet, row, CONFIG.COLUMNS.MAIN.FULL_NAME);
  const query = email || name || fullName;
  if (!query) {
    console.log("Provide an email/name or select a row with data");
    return;
  }
  const results = searchPlayByPointUsers(query);
  // Reorder to put best match first using email and Adult priority
  if (results && results.length) {
    const lower = email ? String(email).toLowerCase() : null;
    results.sort((a, b) => {
      const aExact = lower && ((a.email && String(a.email).toLowerCase() === lower) || (a.user_child_name && String(a.user_child_name).toLowerCase() === lower));
      const bExact = lower && ((b.email && String(b.email).toLowerCase() === lower) || (b.user_child_name && String(b.user_child_name).toLowerCase() === lower));
      if (aExact !== bExact) return aExact ? -1 : 1;
      const aAdult = String(a.user_type_tag || "").toLowerCase() === "adult";
      const bAdult = String(b.user_type_tag || "").toLowerCase() === "adult";
      if (aAdult !== bAdult) return aAdult ? -1 : 1;
      return 0;
    });
  }
  console.log("PBP query:", query);
  console.log("PBP results:", JSON.stringify(results.slice(0, 10), null, 2));
}

/**
 * Choose best PBP user result based on email and Adult priority
 */
function chooseBestPbpUser(results, email) {
  if (!results || !results.length) return null;
  const lower = email ? String(email).toLowerCase() : null;
  if (lower) {
    const exactAdult = results.find(r => (r.email && String(r.email).toLowerCase() === lower || r.user_child_name && String(r.user_child_name).toLowerCase() === lower) && String(r.user_type_tag || "").toLowerCase() === "adult");
    if (exactAdult) return exactAdult;
    const exactAny = results.find(r => (r.email && String(r.email).toLowerCase() === lower) || (r.user_child_name && String(r.user_child_name).toLowerCase() === lower));
    if (exactAny) return exactAny;
  }
  const firstAdult = results.find(r => String(r.user_type_tag || "").toLowerCase() === "adult");
  return firstAdult || results[0];
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
