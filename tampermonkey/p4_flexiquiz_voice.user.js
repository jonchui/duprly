/*
// ==UserScript==
// @name         P4 FlexiQuiz Voice Companion
// @namespace    https://thepicklr.com/
// @version      0.1.0
// @description  Hands-free reading and answering helper for FlexiQuiz using P4 knowledge cues
// @match        https://www.flexiquiz.com/*
// @grant        none
// @author       P4 Assistant
// @license      MIT
// @run-at       document-idle
// ==/UserScript==
*/

(function () {
  "use strict";

  if (window.top !== window.self) return;

  const speechSupported = "speechSynthesis" in window;
  const recSupported = "webkitSpeechRecognition" in window || "SpeechRecognition" in window;

  const state = {
    isListening: false,
    recognition: null,
    lastQuestion: null,
    lastOptions: [],
    lastSuggestion: null,
    speaking: false,
  };

  function createOverlay() {
    const root = document.createElement("div");
    root.id = "p4-voice-overlay";
    root.style.position = "fixed";
    root.style.bottom = "18px";
    root.style.right = "18px";
    root.style.zIndex = "999999";
    root.style.fontFamily = "system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
    root.style.display = "flex";
    root.style.flexDirection = "column";
    root.style.gap = "8px";
    root.style.width = "320px";

    const card = document.createElement("div");
    card.style.background = "#0b1220";
    card.style.color = "#e6ebf5";
    card.style.border = "1px solid rgba(255,255,255,0.15)";
    card.style.borderRadius = "10px";
    card.style.boxShadow = "0 6px 18px rgba(0,0,0,0.25)";
    card.style.padding = "12px";
    card.style.backdropFilter = "blur(4px)";

    const header = document.createElement("div");
    header.style.display = "flex";
    header.style.alignItems = "center";
    header.style.justifyContent = "space-between";

    const title = document.createElement("div");
    title.textContent = "P4 Voice";
    title.style.fontWeight = "600";
    title.style.letterSpacing = "0.2px";

    const micBtn = document.createElement("button");
    micBtn.textContent = "🎤 Start";
    micBtn.title = "Start/Stop voice recognition";
    micBtn.style.background = "#2a6df4";
    micBtn.style.color = "white";
    micBtn.style.border = "none";
    micBtn.style.borderRadius = "8px";
    micBtn.style.padding = "8px 12px";
    micBtn.style.cursor = "pointer";
    micBtn.style.fontWeight = "600";

    header.appendChild(title);
    header.appendChild(micBtn);

    const status = document.createElement("div");
    status.id = "p4-status";
    status.textContent = recSupported
      ? "Say: start, repeat, choose A, final answer, why, next"
      : "SpeechRecognition not supported in this browser";
    status.style.fontSize = "12px";
    status.style.opacity = "0.85";
    status.style.marginTop = "6px";

    const controls = document.createElement("div");
    controls.style.display = "flex";
    controls.style.gap = "6px";
    controls.style.marginTop = "10px";

    const repeatBtn = document.createElement("button");
    repeatBtn.textContent = "Repeat";
    styleGhostBtn(repeatBtn);

    const whyBtn = document.createElement("button");
    whyBtn.textContent = "Why";
    styleGhostBtn(whyBtn);

    const nextBtn = document.createElement("button");
    nextBtn.textContent = "Next";
    styleGhostBtn(nextBtn);

    controls.appendChild(repeatBtn);
    controls.appendChild(whyBtn);
    controls.appendChild(nextBtn);

    const suggest = document.createElement("div");
    suggest.id = "p4-suggestion";
    suggest.style.marginTop = "8px";
    suggest.style.fontSize = "12px";
    suggest.style.lineHeight = "1.4";
    suggest.style.opacity = "0.9";

    card.appendChild(header);
    card.appendChild(status);
    card.appendChild(controls);
    card.appendChild(suggest);
    root.appendChild(card);
    document.body.appendChild(root);

    micBtn.addEventListener("click", toggleListening);
    repeatBtn.addEventListener("click", () => readCurrentQA());
    whyBtn.addEventListener("click", () => explainWhy());
    nextBtn.addEventListener("click", () => clickNext());

    return { micBtn, status, suggest };
  }

  function styleGhostBtn(btn) {
    btn.style.background = "transparent";
    btn.style.color = "#e6ebf5";
    btn.style.border = "1px solid rgba(255,255,255,0.2)";
    btn.style.borderRadius = "8px";
    btn.style.padding = "6px 10px";
    btn.style.cursor = "pointer";
    btn.style.fontWeight = "600";
  }

  function setStatus(text) {
    const el = document.getElementById("p4-status");
    if (el) el.textContent = text;
  }

  function setSuggestion(text) {
    const el = document.getElementById("p4-suggestion");
    if (el) el.textContent = text;
  }

  function speak(text) {
    if (!speechSupported || !text) return;
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.0;
    utter.pitch = 1.0;
    utter.lang = "en-US";
    state.speaking = true;
    utter.onend = () => (state.speaking = false);
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utter);
  }

  function startRecognition() {
    if (!recSupported) return;
    const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new Rec();
    rec.lang = "en-US";
    rec.interimResults = false;
    rec.continuous = true;
    rec.maxAlternatives = 1;

    rec.onresult = (event) => {
      const idx = event.resultIndex;
      const res = event.results[idx];
      if (!res || !res[0]) return;
      const transcript = (res[0].transcript || "").trim().toLowerCase();
      handleCommand(transcript);
    };

    rec.onend = () => {
      if (state.isListening) {
        try {
          rec.start();
        } catch (_) {
          // Swallow restart errors
        }
      }
    };

    rec.onerror = () => {
      setStatus("Mic error. Click 🎤 Start again.");
    };

    try {
      rec.start();
      state.recognition = rec;
      state.isListening = true;
      setStatus(
        "Listening… Say: repeat, choose A/B/C/D, final answer, why, next"
      );
    } catch (e) {
      setStatus("Mic blocked. Allow microphone and click Start again.");
    }
  }

  function stopRecognition() {
    try {
      state.isListening = false;
      state.recognition && state.recognition.stop();
      setStatus("Stopped. Click 🎤 Start to listen.");
    } catch (_) {}
  }

  function toggleListening() {
    if (state.isListening) {
      stopRecognition();
      const btn = document.querySelector("#p4-voice-overlay button");
      if (btn) btn.textContent = "🎤 Start";
    } else {
      startRecognition();
      const btn = document.querySelector("#p4-voice-overlay button");
      if (btn) btn.textContent = "⏺️ Listening";
      // On first start, read the current QA
      setTimeout(readCurrentQA, 300);
    }
  }

  function normalizeText(t) {
    return (t || "")
      .replace(/\s+/g, " ")
      .replace(/\u00A0/g, " ")
      .trim();
  }

  function getQuestionContext() {
    // Heuristic: find the largest visible block that contains radio/checkbox options
    const inputs = Array.from(
      document.querySelectorAll("input[type=radio], input[type=checkbox]")
    ).filter(isVisible);

    if (inputs.length === 0) return null;

    // Group by nearest section container
    const containers = new Map();
    for (const input of inputs) {
      const block = input.closest(".question, .quiz, .qcontainer, .q-block, form, .container, .content") ||
        input.closest("div, section, form");
      if (!block) continue;
      const key = block;
      const arr = containers.get(key) || [];
      arr.push(input);
      containers.set(key, arr);
    }

    let best = null;
    let bestCount = 0;
    for (const [block, arr] of containers.entries()) {
      const count = arr.length;
      if (count > bestCount && isVisible(block)) {
        best = block;
        bestCount = count;
      }
    }
    if (!best) return null;

    const optionInputs = Array.from(best.querySelectorAll("input[type=radio], input[type=checkbox]"))
      .filter(isVisible);

    // Extract option labels in order
    const options = [];
    const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
    let letterIdx = 0;
    for (const input of optionInputs) {
      // Prefer associated <label for>
      let labelEl = null;
      if (input.id) {
        labelEl = best.querySelector(`label[for="${cssEscape(input.id)}"]`);
      }
      if (!labelEl) {
        // Fallback: parent label or nearest text sibling
        labelEl = input.closest("label");
      }
      let text = "";
      if (labelEl) {
        text = normalizeText(labelEl.innerText || labelEl.textContent || "");
      } else {
        // Walk siblings briefly
        const sib = input.parentElement;
        if (sib) text = normalizeText(sib.innerText || sib.textContent || "");
      }
      if (!text) continue;

      const letter = letters[letterIdx++] || "";
      options.push({ input, labelEl, text, letter });
    }

    // Find question text: the closest preceding heading/text above options block
    let questionText = "";
    const candidateBlocks = [];
    let probe = best;
    for (let i = 0; i < 3 && probe; i++) {
      candidateBlocks.push(probe);
      probe = probe.parentElement;
    }
    const textBlocks = candidateBlocks
      .flatMap((blk) => Array.from(blk.querySelectorAll("h1,h2,h3,h4,h5,.question-text,.qtext,p,div")))
      .filter(isVisible);
    let longest = "";
    for (const el of textBlocks) {
      const t = normalizeText(el.innerText || el.textContent || "");
      if (t.length > longest.length && t.length >= 12 && !looksLikeOptionList(t)) {
        longest = t;
      }
    }
    questionText = longest;

    return { container: best, questionText, options };
  }

  function looksLikeOptionList(t) {
    return /\b(a\)|b\)|c\)|d\))|\b(A\.|B\.|C\.|D\.)/i.test(t);
  }

  function isVisible(el) {
    if (!el) return false;
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return (
      rect.width > 0 &&
      rect.height > 0 &&
      style.visibility !== "hidden" &&
      style.display !== "none"
    );
  }

  function cssEscape(s) {
    // Minimal escape for CSS attribute selectors
    return (s || "").replace(/"/g, '\\"');
  }

  function highlightOption(letter) {
    for (const opt of state.lastOptions || []) {
      const host = opt.labelEl || opt.input.parentElement || opt.input;
      if (!host) continue;
      host.style.outline = opt.letter === letter ? "3px solid #2a6df4" : "none";
      host.style.backgroundColor = opt.letter === letter ? "rgba(42,109,244,0.12)" : "";
      host.style.borderRadius = opt.letter === letter ? "6px" : host.style.borderRadius;
    }
  }

  function readCurrentQA() {
    const ctx = getQuestionContext();
    if (!ctx || ctx.options.length === 0) {
      setSuggestion("No question/options detected on this screen.");
      speak("I can't find the question or options on this page.");
      return;
    }
    state.lastQuestion = ctx.questionText;
    state.lastOptions = ctx.options;

    const parts = [];
    parts.push(`Question: ${ctx.questionText}`);
    for (const opt of ctx.options) {
      parts.push(`${opt.letter}. ${opt.text}`);
    }
    speak(parts.join(" \n "));

    // Compute suggestion
    const suggestion = suggestAnswer(ctx.questionText, ctx.options);
    state.lastSuggestion = suggestion;
    if (suggestion && suggestion.letter) {
      highlightOption(suggestion.letter);
      setSuggestion(
        `Suggest: ${suggestion.letter} — ${suggestion.reason || ""}`
      );
    } else if (suggestion && suggestion.reason) {
      setSuggestion(`Guide: ${suggestion.reason}`);
    } else {
      setSuggestion("No confident suggestion. Say 'why' for a guiding rule.");
    }
  }

  function explainWhy() {
    const s = state.lastSuggestion;
    if (!s) {
      speak("No suggestion yet. Say: start or repeat to read the question.");
      return;
    }
    const text = s.reason || "No rationale available.";
    speak(text);
  }

  function clickNext() {
    const btn = findNavButton(["Next", "Continue", "Submit"]);
    if (btn) {
      btn.click();
      setSuggestion("");
      setTimeout(() => readCurrentQA(), 800);
    } else {
      speak("I can't find a Next or Continue button.");
    }
  }

  function clickBack() {
    const btn = findNavButton(["Back", "Previous"]);
    if (btn) {
      btn.click();
      setSuggestion("");
      setTimeout(() => readCurrentQA(), 800);
    } else {
      speak("I can't find a Back button.");
    }
  }

  function findNavButton(labels) {
    const candidates = Array.from(
      document.querySelectorAll("button, input[type=button], input[type=submit], a")
    ).filter(isVisible);
    const normalized = labels.map((t) => t.toLowerCase());
    for (const el of candidates) {
      const text = normalizeText(el.innerText || el.value || el.textContent || "").toLowerCase();
      for (const lbl of normalized) {
        if (text.includes(lbl)) return el;
      }
    }
    return null;
  }

  function chooseOptionByLetter(letter) {
    const opt = (state.lastOptions || []).find((o) => o.letter.toLowerCase() === letter.toLowerCase());
    if (!opt) {
      speak(`I couldn't find option ${letter}.`);
      return;
    }
    if (opt.input && typeof opt.input.click === "function") {
      opt.input.click();
      highlightOption(opt.letter);
      speak(`Selected option ${opt.letter}. Say 'final answer' to proceed, or 'why'.`);
    }
  }

  function handleCommand(raw) {
    const transcript = raw.replace(/\s+/g, " ").trim();
    if (!transcript) return;

    // Control commands
    if (/^(start|begin|let's go|read|read question)$/i.test(transcript)) {
      readCurrentQA();
      return;
    }
    if (/^(repeat|say again|one more time)$/i.test(transcript)) {
      readCurrentQA();
      return;
    }
    if (/^(why|explain|explanation|rationale|reason|hint)$/i.test(transcript)) {
      explainWhy();
      return;
    }
    if (/^(next|continue|go next|final answer|submit)$/i.test(transcript)) {
      // If user said final answer after choosing, click next
      clickNext();
      return;
    }
    if (/^(back|previous|go back)$/i.test(transcript)) {
      clickBack();
      return;
    }

    // Option selection
    const letter = parseLetterCommand(transcript);
    if (letter) {
      chooseOptionByLetter(letter);
      return;
    }

    // Fallback keyword: choose suggestion
    if (/^(choose|select) (suggestion|that|this)$/i.test(transcript)) {
      const s = state.lastSuggestion;
      if (s && s.letter) chooseOptionByLetter(s.letter);
      return;
    }

    // Unknown command
    setStatus(`Heard: "${transcript}" (unknown). Try: choose A, why, next.`);
  }

  function parseLetterCommand(t) {
    // Map NATO and common variants to letters
    const map = {
      a: ["a", "alpha", "option a", "letter a"],
      b: ["b", "bravo", "option b", "letter b", "be"],
      c: ["c", "charlie", "option c", "letter c", "see"],
      d: ["d", "delta", "option d", "letter d", "dee"],
    };
    const s = t.toLowerCase();
    for (const [letter, keys] of Object.entries(map)) {
      for (const k of keys) {
        if (s === k || s.startsWith(k + " ") || s.endsWith(" " + k) || s.includes(" " + k + " ")) {
          return letter;
        }
      }
      if (s === `choose ${letter}` || s === `select ${letter}` || s === `answer ${letter}`) return letter;
    }
    // Patterns like "choose option C", "answer Bravo"
    const m = s.match(/(choose|select|answer)\s+(option\s+)?([a-d]|alpha|bravo|charlie|delta)/);
    if (m) {
      const token = m[3];
      if (token) {
        if (/alpha|^a$/.test(token)) return "a";
        if (/bravo|^b$/.test(token)) return "b";
        if (/charlie|^c$/.test(token)) return "c";
        if (/delta|^d$/.test(token)) return "d";
      }
    }
    return null;
  }

  // --- P4 suggestion engine ---
  const P4_BANK = buildP4Bank();

  function buildP4Bank() {
    // Minimal bank with keywords and option-match hints
    // Source concepts adapted from P4 workbook and outline (Grip, Ball Sectors, Zones, Energy, Serve/Return, Third/5th, Dinks)
    const rules = [
      rule(
        "fundamentals",
        ["fundamental", "principle", "core", "p4"],
        "Core: see bounce in front, contact in front, balance, simplest shot.",
        [
          /bounce.*in front/i,
          /contact.*in front/i,
          /balance/i,
          /simplest|easiest.*shot/i,
        ]
      ),
      rule(
        "grip",
        ["grip", "continental", "eastern", "paddle face", "knuckles", "palms"],
        "Use Continental/Eastern. Paddle face mirrors palms/knuckles to aim.",
        [/continental|eastern/i, /mirrors.*palms|knuckles/i]
      ),
      rule(
        "ball_top",
        ["ball sector", "b1", "b4", "top half", "speed up", "drive"],
        "Top-half (B1/B4) contact flattens and drives — use to attack when balanced.",
        [/top.*half|b1|b4|drive|speed/i]
      ),
      rule(
        "ball_bottom",
        ["ball sector", "b2", "b3", "bottom half", "lift", "arc", "reset"],
        "Bottom-half (B2/B3) adds lift/arc — use to reset, drop, or add margin.",
        [/bottom.*half|b2|b3|lift|arc|reset|drop/i]
      ),
      rule(
        "zones_overview",
        ["zones", "z1", "z2", "z3", "z4", "kitchen", "transition", "baseline"],
        "Z4 build, Z3 reset/advance, Z2 pressure/targets, Z1 finish soft.",
        [/z4.*baseline/i, /z3.*transition|reset/i, /z2.*target|pressure/i, /z1.*(nvz|kitchen|soft)/i]
      ),
      rule(
        "z2_target",
        ["z2", "picklr zone", "heat zone", "offensive target", "dink target"],
        "Z2 is your primary offensive dink target; creates angles and time.",
        [/z2|picklr.*zone|heat.*zone|offensive.*target/i]
      ),
      rule(
        "z3_reset",
        ["z3", "transition", "reset", "most important"],
        "Z3 (transition) is the work zone — reset to advance to Z2.",
        [/z3|transition|reset/i]
      ),
      rule(
        "serve_return",
        ["serve", "return", "deep", "middle"],
        "Serve deep (often middle). Return deep/high, then advance with a split step.",
        [/serve.*deep/i, /return.*deep|high/i]
      ),
      rule(
        "third_drop",
        ["third", "fifth", "drop", "drive", "rushed", "sitter"],
        "If rushed, drop/reset. If sitter, drive to body/open lane.",
        [/rushed.*drop|reset/i, /sitter.*drive/i]
      ),
      rule(
        "energy_dial",
        ["energy", "arc", "flatten", "de-escalate", "attack"],
        "Arc to de-escalate and add margin; flatten to attack from balance.",
        [/add.*arc|lift/i, /flatten|attack/i]
      ),
      rule(
        "dink_cross",
        ["dink", "crosscourt", "safe", "zones"],
        "Safest dink: crosscourt into Z2; call your target zone out loud.",
        [/crosscourt.*dink|z2/i]
      ),
    ];
    return rules;
  }

  function rule(id, keywords, reason, optionMatchers) {
    return { id, keywords, reason, optionMatchers: optionMatchers || [] };
  }

  function suggestAnswer(questionText, options) {
    const q = normalizeText(questionText || "").toLowerCase();
    const scored = P4_BANK.map((r) => ({ r, score: scoreRule(r, q) }))
      .sort((a, b) => b.score - a.score);

    const top = scored[0];
    if (!top || top.score <= 0) {
      return { letter: null, reason: genericGuidance(q) };
    }

    // Try to match an option that aligns with the rule
    const match = pickOptionForRule(top.r, options);
    if (match) {
      return { letter: match.letter, reason: top.r.reason };
    }
    // If no option match, provide guiding rationale only
    return { letter: null, reason: top.r.reason };
  }

  function scoreRule(rule, q) {
    let score = 0;
    for (const kw of rule.keywords) {
      if (q.includes(kw)) score += 2;
    }
    // Bonus for exact phrases common in bank
    if (/b1|b4|top half/.test(q) && rule.id === "ball_top") score += 3;
    if (/b2|b3|bottom half/.test(q) && rule.id === "ball_bottom") score += 3;
    if (/z2|heat|picklr/.test(q) && rule.id === "z2_target") score += 2;
    if (/transition|z3/.test(q) && rule.id === "z3_reset") score += 2;
    return score;
  }

  function pickOptionForRule(rule, options) {
    // First pass: regex match on option text
    for (const rx of rule.optionMatchers || []) {
      for (const opt of options) {
        if (rx.test(opt.text)) return opt;
      }
    }
    // Second pass: heuristic contains
    const heuristics = [
      { id: "ball_top", needles: ["top", "drive", "speed", "flatten", "b1", "b4"] },
      { id: "ball_bottom", needles: ["bottom", "lift", "arc", "reset", "drop", "b2", "b3"] },
      { id: "z2_target", needles: ["z2", "picklr", "heat", "offensive", "target"] },
      { id: "z3_reset", needles: ["z3", "transition", "reset"] },
      { id: "serve_return", needles: ["serve", "return", "deep", "middle", "split step"] },
      { id: "third_drop", needles: ["third", "fifth", "drop", "drive", "rushed", "sitter"] },
      { id: "dink_cross", needles: ["dink", "crosscourt", "z2"] },
      { id: "grip", needles: ["continental", "eastern", "palms", "knuckles", "mirror"] },
      { id: "fundamentals", needles: ["contact in front", "balance", "simplest", "bounce"] },
      { id: "energy_dial", needles: ["arc", "flatten", "attack", "margin"] },
    ];
    const h = heuristics.find((h) => h.id === rule.id);
    if (!h) return null;
    const scored = options
      .map((opt) => ({ opt, score: scoreNeedles(opt.text.toLowerCase(), h.needles) }))
      .sort((a, b) => b.score - a.score);
    return scored[0] && scored[0].score > 0 ? scored[0].opt : null;
  }

  function scoreNeedles(text, needles) {
    let s = 0;
    for (const n of needles) if (text.includes(n)) s += 1;
    return s;
  }

  function genericGuidance(q) {
    if (/b1|b4|top/.test(q)) return "Top half drives; bottom half lifts. Attack only from balance.";
    if (/b2|b3|bottom|reset|drop/.test(q)) return "Use bottom-half contact to add arc and reset under pressure.";
    if (/z2|z3|z4|z1|zone/.test(q)) return "Z4 build; Z3 reset/advance; Z2 pressure; Z1 finish soft.";
    if (/serve|return/.test(q)) return "Serve deep; return deep/high then move in with a split step.";
    if (/third|fifth/.test(q)) return "If rushed, drop; if sitter, drive to body/open lane.";
    if (/dink/.test(q)) return "Safest: crosscourt into Z2. Call your target zone.";
    if (/grip|paddle face/.test(q)) return "Continental/Eastern; paddle mirrors palms/knuckles for aim.";
    return "Favor the simplest, most repeatable shot. Contact in front, stay balanced.";
  }

  // Bootstrap overlay
  const ui = createOverlay();

  // Keyboard fallback: Shift+Space toggles listening
  window.addEventListener("keydown", (e) => {
    if (e.shiftKey && e.code === "Space") {
      e.preventDefault();
      toggleListening();
    }
  });

  // Auto-read on navigation changes
  const observer = new MutationObserver(() => {
    // Debounce reads
    if (!state.speaking) {
      setTimeout(() => {
        // Refresh context silently; only speak if listening
        const ctx = getQuestionContext();
        if (ctx && ctx.questionText && state.isListening) {
          readCurrentQA();
        }
      }, 300);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();


