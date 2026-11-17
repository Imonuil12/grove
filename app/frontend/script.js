// Guest state is scoped to this browser tab and never stored in localStorage.
function isGuest() { return !!sessionStorage.getItem("guestToken"); }
function learningStorage() { return isGuest() ? sessionStorage : localStorage; }
async function startGuest(returnTo) {
  try {
    const { startGuestSession } = await import("./auth/guestSession.js");
    await startGuestSession(BASE_URL, returnTo);
  } catch (e) { alert(e.message); }
}
// Signed in with a real account (not a guest, not signed out).
function hasAccount() {
  return !isGuest() && !!(localStorage.getItem("userEmail") || localStorage.getItem("idToken") || localStorage.getItem("accessToken"));
}
function endGuest() {
  const token = sessionStorage.getItem("guestToken");
  if (token) fetch(`${BASE_URL}/auth/guest`, {method: "DELETE", headers: {"X-Guest-Session": token}}).catch(() => {});
  sessionStorage.clear();
  window.location.href = "index.html";
}
// Backend URL. In production the backend serves these pages, so the API is on
// the same origin. Local static dev servers (ports 5500-5599) call port 8000.
const BASE_URL = window.API_BASE_URL || (/^55\d\d$/.test(location.port)
  ? `http://${location.hostname || "127.0.0.1"}:8000`
  : location.origin);
const API_URL = `${BASE_URL}/chat`;

let currentDrugData = null;
let currentLearningPlan = null;
let savedArchetype = null;

// path.html / lesson.html have no archetype picker of their own — this pulls
// the user's saved choice (set in the intake form) once, so the floating
// chatbot there still speaks in their chosen persona instead of always
// falling back to the default.
async function loadSavedArchetype() {
  if (savedArchetype || !getUsername()) return;
  try {
    const r = await apiFetch(`${BASE_URL}/profile/${encodeURIComponent(getUsername())}`);
    if (!r.ok) return;
    const d = await r.json();
    savedArchetype = d.archetype || null;
  } catch (e) {
    // Non-fatal — chat just falls back to the default persona.
  }
}

function getUsername() {
  if (isGuest()) {
    const gid = sessionStorage.getItem("guestIdentity");
    if (gid) return gid;
  }
  let email = localStorage.getItem("userEmail");
  if (!email) {
    const token = localStorage.getItem("idToken") || localStorage.getItem("accessToken");
    if (token) {
      try {
        const parts = token.split(".");
        if (parts.length >= 2) {
          const padded = parts[1] + "=".repeat((4 - (parts[1].length % 4)) % 4);
          const claims = JSON.parse(atob(padded.replace(/-/g, "+").replace(/_/g, "/")));
          email = claims.email || claims["cognito:username"] || claims.username || claims.sub;
          if (email) localStorage.setItem("userEmail", email);
        }
      } catch (e) {
        // Identity recovery is best-effort; the backend validates the token.
      }
    }
  }
  // Signed out: no identity. (Older builds invented a "user_xxxx" account here.)
  return email || null;
}
try { localStorage.removeItem("anonUserIdentity"); } catch (e) {}

async function apiFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (isGuest()) {
    headers.set("X-Guest-Session", sessionStorage.getItem("guestToken"));
    const response = await window.fetch(url, {...options, headers});
    if (response.status === 401) {
      sessionStorage.clear();
      alert("Your guest session ended. Choose Try without an account to start again.");
      window.location.href = "index.html";
    }
    return response;
  }
  let cognitoToken = localStorage.getItem("idToken") || localStorage.getItem("accessToken");
  const turnstileSession = localStorage.getItem("turnstileSessionToken");
  if (localStorage.getItem("userEmail")) {
    try {
      const { getValidIdToken } = await import("./auth/authService.js");
      const refreshedToken = await getValidIdToken();
      if (refreshedToken) cognitoToken = refreshedToken;
    } catch (error) {
      console.warn("Could not refresh the Cognito session:", error);
    }
  }
  if (cognitoToken) headers.set("Authorization", `Bearer ${cognitoToken}`);
  if (turnstileSession) headers.set("X-Turnstile-Session", turnstileSession);
  const response = await window.fetch(url, { ...options, headers });
  // Only a real session that expired goes to the login page; signed-out visitors
  // just get the 401 and the page shows its own "sign in" prompt.
  if (response.status === 401 && cognitoToken) {
    localStorage.removeItem("turnstileSessionToken");
    localStorage.removeItem("turnstileSessionExpiresAt");
    if (!window.location.pathname.endsWith("/login.html")) {
      window.location.href = "login.html";
    }
  }
  return response;
}

function getSelectedDrug() {
  const el = document.getElementById("drugSelect");
  if (el?.value) return el.value;
  // Pages like lesson.html have no drug picker of their own — fall back to
  // the drug the current lesson/path was opened with.
  if (typeof lessonState !== "undefined" && lessonState && lessonState.drug) return lessonState.drug;
  return getUrlParam("drug") || "amoxicillin";
}

function getSelectedArchetype() {
  // The intake form's chip picker is now the primary source (so the user
  // actively chooses instead of a passive sidebar dropdown they might never
  // touch). Fall back to a legacy #archetypeSelect element for pages
  // (like chatbot.html) that still have one.
  const chip = document.querySelector('.in-chips[data-id="in_archetype"] .in-chip.in-selected');
  if (chip) return chip.textContent.trim();
  const el = document.getElementById("archetypeSelect");
  if (el) return el.value;
  return savedArchetype || "Needs more explanations";
}

function showTab(tab, btn = null) {
  document.querySelectorAll(".tab").forEach((t) => {
    t.style.display = "none";
  });
  document.querySelectorAll(".nav-btn").forEach((b) => {
    b.classList.remove("active");
  });
  const activeTab = document.getElementById(tab);
  if (activeTab) activeTab.style.display = "block";
  if (btn) btn.classList.add("active");
}

function logout() {
  if (isGuest()) { endGuest(); return; }
  localStorage.clear();
  renderAuthSection();
  const guestMsg = `<div class="progress-card"><p>Please log in to use this feature.</p></div>`;
  ["planContent", "lessonsContent", "checkpointContent", "progressContent"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = guestMsg;
  });
  const quizContent = document.getElementById("quizContent");
  if (quizContent) quizContent.innerHTML = `<div class="progress-card"><p>Please log in to take the quiz.</p></div>`;
}

function closeLogin() {
  const modal = document.getElementById("loginModal");
  if (modal) modal.style.display = "none";
}

async function handleLogin() {
  window.location.href = "login.html";
}



function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// The chatbot UI lives in chat-core.js (engine), chatbot.html (full page) and
// chat-widget.js (floating widget). renderSafetyWarning stays here because
// chat-quiz.js uses it for questions asked mid-quiz.
function renderSafetyWarning(warningText, container = null) {
  const chatBox = container || document.getElementById("chatBox");
  if (!chatBox || !warningText) return;

  chatBox.querySelectorAll(".typing").forEach((el) => el.remove());

  const banner = document.createElement("div");
  banner.className = "safety-warning-banner";
  banner.setAttribute("role", "alert");

  const header = document.createElement("div");
  header.className = "safety-warning-header";
  header.innerHTML = `
    <span class="safety-warning-icon" aria-hidden="true">⚠️</span>
    <span class="safety-warning-title">CLINICAL SAFETY ALERT</span>
    <span class="safety-warning-badge">High Priority</span>
  `;

  const body = document.createElement("div");
  body.className = "safety-warning-body";
  body.textContent = warningText;

  const footer = document.createElement("div");
  footer.className = "safety-warning-footer";
  footer.textContent = "Clinical safety guardrail: Please discuss potential contraindications and drug interactions with your clinician or pharmacist.";

  banner.appendChild(header);
  banner.appendChild(body);
  banner.appendChild(footer);
  chatBox.appendChild(banner);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function loadDrugContent() {
  const drug = getSelectedDrug();
  try {
    const response = await apiFetch(`${BASE_URL}/drug-content/${drug}`);
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();
    currentDrugData = data;
    renderInitialQuiz(data);
  } catch (error) {
    console.error("Failed to load drug content:", error);
  }
}


let intakeSlide = 0;
const INTAKE_TOTAL = 5;

function renderIntakeForm() {
  const el = document.getElementById("intakeContent");
  if (!el) return;

  el.innerHTML = `
    <style>
      .in-chip {
        padding: 7px 14px; border-radius: 20px; border: 1px solid #d1d5db;
        font-size: 13px; color: #6b7280; cursor: pointer; display: inline-block;
        transition: all 0.15s; user-select: none;
      }
      .in-chip:hover { border-color: #2f855a; color: #2f855a; }
      .in-chip.in-selected { background: #e2f0e7; border-color: #2f855a; color: #225f40; font-weight: 600; }
      .in-chips { display: flex; flex-wrap: wrap; gap: 8px; }
      .in-toggle-row {
        display: flex; align-items: center; justify-content: space-between;
        padding: 10px 14px; border: 1px solid #e5e7eb; border-radius: 8px;
        background: #f9fafb; margin-bottom: 8px;
      }
      .in-toggle-row span { font-size: 14px; color: #374151; }
      .in-slide { display: none; }
      .in-slide.in-active { display: block; }
      .in-q { margin-bottom: 20px; }
      .in-label { font-size: 14px; font-weight: 600; display: block; margin-bottom: 8px; color: #1e2e25; }
      .in-sublabel { font-size: 12px; color: #6b7280; margin-bottom: 8px; display: block; }
      .in-input { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; box-sizing: border-box; }
      .in-select { width: 100%; padding: 10px 12px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; background: white; }
      .in-range-wrap { display: flex; align-items: center; gap: 12px; }
      .in-range-wrap input[type=range] { flex: 1; accent-color: #2f855a; }
      .in-range-val { font-size: 14px; font-weight: 600; min-width: 56px; color: #1e2e25; }
      .step-dot {
        width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center;
        justify-content: center; font-size: 12px; font-weight: 600; flex-shrink: 0;
        transition: all 0.3s;
      }
      .step-dot.done { background: #2f855a; color: white; }
      .step-dot.active { background: #e2f0e7; color: #2f855a; border: 2px solid #2f855a; }
      .step-dot.todo { background: #f3f4f6; color: #9ca3af; border: 2px solid #e5e7eb; }
      .step-line { flex: 1; height: 2px; background: #e5e7eb; margin: 0 4px; margin-bottom: 18px; transition: background 0.3s; }
      .step-line.done { background: #2f855a; }
    </style>

    <div style="max-width: 640px;"><div style="width: 100%; min-width: 0; box-sizing: border-box;">

      <!-- Step indicator -->
      <div style="margin-bottom: 28px;">
        <div style="display: flex; align-items: center; margin-bottom: 6px;" id="inStepDots"></div>
        <div style="display: flex; justify-content: space-between; padding: 0 2px;" id="inStepLabels"></div>
      </div>

      <!-- Slide 0: About Me -->
      <div id="in-slide-0" class="in-slide in-active">
        <p style="font-size:11px; font-weight:600; letter-spacing:.08em; color:#2f855a; text-transform:uppercase; margin-bottom:6px;">About Me</p>
        <h2 style="font-size:18px; font-weight:600; margin-bottom:6px;">Let's start with the basics</h2>
        <p style="font-size:14px; color:#6b7280; margin-bottom:24px; line-height:1.6;">This helps us personalize your experience.</p>

        <div class="in-q">
        <label class="in-label">Date of birth</label>
        <input type="date" id="in_dob" class="in-input" onchange="updateConditionalFields()">
        </div>

        <div class="in-q">
          <label class="in-label">Sex</label>
          <span class="in-sublabel">Biological sex assigned at birth, used for dosing and safety guidance.</span>
          <div class="in-chips" data-id="in_gender">
            ${['Male','Female','Intersex','Prefer not to say'].map(o=>`<div class="in-chip" onclick="inPick(this,'in_gender')">${o}</div>`).join('')}
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">How do you like things explained?</label>
          <span class="in-sublabel">This sets the tone of your lessons and chatbot answers.</span>
          <div class="in-chips" data-id="in_archetype">
            ${['Needs more explanations','The Skeptic','Trying not to get Worse',"All In Until I'm Not"].map(o=>`<div class="in-chip" onclick="inPick(this,'in_archetype')">${o}</div>`).join('')}
          </div>
        </div>
   <!-- Gated: only shown after DOB + sex confirmed -->
  <div id="slide0_rest" style="display:none;">

    <div class="in-q">
      <label class="in-label">How comfortable are you with medical information?</label>
      <select id="in_experience_level" class="in-select" onchange="saveLearningPreferences({ experience_level: this.value })">
        <option value="">Select...</option>
        <option value="beginner">Beginner (prefer simple explanations)</option>
        <option value="intermediate">Intermediate (some familiarity)</option>
        <option value="advanced">Advanced (comfortable with medical terms)</option>
      </select>
    </div>

    <div id="adult_lifestyle_fields">
      <div class="in-q">
        <label class="in-label">Average alcoholic drinks per week</label>
        <div class="in-range-wrap">
          <input type="range" min="0" max="30" step="1" value="0" id="in_alcohol_drinks"
            oninput="document.getElementById('in_alcohol_val').textContent=this.value">
          <span class="in-range-val" id="in_alcohol_val">0</span>
          <span style="font-size:13px; color:#6b7280;">drinks/week</span>
        </div>
      </div>

      <div class="in-q">
        <label class="in-label">Cigarette use</label>
        <select id="in_cigarette_use" class="in-select">
          <option value="">Select...</option>
          <option>Never used</option>
          <option>Former user</option>
          <option>Current user</option>
        </select>
      </div>

      <div class="in-q" id="in_cig_years_wrap" style="display:none;">
        <label class="in-label">How many years did you smoke?</label>
        <input type="number" id="in_cig_years" class="in-input" min="0" placeholder="e.g. 5">
      </div>
    </div>

    <div id="pediatric_warning" style="display:none; margin-top:8px; padding:10px 14px; background:#fef3c7; border:1px solid #f59e0b; border-radius:8px; font-size:13px; color:#92400e;">
      ⚠️ Patient appears to be under 12. Dosing for children differs significantly — consult a clinician.
    </div>

  </div><!-- end slide0_rest -->

  <!-- Confirm button, only visible before rest is revealed -->
  <div id="slide0_confirm_wrap" style="margin-top:16px;">
    <button onclick="confirmSlide0()" style="
      padding:10px 22px; background:#2f855a; border:none;
      border-radius:8px; font-size:14px; color:white; font-weight:600; cursor:pointer;">
      Continue →
    </button>
    <p id="slide0_confirm_error" style="color:#dc2626; font-size:13px; margin-top:8px; display:none;">
      Please enter your date of birth and select a sex to continue.
    </p>
  </div>

</div>


      <!-- Slide 1: Diet -->
      <div id="in-slide-1" class="in-slide">
        <p style="font-size:11px; font-weight:600; letter-spacing:.08em; color:#2f855a; text-transform:uppercase; margin-bottom:6px;">Diet & Hydration</p>
        <h2 style="font-size:18px; font-weight:600; margin-bottom:6px;">Tell us about your eating habits</h2>
        <p style="font-size:14px; color:#6b7280; margin-bottom:24px; line-height:1.6;">What you eat affects how your body absorbs and tolerates medication.</p>

        <div class="in-q">
          <label class="in-label">Meals per day</label>
          <div class="in-chips" data-id="in_meals_per_day">
            ${['1','2','3','4+','I graze'].map((o,i)=>`<div class="in-chip${i===2?' in-selected':''}" onclick="inPick(this,'in_meals_per_day')">${o}</div>`).join('')}
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">How often do you skip meals?</label>
          <div class="in-chips" data-id="in_skips_meals">
            ${['Rarely','Sometimes','Often','Most days'].map((o,i)=>`<div class="in-chip${i===0?' in-selected':''}" onclick="inPick(this,'in_skips_meals')">${o}</div>`).join('')}
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">Water intake</label>
          <div class="in-range-wrap">
            <input type="range" min="0" max="20" step="1" value="8" id="in_water"
              oninput="document.getElementById('in_water_val').textContent=this.value">
            <span class="in-range-val" id="in_water_val">8</span>
            <span style="font-size:13px; color:#6b7280;">cups/day</span>
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">Fruit & vegetable intake</label>
          <div class="in-range-wrap">
          <input type="range" min="0" max="10" step="1" id="in_fruit_veg"
            oninput="document.getElementById('in_fv_val').textContent=this.value">
            <span class="in-range-val" id="in_fv_val">3</span>
            <span style="font-size:13px; color:#6b7280;">servings/day</span>
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">Dietary pattern</label>
          <select id="in_diet_type" class="in-select">
            ${['No restrictions','Vegetarian','Vegan','Low carb / keto','Dairy free','Gluten free','Other'].map(o=>`<option>${o}</option>`).join('')}
          </select>
        </div>

        <div class="in-q">
          <label class="in-label">Do you restrict your calorie intake?</label>
          <div class="in-chips" data-id="in_calorie_restrict">
            ${['No','Yes'].map((o,i)=>`<div class="in-chip${i===0?' in-selected':''}" onclick="inPick(this,'in_calorie_restrict')">${o}</div>`).join('')}
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">Daily caffeine use</label>
          <div class="in-chips" data-id="in_caffeine">
            ${['None','Light (1–2 cups)','Moderate (3–4 cups)','Heavy (5+)'].map((o,i)=>`<div class="in-chip${i===1?' in-selected':''}" onclick="inPick(this,'in_caffeine')">${o}</div>`).join('')}
          </div>
        </div>
      </div>

      <!-- Slide 2: Sleep & Stress -->
      <div id="in-slide-2" class="in-slide">
        <p style="font-size:11px; font-weight:600; letter-spacing:.08em; color:#2f855a; text-transform:uppercase; margin-bottom:6px;">Sleep & Stress</p>
        <h2 style="font-size:18px; font-weight:600; margin-bottom:6px;">How are you feeling lately?</h2>
        <p style="font-size:14px; color:#6b7280; margin-bottom:24px; line-height:1.6;">Stress and sleep can affect how symptoms feel and how you recover.</p>

        <div class="in-q">
          <label class="in-label">Average hours of sleep per night</label>
          <div class="in-range-wrap">
            <input type="range" min="2" max="12" step="1" value="7" id="in_sleep_hours"
              oninput="document.getElementById('in_sleep_val').textContent=this.value+'h'">
            <span class="in-range-val" id="in_sleep_val">7h</span>
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">Sleep quality</label>
          <div class="in-chips" data-id="in_sleep_quality">
            ${['Very poor','Poor','Fair','Good','Excellent'].map((o,i)=>`<div class="in-chip${i===2?' in-selected':''}" onclick="inPick(this,'in_sleep_quality')">${o}</div>`).join('')}
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">Any sleep issues?</label>
          ${inToggle('in_trouble_falling_asleep','Trouble falling asleep')}
          ${inToggle('in_waking_night','Waking up during the night')}
          ${inToggle('in_waking_early','Waking up too early')}
        </div>

        <div class="in-q">
          <label class="in-label">Current stress level</label>
          <div class="in-range-wrap">
            <input type="range" min="1" max="10" step="1" value="5" id="in_stress"
              oninput="document.getElementById('in_stress_val').textContent=this.value+'/10'">
            <span class="in-range-val" id="in_stress_val">5/10</span>
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">Overall mood most days</label>
          <div class="in-chips" data-id="in_mood">
            ${['Low / flat','Anxious','Neutral','Generally okay','Good'].map((o,i)=>`<div class="in-chip${i===2?' in-selected':''}" onclick="inPick(this,'in_mood')">${o}</div>`).join('')}
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">Stress management practices</label>
          <span class="in-sublabel">Select all that apply</span>
          <div class="in-chips in-multi" data-id="in_stress_practices">
            ${['Meditation','Exercise','Journaling','Therapy','None'].map(o=>`<div class="in-chip" onclick="inMultiPick(this)">${o}</div>`).join('')}
          </div>
        </div>
      </div>

      <!-- Slide 3: Activity -->
      <div id="in-slide-3" class="in-slide">
        <p style="font-size:11px; font-weight:600; letter-spacing:.08em; color:#2f855a; text-transform:uppercase; margin-bottom:6px;">Physical Activity</p>
        <h2 style="font-size:18px; font-weight:600; margin-bottom:6px;">How active are you?</h2>
        <p style="font-size:14px; color:#6b7280; margin-bottom:24px; line-height:1.6;">Activity affects recovery time, energy, and how your body processes medication.</p>

        <div class="in-q">
          <label class="in-label">Days per week you exercise</label>
          <div class="in-range-wrap">
            <input type="range" min="0" max="7" step="1" value="3" id="in_exercise_days"
              oninput="document.getElementById('in_ex_val').textContent=this.value+' days'">
            <span class="in-range-val" id="in_ex_val">3 days</span>
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">Type of activity</label>
          <span class="in-sublabel">Select all that apply</span>
          <div class="in-chips in-multi" data-id="in_activity_types">
            ${['Walking','Running','Strength training','Yoga / stretching','Cycling','Sports','None'].map(o=>`<div class="in-chip" onclick="inMultiPick(this)">${o}</div>`).join('')}
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">Daily routine</label>
          <div class="in-chips" data-id="in_sedentary">
            ${['Mostly sitting','Mix of sitting & moving','Mostly on my feet','Physically demanding job'].map((o,i)=>`<div class="in-chip${i===1?' in-selected':''}" onclick="inPick(this,'in_sedentary')">${o}</div>`).join('')}
          </div>
        </div>

        <div class="in-q">
          <label class="in-label">Physical limitations</label>
          ${inToggle('in_chronic_pain','Chronic pain or injury')}
          ${inToggle('in_limited_mobility','Limited mobility')}
        </div>
      </div>

      <!-- Slide 4: Medical -->
      <div id="in-slide-4" class="in-slide">
        <p style="font-size:11px; font-weight:600; letter-spacing:.08em; color:#2f855a; text-transform:uppercase; margin-bottom:6px;">Medical</p>
        <h2 style="font-size:18px; font-weight:600; margin-bottom:6px;">Medical background</h2>
        <p style="font-size:14px; color:#6b7280; margin-bottom:24px; line-height:1.6;">This helps flag anything worth discussing with your clinician.</p>

        <div class="in-q">
          <label class="in-label">Allergies & reactions</label>
          ${inToggle('penicillin_allergy','Penicillin allergy')}
          ${inToggle('anaphylaxis_history','Severe allergy or anaphylaxis history')}
        </div>

        <div class="in-q">
          <label class="in-label">Medical conditions</label>
          ${inToggle('mono_suspected','Mono (EBV) suspected recently')}
          ${inToggle('kidney_disease','Kidney disease')}
        </div>

        <div class="in-q">
          <label class="in-label">Life stage</label>

          <div id="female_fields_group">
            <div id="breastfeeding_group">
              ${inToggle('breastfeeding','Breastfeeding')}
            </div>
            <label class="in-label" style="margin-top:12px;">Pregnancy status</label>
            <select id="pregnancy_status" class="in-select">
              <option value="Unknown">Unknown</option>
              <option value="Not pregnant">Not pregnant</option>
              <option value="Pregnant">Pregnant</option>
              <option value="Trying">Trying</option>
              <option value="Unsure">Unsure</option>
            </select>
          </div>

          <div id="elderly_group" style="display:none; margin-top:12px;">
            <label class="in-label">Elderly considerations</label>
            ${inToggle('fall_risk', 'Increased fall risk')}
            ${inToggle('polypharmacy', 'Taking 5+ medications (polypharmacy)')}
            ${inToggle('renal_decline', 'Known age-related kidney decline')}
          </div>

        </div>

        <div class="in-q">
          <label class="in-label">Current medications</label>
          <input type="text" id="meds_text" class="in-input" placeholder="e.g. warfarin, methotrexate">
        </div>

        <div id="intakeWarnings" style="margin-top:8px;"></div>
      </div>

      <!-- Nav -->
      <div style="display:flex; justify-content:space-between; align-items:center; margin-top:28px; padding-top:20px; border-top:1px solid #e5e7eb;">
        <button id="inBtnBack" onclick="inPrevSlide()" style="
          padding:10px 18px; background:transparent; border:1px solid #d1d5db;
          border-radius:8px; font-size:14px; color:#6b7280; cursor:pointer; visibility:hidden;">
          Back
        </button>
        <button id="inBtnNext" onclick="inNextSlide()" style="
          padding:10px 22px; background:#2f855a; border:none;
          border-radius:8px; font-size:14px; color:white; font-weight:600; cursor:pointer;">
          Next →
        </button>
      </div>
    </div>
  `;



  intakeSlide = 0;
  inUpdateNav();
}

// ── Helper: toggle row ───────────────────────────────────────
function inToggle(id, label, checked = false) {
  return `
    <div class="in-toggle-row">
      <span>${label}</span>
      <input type="checkbox" id="${id}"${checked ? ' checked' : ''}
        style="width:18px; height:18px; accent-color:#2f855a; cursor:pointer;">
    </div>
  `;
}

// ── Chip helpers ─────────────────────────────────────────────
function inPick(el, groupId) {
  document.querySelectorAll(`.in-chips[data-id="${groupId}"] .in-chip`)
    .forEach(c => c.classList.remove('in-selected'));
  el.classList.add('in-selected');

  // Trigger conditional logic on any chip pick, not just gender
  setTimeout(updateConditionalFields, 0);

  // The learning style applies everywhere (chatbot, lessons, chat quiz) as soon as it's picked.
  if (groupId === 'in_archetype') saveLearningPreferences({ archetype: el.textContent.trim() });
}

async function saveLearningPreferences(prefs) {
  try {
    const r = await apiFetch(`${BASE_URL}/preferences`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: getUsername(), ...prefs }),
    });
    if (!r.ok) return null;
    const data = await r.json();
    if (data.archetype) savedArchetype = data.archetype;
    document.dispatchEvent(new CustomEvent("mys:preferences", { detail: data }));
    return data;
  } catch (e) {
    console.warn("Could not save learning preferences:", e);
    return null;
  }
}

function inMultiPick(el) { el.classList.toggle('in-selected'); }
function inGetChip(groupId) {
  const sel = document.querySelector(`.in-chips[data-id="${groupId}"] .in-chip.in-selected`);
  return sel ? sel.textContent.trim() : '';
}
function inGetMulti(groupId) {
  return [...document.querySelectorAll(`.in-chips[data-id="${groupId}"] .in-chip.in-selected`)].map(c => c.textContent.trim());
}
function inVal(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  if (el.type === 'checkbox') return el.checked;
  if (el.type === 'range') return parseInt(el.value);
  return el.value;
}

// ── Step indicator ───────────────────────────────────────────
const INTAKE_STEPS = ['About Me','Diet','Sleep & Stress','Activity','Medical'];

function inUpdateNav() {
  // Dots + lines
  const dotsEl = document.getElementById('inStepDots');
  const labelsEl = document.getElementById('inStepLabels');
  if (!dotsEl) return;

  let dotsHTML = '';
  let labelsHTML = '';
  INTAKE_STEPS.forEach((s, i) => {
    const cls = i < intakeSlide ? 'done' : i === intakeSlide ? 'active' : 'todo';
    const icon = i < intakeSlide ? '✓' : i + 1;
    dotsHTML += `<div class="step-dot ${cls}">${icon}</div>`;
    if (i < INTAKE_STEPS.length - 1) {
      dotsHTML += `<div class="step-line ${i < intakeSlide ? 'done' : ''}"></div>`;
    }
    labelsHTML += `<span style="font-size:11px; color:${i === intakeSlide ? '#2f855a' : '#9ca3af'}; font-weight:${i === intakeSlide ? '600' : '400'}; text-align:center; width:${100/INTAKE_STEPS.length}%;">${s}</span>`;
  });
  dotsEl.innerHTML = dotsHTML;
  labelsEl.innerHTML = labelsHTML;

  // Back/next buttons
  const back = document.getElementById('inBtnBack');
  const next = document.getElementById('inBtnNext');
  if (back) back.style.visibility = intakeSlide === 0 ? 'hidden' : 'visible';
  if (next) next.textContent = intakeSlide === INTAKE_STEPS.length - 1 ? 'Save intake' : 'Next →';
}

function inGoToSlide(n) {
  document.getElementById('in-slide-' + intakeSlide).classList.remove('in-active');
  intakeSlide = n;
  document.getElementById('in-slide-' + intakeSlide).classList.add('in-active');
  inUpdateNav();
  document.getElementById('intakeContent').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function inNextSlide() {
  // If on slide 0 and the rest hasn't been revealed yet, force confirm first
  if (intakeSlide === 0) {
    const rest = document.getElementById("slide0_rest");
    if (rest && rest.style.display === "none") {
      confirmSlide0();
      return;
    }


  }

  if (intakeSlide < INTAKE_STEPS.length - 1) {
    inGoToSlide(intakeSlide + 1);
  } else {
    submitIntake();
  }
}
function inPrevSlide() {
  if (intakeSlide > 0) inGoToSlide(intakeSlide - 1);
}

// ── Replace your existing submitIntake() with this ───────────
async function submitIntake() {
  if (!requireLogin()) return;
  const intakeWarnings = document.getElementById("intakeWarnings");
  let level = inVal("in_experience_level") || "Beginner";

  level = level.toLowerCase();

  if (level.includes("beginner")) level = "beginner";
  else if (level.includes("intermediate")) level = "intermediate";
  else if (level.includes("advanced")) level = "advanced";
  const payload = {
    username: getUsername(),
    drug: getSelectedDrug(),
    // Medical (existing fields your backend expects)
    penicillin_allergy: inVal('penicillin_allergy') || false,
    anaphylaxis_history: inVal('anaphylaxis_history') || false,
    mono_suspected: inVal('mono_suspected') || false,
    kidney_disease: inVal('kidney_disease') || false,
    breastfeeding: inVal('breastfeeding') || false,
    pregnancy_status: inVal('pregnancy_status') || 'Unknown',

    experience_level: level,
    meds_text: inVal('meds_text') || '',
    // Lifestyle fields (stored in intake blob)
    dob: inVal('in_dob') || '',
    gender: inGetChip('in_gender'),
    archetype: inGetChip('in_archetype') || 'Needs more explanations',
    alcohol_drinks_per_week: inVal('in_alcohol_drinks') || 0,
    cigarette_use: inVal('in_cigarette_use') || '',
    cigarette_years: inVal('in_cig_years') || 0,
    meals_per_day: inGetChip('in_meals_per_day'),
    skips_meals: inGetChip('in_skips_meals'),
    water_cups: inVal('in_water') || 0,
    fruit_veg_servings: inVal('in_fruit_veg') || 0,
    diet_type: inVal('in_diet_type') || '',
    calorie_restrict: inGetChip('in_calorie_restrict'),
    caffeine: inGetChip('in_caffeine'),
    sleep_hours: inVal('in_sleep_hours') || 7,
    sleep_quality: inGetChip('in_sleep_quality'),
    trouble_falling_asleep: inVal('in_trouble_falling_asleep') || false,
    waking_night: inVal('in_waking_night') || false,
    waking_early: inVal('in_waking_early') || false,
    stress_level: inVal('in_stress') || 5,
    mood: inGetChip('in_mood'),
    stress_practices: inGetMulti('in_stress_practices'),
    exercise_days: inVal('in_exercise_days') || 0,
    activity_types: inGetMulti('in_activity_types'),
    sedentary_level: inGetChip('in_sedentary'),
    chronic_pain: inVal('in_chronic_pain') || false,
    limited_mobility: inVal('in_limited_mobility') || false,
    fall_risk: inVal('fall_risk') || false,
    polypharmacy: inVal('polypharmacy') || false,
    renal_decline: inVal('renal_decline') || false

  };

  learningStorage().setItem("experienceLevel", payload.experience_level);

  try {
    const response = await apiFetch(`${BASE_URL}/intake`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();
    clearIntakeDraft();
    if (intakeWarnings) {
      intakeWarnings.innerHTML = `
        <div class="progress-card">
          <h3>✓ Saved — Warnings</h3>
          ${data.warnings.map(w => `<p>• ${w}</p>`).join("")}
        </div>
      `;
    }
  } catch (error) {
    console.error("Failed to submit intake:", error);
    if (intakeWarnings) intakeWarnings.innerHTML = `<p>Could not save intake. Please complete the security check first.</p>`;
  }
}



function renderAuthSection() {
  const container = document.getElementById("authSection");
  if (!container) return;
  const user = getUsername();
  if (isGuest()) {
    container.innerHTML = `<strong>Guest play</strong><p>Progress lasts only for this visit. It ends when you close this tab, leave guest play, or the temporary session expires.</p><button class="nav-btn" onclick="goToLogin()">Log in / Sign up</button>`;
    return;
  }
  if (user) {
    container.innerHTML = `
      <p style="margin-bottom:4px; font-size:13px; color:#aab;">Logged in as:</p>
      <strong style="font-size:13px; word-break:break-all;">${user}</strong>
    `;
  } else {
    container.innerHTML = `
      <button class="nav-btn" onclick="goToLogin()">Login / Signup</button><button class="nav-btn" onclick="startGuest()">Try without an account</button><p>Explore lessons and quizzes. Guest progress is temporary.</p>
    `;
  }
}

function goToLogin() {
  if (isGuest()) {
    if (!confirm("Guest progress will be discarded. Continue to login or signup?")) return;
    endGuest();
  }
  window.location.href = "login.html";
}

function renderInitialQuiz(data) {
  const quizContent = document.getElementById("quizContent");
  if (!quizContent) return;
  if (!getUsername()) {
    quizContent.innerHTML = `<div class="progress-card"><p>Please log in to take the quiz.</p></div>`;
    return;
  }
  quizContent.innerHTML = "";
  Object.entries(data.categories).forEach(([category, objectives]) => {
    objectives.forEach((obj) => {
      const card = document.createElement("div");
      card.className = "assessment-card";
      card.innerHTML = `
        <h3>${obj.oid} — ${category}</h3>
        <p>${obj.question}</p>
        <input type="text" data-oid="${obj.oid}" placeholder="Type your answer here">
      `;
      quizContent.appendChild(card);
    });
  });
}

async function submitInitialQuiz() {
  if (!requireLogin()) return;
  const quizResults = document.getElementById("quizResults");
  const inputs = document.querySelectorAll("#quizContent input[data-oid]");
  const answers = {};
  inputs.forEach((input) => { answers[input.dataset.oid] = input.value.trim(); });
  try {
    const response = await apiFetch(`${BASE_URL}/initial-assessment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: getUsername(), drug: getSelectedDrug(), answers: answers })
    });
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();
    quizResults.innerHTML = `
      <div class="progress-card">
        <h3>Initial Quiz Results</h3>
        ${data.results.map(r => `<p>${r.oid}: ${r.message}</p>`).join("")}
      </div>
    `;
    await loadLearningPlan();
    await loadProgress();
  } catch (error) {
    console.error("Failed to submit initial quiz:", error);
    quizResults.innerHTML = `<p>Could not score initial quiz. Please complete the security check first.</p>`;
  }
}

async function loadLearningPlan() {
  const planContent = document.getElementById("planContent");
  const lessonsContent = document.getElementById("lessonsContent");
  const checkpointContent = document.getElementById("checkpointContent");

  // *** GUARD: don't make API call with null username ***
  if (!getUsername()) {
    const msg = `<div class="progress-card"><p>Please complete the security check to see your learning plan.</p></div>`;
    if (planContent) planContent.innerHTML = msg;
    if (lessonsContent) lessonsContent.innerHTML = msg;
    if (checkpointContent) checkpointContent.innerHTML = msg;
    return;
  }

  try {
    const response = await apiFetch(
      `${BASE_URL}/learning-plan/${getSelectedDrug()}?username=${encodeURIComponent(getUsername())}`
    );
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();
    currentLearningPlan = data;

    if (planContent) {
      if (!data.has_started) {
        planContent.innerHTML = `
          <div class="progress-card">
            <h3>Learning Plan</h3>
            <p>No learning plan yet. Complete the initial quiz to generate a personalized lesson plan.</p>
          </div>
        `;
      } else if (!data.queued_objectives.length) {
        planContent.innerHTML = `
          <div class="progress-card">
            <h3>Learning Plan</h3>
            <p>Everything is currently mastered.</p>
          </div>
        `;
      } else {
        planContent.innerHTML = data.queued_objectives.map(obj => `
          <div class="lesson-card">
            <h3>${obj.oid} — ${obj.category}</h3>
            <p>${obj.objective_text}</p>
          </div>
        `).join("");
      }
    }

    if (lessonsContent) {
lessonsContent.innerHTML = data.queued_objectives.map(obj => {
  let lessonText = obj.lesson_text;

  // FIX: handle object vs string
  if (typeof lessonText === "object") {
    const level = (learningStorage().getItem("experienceLevel") || "beginner").toLowerCase();
    lessonText = lessonText[level] || lessonText["beginner"];
  }

  lessonText = String(lessonText || "").replace(/\n/g, "<br>");

  return `
    <div class="lesson-card">
      <h3>${obj.oid} — ${obj.category}</h3>
      <p>${obj.objective_text}</p>
      <p>${lessonText}</p>
    </div>
  `;
}).join("");    }

    if (checkpointContent) {
      checkpointContent.innerHTML = data.queued_objectives.map(obj => {
        return `
          <div class="assessment-card">
            <h3>${obj.oid} — ${obj.category}</h3>
            <p>${obj.question}</p>
            <input type="text" data-oid="${obj.oid}" placeholder="Type your new answer here">
          </div>
        `;
      }).join("");
}
  } catch (error) {
    console.error("Failed to load learning plan:", error);
    if (planContent) planContent.innerHTML = `<p>Could not load learning plan. Please complete the security check first.</p>`;
  }
}

async function submitCheckpoint() {
  if (!requireLogin()) return;
  const checkpointResults = document.getElementById("checkpointResults");
  const inputs = document.querySelectorAll("#checkpointContent input[data-oid]");
  const answers = {};
  inputs.forEach((input) => { answers[input.dataset.oid] = input.value.trim(); });
  try {
    const response = await apiFetch(`${BASE_URL}/checkpoint`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: getUsername(), drug: getSelectedDrug(), answers: answers })
    });
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();
    checkpointResults.innerHTML = `
      <div class="progress-card">
        <h3>Checkpoint Results</h3>
        ${data.results.map(r => `<p>${r.oid}: ${r.message}</p>`).join("")}
        <p><strong>All mastered:</strong> ${data.all_mastered ? "Yes" : "Not yet"}</p>
      </div>
    `;
    await loadLearningPlan();
    await loadProgress();
  } catch (error) {
    console.error("Failed to submit checkpoint:", error);
    checkpointResults.innerHTML = `<p>Could not score checkpoint. Please complete the security check first.</p>`;
  }
}

async function loadProgress() {
  const progressContent = document.getElementById("progressContent");
  if (!progressContent) return;

  // *** GUARD: don't make API call with null username ***
  if (!getUsername()) {
    progressContent.innerHTML = `<div class="progress-card"><p>Please complete the security check to see your progress.</p></div>`;
    return;
  }

  try {
    const response = await apiFetch(
      `${BASE_URL}/progress/${getSelectedDrug()}?username=${encodeURIComponent(getUsername())}`
    );
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();
    progressContent.innerHTML = `
      <div class="progress-card">
        <h3>${data.drug} Progress</h3>
        <p>Known: ${data.known} / ${data.total}</p>
      </div>
      ${Object.entries(data.by_category).map(([category, stats]) => `
        <div class="progress-card">
          <h3>${category}</h3>
          <p>${stats.known} / ${stats.total} mastered</p>
        </div>
      `).join("")}
      <div class="progress-card">
        <h3>Latest Results</h3>
        ${data.last_results.map(r => `<p>${r.oid}: ${r.message}</p>`).join("")}
      </div>
    `;
  } catch (error) {
    console.error("Failed to load progress:", error);
    progressContent.innerHTML = `<p>Could not load progress. Please complete the security check first.</p>`;
  }
}
function requireLogin() {
  if (!getUsername()) {
    alert("Please log in and complete the security check first.");
    window.location.href = "login.html";
    return false;
  }
  return true;
}

// ============================================================
// INTAKE PERSISTENCE — draft autosave + restore-from-server
// (Keeps the intake form's contents intact whenever the user
// navigates away to another page and comes back.)
// ============================================================

function populateIntakeFields(intake) {
  if (!intake) return;

  ["penicillin_allergy", "anaphylaxis_history", "mono_suspected", "kidney_disease", "breastfeeding",
   "trouble_falling_asleep", "waking_night", "waking_early", "chronic_pain", "limited_mobility",
   "fall_risk", "polypharmacy", "renal_decline"].forEach(f => {
    const el = document.getElementById(f);
    if (el && intake[f] !== undefined) el.checked = !!intake[f];
  });

  const ps = document.getElementById("pregnancy_status");
  if (ps && intake.pregnancy_status) ps.value = intake.pregnancy_status;
  const mt = document.getElementById("meds_text");
  if (mt && intake.meds_text !== undefined) mt.value = intake.meds_text;

  const exp = document.getElementById("in_experience_level");
  if (exp) exp.value = intake.experience_level || "Beginner";
  if (intake.experience_level) learningStorage().setItem("experienceLevel", intake.experience_level);

  const dob = document.getElementById("in_dob");
  if (dob && intake.dob) dob.value = intake.dob;

  const cy = document.getElementById("in_cig_years");
  if (cy && intake.cigarette_years !== undefined && intake.cigarette_years !== "") cy.value = intake.cigarette_years;

  const setRange = (id, valId, value, suffix = "") => {
    const el = document.getElementById(id);
    const valEl = document.getElementById(valId);
    if (el && value !== undefined && value !== null && value !== "") {
      el.value = value;
      if (valEl) valEl.textContent = value + suffix;
    }
  };
  setRange("in_alcohol_drinks", "in_alcohol_val", intake.alcohol_drinks_per_week);
  setRange("in_sleep_hours", "in_sleep_val", intake.sleep_hours, "h");
  setRange("in_stress", "in_stress_val", intake.stress_level, "/10");
  setRange("in_exercise_days", "in_ex_val", intake.exercise_days, " days");
  setRange("in_water", "in_water_val", intake.water_cups);
  setRange("in_fruit_veg", "in_fv_val", intake.fruit_veg_servings);

  const cig = document.getElementById("in_cigarette_use");
  if (cig && intake.cigarette_use) cig.value = intake.cigarette_use;
  const diet = document.getElementById("in_diet_type");
  if (diet && intake.diet_type) diet.value = intake.diet_type;

  const setChip = (groupId, value) => {
    if (!value) return;
    const chips = document.querySelectorAll(`.in-chips[data-id="${groupId}"] .in-chip`);
    chips.forEach(c => {
      if (c.textContent.trim() === value) c.classList.add("in-selected");
      else c.classList.remove("in-selected");
    });
  };
  setChip("in_gender", intake.gender);
  setChip("in_archetype", intake.archetype);
  setChip("in_meals_per_day", intake.meals_per_day);
  setChip("in_skips_meals", intake.skips_meals);
  setChip("in_caffeine", intake.caffeine);
  setChip("in_sleep_quality", intake.sleep_quality);
  setChip("in_mood", intake.mood);
  setChip("in_sedentary", intake.sedentary_level);
  setChip("in_calorie_restrict", intake.calorie_restrict);

  const setMulti = (groupId, values) => {
    if (!values || !Array.isArray(values) || !values.length) return;
    const chips = document.querySelectorAll(`.in-chips[data-id="${groupId}"] .in-chip`);
    chips.forEach(c => {
      if (values.includes(c.textContent.trim())) c.classList.add("in-selected");
      else c.classList.remove("in-selected");
    });
  };
  setMulti("in_stress_practices", intake.stress_practices);
  setMulti("in_activity_types", intake.activity_types);

  updateConditionalFields();
}

function saveIntakeDraft() {
  const username = getUsername();
  if (!username) return;
  const draft = {
    _slide: intakeSlide,
    penicillin_allergy: inVal('penicillin_allergy'),
    anaphylaxis_history: inVal('anaphylaxis_history'),
    mono_suspected: inVal('mono_suspected'),
    kidney_disease: inVal('kidney_disease'),
    breastfeeding: inVal('breastfeeding'),
    pregnancy_status: inVal('pregnancy_status'),
    experience_level: inVal('in_experience_level'),
    meds_text: inVal('meds_text'),
    dob: inVal('in_dob'),
    gender: inGetChip('in_gender'),
    archetype: inGetChip('in_archetype'),
    alcohol_drinks_per_week: inVal('in_alcohol_drinks'),
    cigarette_use: inVal('in_cigarette_use'),
    cigarette_years: inVal('in_cig_years'),
    meals_per_day: inGetChip('in_meals_per_day'),
    skips_meals: inGetChip('in_skips_meals'),
    water_cups: inVal('in_water'),
    fruit_veg_servings: inVal('in_fruit_veg'),
    diet_type: inVal('in_diet_type'),
    calorie_restrict: inGetChip('in_calorie_restrict'),
    caffeine: inGetChip('in_caffeine'),
    sleep_hours: inVal('in_sleep_hours'),
    sleep_quality: inGetChip('in_sleep_quality'),
    trouble_falling_asleep: inVal('in_trouble_falling_asleep'),
    waking_night: inVal('in_waking_night'),
    waking_early: inVal('in_waking_early'),
    stress_level: inVal('in_stress'),
    mood: inGetChip('in_mood'),
    stress_practices: inGetMulti('in_stress_practices'),
    exercise_days: inVal('in_exercise_days'),
    activity_types: inGetMulti('in_activity_types'),
    sedentary_level: inGetChip('in_sedentary'),
    chronic_pain: inVal('in_chronic_pain'),
    limited_mobility: inVal('in_limited_mobility'),
    fall_risk: inVal('fall_risk'),
    polypharmacy: inVal('polypharmacy'),
    renal_decline: inVal('renal_decline'),
  };
  try {
    learningStorage().setItem(`intakeDraft_${username}`, JSON.stringify(draft));
  } catch (e) {
    // Storage full or unavailable — not fatal, the server copy still saves on submit.
  }
}

function clearIntakeDraft() {
  const username = getUsername();
  if (!username) return;
  try { learningStorage().removeItem(`intakeDraft_${username}`); } catch (e) {}
}

function attachIntakeAutosave() {
  const el = document.getElementById("intakeContent");
  if (!el || el.dataset.autosaveBound) return;
  el.dataset.autosaveBound = "1";
  el.addEventListener("input", saveIntakeDraft);
  el.addEventListener("change", saveIntakeDraft);
  el.addEventListener("click", (e) => {
    if (e.target && e.target.classList && e.target.classList.contains("in-chip")) {
      setTimeout(saveIntakeDraft, 0);
    }
  });
}

// Restores whatever the user last had in the form: an unsaved in-progress
// draft takes priority (most recent), otherwise falls back to whatever was
// last actually saved to the server.
function restoreIntakeState() {
  const username = getUsername();
  if (!username) return;

  let draft = null;
  try {
    const raw = learningStorage().getItem(`intakeDraft_${username}`);
    if (raw) draft = JSON.parse(raw);
  } catch (e) {
    draft = null;
  }

  if (draft) {
    setTimeout(() => {
      populateIntakeFields(draft);
      if (typeof draft._slide === "number" && draft._slide > 0) inGoToSlide(draft._slide);
    }, 0);
    return;
  }

  apiFetch(`${BASE_URL}/profile/${encodeURIComponent(username)}`)
    .then(r => (r.ok ? r.json() : null))
    .then(data => {
      if (data && data.intake) {
        setTimeout(() => populateIntakeFields(data.intake), 0);
      }
    })
    .catch(() => {});
}

async function resumeLearning() {
  if (!requireLogin()) return;
  const username = getUsername();
  try {
    const response = await apiFetch(`${BASE_URL}/profile/${encodeURIComponent(username)}`);
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();

    const drugSelect = document.getElementById("drugSelect");
    const archetypeSelect = document.getElementById("archetypeSelect");
    if (drugSelect) drugSelect.value = data.selected_drug || "amoxicillin";
    if (archetypeSelect) archetypeSelect.value = data.archetype || "Needs more explanations";

    renderIntakeForm();
    attachIntakeAutosave();
    restoreIntakeState();

    await loadDrugContent();
    await loadLearningPlan();
    await loadProgress();
    showTab("intake", document.getElementById("navIntakeBtn"));
  } catch (error) {
    console.error("Resume failed:", error);
    alert("Could not resume this user profile. Please log in and complete the security check again.");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (["outline", "topic"].includes(document.body.dataset.lessonSource)) return;
  renderAuthSection();

  const drugSelect = document.getElementById("drugSelect");

const username = getUsername();
  if (username) {
    apiFetch(`${BASE_URL}/profile/${encodeURIComponent(username)}`)
      .then(r => r.json())
      .then(data => {
        const level = data?.intake?.experience_level || "";
        if (level) learningStorage().setItem("experienceLevel", level);
      })
      .catch(() => {});
  }

  if (drugSelect) {
    drugSelect.addEventListener("change", async () => {
      await loadDrugContent();
      renderIntakeForm();
      attachIntakeAutosave();
      restoreIntakeState();
      await loadLearningPlan();
      await loadProgress();
    });
  }

  renderIntakeForm();
  attachIntakeAutosave();
  restoreIntakeState();   // brings back an in-progress draft, or the last saved intake
  loadDrugContent();   // no username needed — just fetches drug info
  loadLearningPlan();  // guarded - prompts for the security check if needed
  loadProgress();      // guarded - prompts for the security check if needed

  // run once after loading
  updateConditionalFields();
  showTab("home", document.getElementById("navHomeBtn"));
});


function updateConditionalFields() {
  const gender = inGetChip("in_gender");
  const dob = document.getElementById("in_dob")?.value;

  // --- Calculate age ---
  let age = null;
  if (dob) {
    const birthDate = new Date(dob);
    const today = new Date();
    age = today.getFullYear() - birthDate.getFullYear();
    const m = today.getMonth() - birthDate.getMonth();
    if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) age--;
  }

  const isFemale = gender === "Female";
  const isMale   = gender === "Male";
  const isElderly = age !== null && age >= 60;
  const isChildbearing = isFemale && (age === null || (age >= 12 && age < 55));

  // --- Female-only fields (pregnancy + breastfeeding) ---
  const femaleGroup = document.getElementById("female_fields_group");
  if (femaleGroup) {
    femaleGroup.style.display = (isMale || isElderly) ? "none" : "block";
  }

  // ---   // Breastfeeding: only for childbearing-age females
  const breastfeedingGroup = document.getElementById("breastfeeding_group");
  if (breastfeedingGroup) {
    breastfeedingGroup.style.display = isChildbearing ? "block" : "none";
    if (!isChildbearing) {
      const cb = document.getElementById("breastfeeding");
      if (cb) cb.checked = false;
    }
  }

  // Elderly group: 60+, any gender
  const elderlyGroup = document.getElementById("elderly_group");
  if (elderlyGroup) {
    elderlyGroup.style.display = isElderly ? "block" : "none";
    if (!isElderly) {
      ["fall_risk", "polypharmacy", "renal_decline"].forEach(id => {
        const cb = document.getElementById(id);
        if (cb) cb.checked = false;
      });
    }
  }

    // Pediatric warning: under 12
  let pediatricWarn = document.getElementById("pediatric_warning");
  if (age !== null && age < 12) {
    if (!pediatricWarn) {
      pediatricWarn = document.createElement("div");
      pediatricWarn.id = "pediatric_warning";
      pediatricWarn.style.cssText = "margin-top:8px; padding:10px 14px; background:#fef3c7; border:1px solid #f59e0b; border-radius:8px; font-size:13px; color:#92400e;";
      pediatricWarn.textContent = "⚠️ Patient appears to be under 12. Dosing for children differs significantly — consult a clinician.";
      document.getElementById("in-slide-0")?.appendChild(pediatricWarn);
    }
  } else if (pediatricWarn) {
    pediatricWarn.remove();
  }


  // --- Hide adult lifestyle questions for under-12s ---
  const alcoholQ = document.getElementById("in_alcohol_drinks")?.closest(".in-q");
  const cigaretteQ = document.getElementById("in_cigarette_use")?.closest(".in-q");
  const cigYearsQ = document.getElementById("in_cig_years_wrap");

  if (age !== null && age < 12) {
    if (alcoholQ) alcoholQ.style.display = "none";
    if (cigaretteQ) cigaretteQ.style.display = "none";
    if (cigYearsQ) cigYearsQ.style.display = "none";
  } else {
    if (alcoholQ) alcoholQ.style.display = "block";
    if (cigaretteQ) cigaretteQ.style.display = "block";
    // cig years stays controlled by the cigarette select listener, don't restore it here
  }
}

function confirmSlide0() {
  const dob = document.getElementById("in_dob")?.value;
  const gender = inGetChip("in_gender");
  const errEl = document.getElementById("slide0_confirm_error");

  // Validate both are filled
  if (!dob || !gender) {
    if (errEl) errEl.style.display = "block";
    return;
  }
  if (errEl) errEl.style.display = "none";

  // Calculate age
  const birthDate = new Date(dob);
  const today = new Date();
  let age = today.getFullYear() - birthDate.getFullYear();
  const m = today.getMonth() - birthDate.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) age--;

  // Reveal the rest of slide 0
  const rest = document.getElementById("slide0_rest");
  if (rest) rest.style.display = "block";

  // Hide the confirm button now that it's been used
  const confirmWrap = document.getElementById("slide0_confirm_wrap");
  if (confirmWrap) confirmWrap.style.display = "none";

  // Show/hide adult lifestyle questions
  const adultFields = document.getElementById("adult_lifestyle_fields");
  if (adultFields) adultFields.style.display = age < 12 ? "none" : "block";

  // Show pediatric warning inline (not as a popup — popup comes on Next)
  const warn = document.getElementById("pediatric_warning");
  if (warn) warn.style.display = age < 12 ? "block" : "none";


  updateConditionalFields();
}




// ============================================================
// PATH & LESSON (Gamified Learning Loop — Phase 1)
// ============================================================

function getUrlParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

const CATEGORY_LABELS = {
  "Facts": "Facts",
  "Dosage": "Dosage",
  "Procedures": "Procedures",
  "Rationales": "Rationales"
};

// Small stroke-based SVG icon set (currentColor) used across the path and
// lesson screens instead of emoji — sized with the "1em" trick so they scale
// with whatever font-size their containing element has.
const ICONS = {
  book: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>',
  pill: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="9.5" width="15" height="6.5" rx="3.25" transform="rotate(45 12 12.75)"></rect><line x1="9" y1="10" x2="15" y2="16"></line></svg>',
  stethoscope: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3v6a4 4 0 0 0 8 0V3"></path><path d="M9 15v1a6 6 0 0 0 12 0v-2.5"></path><circle cx="21" cy="10.5" r="1.75"></circle></svg>',
  lightbulb: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6"></path><path d="M10 22h4"></path><path d="M12 2a7 7 0 0 0-4 12.6c.6.5 1 1.2 1 2.1V17h6v-.3c0-.9.4-1.6 1-2.1A7 7 0 0 0 12 2z"></path></svg>',
  lock: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>',
  check: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2.75" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>',
  x: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2.75" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>',
  heartFilled: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" stroke="none"><path d="M12 21s-6.5-4.35-9.5-8.5C.5 9.5 1.5 5.5 5 4.5c2-.6 3.7.3 4.7 1.7L12 8.5l2.3-2.3C15.3 4.8 17 3.9 19 4.5c3.5 1 4.5 5 2.5 8-3 4.15-9.5 8.5-9.5 8.5z"></path></svg>',
  heartOutline: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s-6.5-4.35-9.5-8.5C.5 9.5 1.5 5.5 5 4.5c2-.6 3.7.3 4.7 1.7L12 8.5l2.3-2.3C15.3 4.8 17 3.9 19 4.5c3.5 1 4.5 5 2.5 8-3 4.15-9.5 8.5-9.5 8.5z"></path></svg>',
  flame: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"></path></svg>',
  bolt: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>',
  crown: '<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" stroke="none"><path d="M2 18h20l-1.6-8-5.4 4-3-8-3 8-5.4-4L2 18z"></path></svg>',
};

const CATEGORY_ICONS = {
  "Facts": ICONS.book,
  "Dosage": ICONS.pill,
  "Procedures": ICONS.stethoscope,
  "Rationales": ICONS.lightbulb
};

async function loadPath() {
  const pathMap = document.getElementById("pathMap");
  const drugSelect = document.getElementById("drugSelect");
  const username = getUsername();
  if (!pathMap || !username || drugSelect?.disabled || document.body.dataset.lessonSource === "outline") return;

  loadSavedArchetype();
  const drug = getSelectedDrug();

  try {
    const response = await apiFetch(`${BASE_URL}/path/${encodeURIComponent(drug)}?username=${encodeURIComponent(username)}`);
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();
    if (getSelectedDrug() !== drug) return;
    renderPath(drug, data);
  } catch (error) {
    if (getSelectedDrug() !== drug) return;
    console.error("Failed to load path:", error);
    if (document.body.dataset.pathView === "hub" && typeof renderHub === "function") {
      renderHub(drug, null);
    } else {
      pathMap.innerHTML = `<div class="empty-state">Could not load your path. Please try again.</div>`;
    }
  }
}

function renderPath(drug, data) {
  const pathMap = document.getElementById("pathMap");
  if (!pathMap) return;

  const statXp = document.getElementById("statXp");
  const statStreak = document.getElementById("statStreak");
  const statHearts = document.getElementById("statHearts");
  if (statXp) statXp.textContent = data.xp_total;
  if (statStreak) statStreak.textContent = data.streak_current;
  if (statHearts) statHearts.textContent = data.hearts_remaining;

  const reviewBanner = document.getElementById("reviewBanner");
  if (reviewBanner) {
    const pending = data.review_items || [];
    const heartsLocked = (data.hearts_remaining || 0) <= 0;
    // Show this banner any time hearts are at 0 — not only when there's a
    // question list to show. Otherwise a user whose hearts hit 0 without a
    // recorded review (e.g. an older session) would land here with no
    // questions to review AND no button, a dead end with no way to retry.
    if (heartsLocked) {
      const introText = pending.length
        ? "Review what you missed below, then try again to keep going."
        : "Nothing on file to review — you can go ahead and try again.";
      const listHtml = pending.length
        ? `
          <div class="review-heading">Review before you retry</div>
          <div class="review-list">
            ${pending.map(item => `
              <div class="review-item">
                <p class="review-q">${item.question}</p>
                <p class="review-a">${item.remediation}</p>
              </div>
            `).join('')}
          </div>
        `
        : "";
      reviewBanner.innerHTML = `
        <div class="review-banner" id="reviewBannerBox">
          <div class="review-banner-flag">REVIEW NEEDED</div>
          <h3>You're out of hearts — review to continue</h3>
          <p>${introText}</p>
          ${listHtml}
          <div style="margin-top:16px;">
            <button class="review-btn" id="pathReviewDoneBtn" onclick="completeReview()">I've reviewed this — try again</button>
          </div>
        </div>
      `;
      // This is what the "you're out of hearts" message in the lesson sent
      // them here to find — bring it into view instead of leaving them to
      // scroll and guess where it is.
      setTimeout(() => {
        document.getElementById("reviewBannerBox")?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 100);
    } else {
      reviewBanner.innerHTML = "";
    }
  }

  if (!data.units || !data.units.length) {
    pathMap.innerHTML = `<div class="empty-state">No content for this drug yet.</div>`;
    return;
  }

  const RING_R = 28;
  const RING_CIRC = 2 * Math.PI * RING_R;

  // The "current" unit is the first one that's unlocked but not yet mastered —
  // gets a glow + a bouncing badge to draw the eye, like a "start here" cue.
  const currentIndex = data.units.findIndex(u => u.unlocked && u.min_crown < 5);

  let crownSum = 0;
  data.units.forEach(u => { crownSum += u.min_crown; });
  const overallPct = Math.round((crownSum / (data.units.length * 5)) * 100);
  const overallFill = document.getElementById("overallFill");
  const overallLabel = document.getElementById("overallLabel");
  if (overallFill) overallFill.style.width = `${overallPct}%`;
  if (overallLabel) overallLabel.textContent = `${overallPct}% mastered`;

  pathMap.innerHTML = data.units.map((unit, i) => {
    const crownFilled = unit.min_crown;
    const mastered = crownFilled >= 5;
    const isCurrent = i === currentIndex;
    const dots = Array.from({length: 5}, (_, idx) =>
      `<span class="crown-dot${idx < crownFilled ? ' filled' : ''}">${ICONS.crown}</span>`
    ).join("");
    const circleClass = mastered ? "mastered" : (unit.unlocked ? "active" : "locked-circle");
    const icon = !unit.unlocked ? ICONS.lock : (mastered ? ICONS.check : (CATEGORY_ICONS[unit.category] || (i + 1)));
    const dashoffset = RING_CIRC * (1 - (unit.unlocked ? crownFilled : 0) / 5);
    let badge = "";
    if (mastered) badge = `<span class="unit-badge mastered">MASTERED</span>`;
    else if (unit.unlocked) badge = `<span class="unit-badge${isCurrent ? ' pulse' : ''}">${crownFilled > 0 ? 'CONTINUE' : 'START'}</span>`;

    return `
      <div class="unit-node${unit.unlocked ? '' : ' locked'}${isCurrent ? ' current' : ''}" ${unit.unlocked ? `onclick="goToLesson('${drug}','${unit.category}')"` : ''}>
        <div class="unit-ring-wrap">
          <svg class="crown-ring" viewBox="0 0 64 64">
            <circle class="ring-bg" cx="32" cy="32" r="${RING_R}"></circle>
            <circle class="ring-fill" cx="32" cy="32" r="${RING_R}"
              stroke-dasharray="${RING_CIRC}" stroke-dashoffset="${dashoffset}"></circle>
          </svg>
          <div class="unit-circle ${circleClass}">${icon}</div>
        </div>
        <div class="unit-info">
          <div class="unit-title-row">
            <h3>${CATEGORY_LABELS[unit.category] || unit.category}</h3>
            ${badge}
          </div>
          <p>${unit.objective_count} objective${unit.objective_count === 1 ? '' : 's'}${unit.unlocked ? '' : ' — complete the previous unit to unlock'}</p>
          <div class="crown-row">${dots}<span class="crown-count">${crownFilled}/5</span></div>
        </div>
      </div>
    `;
  }).join("");

  // Stagger the entrance animation per node.
  Array.from(pathMap.children).forEach((node, i) => {
    node.style.animationDelay = `${i * 70}ms`;
  });
}

// Focused mode has two lesson formats: "quiz" (mini quizzes, lesson.html)
// and "chat" (conversational quiz, chat-quiz.html). Game mode always uses lesson.html.
function getFocusedFormat() {
  try { return localStorage.getItem("focusedFormat") === "chat" ? "chat" : "quiz"; } catch (e) { return "quiz"; }
}
function setFocusedFormat(format) {
  try { localStorage.setItem("focusedFormat", format === "chat" ? "chat" : "quiz"); } catch (e) {}
}

function goToLesson(drug, category) {
  const focused = typeof isFocused === "function" && isFocused();
  const page = focused && getFocusedFormat() === "chat" ? "chat-quiz.html" : "lesson.html";
  window.location.href = `${page}?drug=${encodeURIComponent(drug)}&category=${encodeURIComponent(category)}`;
}

// ---- Lesson screen ----

let lessonState = { drug: null, category: null, totalQuestions: 0, currentOid: null, questionNumber: 0, currentHearts: 5 };

async function initLesson() {
  const drug = getUrlParam("drug") || "amoxicillin";
  const category = getUrlParam("category") || "Facts";
  lessonState = { drug, category, totalQuestions: 0, currentOid: null, questionNumber: 0, currentHearts: 5 };
  loadSavedArchetype();

  try {
    const response = await apiFetch(`${BASE_URL}/lesson/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: getUsername(), drug, category })
    });
    if (response.status === 403) {
      // Out of hearts and haven't completed the review yet.
      const body = document.getElementById("lessonBody");
      if (body) {
        body.innerHTML = `
          <div class="lesson-card" style="text-align:center;">
            <div class="summary-icon out-of-hearts">${ICONS.heartOutline}</div>
            <h2>You're out of hearts</h2>
            <p class="summary-note">On the Learning Path page, look for the "REVIEW NEEDED" box near the top — it has what you missed and a button to refill your hearts.</p>
            <button class="continue-btn" onclick="window.location.href='path.html'">Go to Learning Path</button>
          </div>
        `;
      }
      return;
    }
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();

    lessonState.totalQuestions = data.total_questions;
    updateHearts(data.hearts);
    updateProgress(0, data.total_questions);

    if (data.question) {
      lessonState.currentOid = data.question.oid;
      lessonState.questionNumber = 1;
      renderQuestion(data.question);
    } else {
      renderNoQuestions();
    }
  } catch (error) {
    console.error("Failed to start lesson:", error);
    const body = document.getElementById("lessonBody");
    if (body) body.innerHTML = `<div class="lesson-card">Could not start this lesson. <a href="path.html">Back to path</a></div>`;
  }
}

function updateHearts(hearts, animateLossIndex) {
  const el = document.getElementById("heartsDisplay");
  if (!el) return;
  let html = "";
  for (let i = 0; i < 5; i++) {
    const filled = i < hearts;
    const isNewLoss = animateLossIndex !== undefined && i === animateLossIndex;
    html += `<span class="heart-icon${filled ? ' filled' : ' empty'}${isNewLoss ? ' lost' : ''}">${filled ? ICONS.heartFilled : ICONS.heartOutline}</span>`;
  }
  el.innerHTML = html;
  lessonState.currentHearts = hearts;
}

function updateProgress(index, total) {
  const fill = document.getElementById("progressFill");
  if (!fill) return;
  const pct = total > 0 ? Math.min(100, Math.round((index / total) * 100)) : 0;
  fill.style.width = `${pct}%`;
}

function renderQuestion(question) {
  const body = document.getElementById("lessonBody");
  if (!body) return;
  const icon = CATEGORY_ICONS[question.category] || CATEGORY_ICONS[lessonState.category] || ICONS.book;
  const label = CATEGORY_LABELS[question.category] || CATEGORY_LABELS[lessonState.category] || lessonState.category;
  body.innerHTML = `
    <div class="lesson-card" id="lessonCard">
      <div class="lesson-meta">
        <span class="category-chip"><span class="category-chip-icon">${icon}</span> ${label}</span>
        <span class="question-counter">Question ${lessonState.questionNumber} of ${lessonState.totalQuestions}</span>
      </div>
      <h2>${question.question}</h2>
      <textarea id="lessonAnswer" placeholder="Type your answer..."></textarea>
      <button class="lesson-submit" onclick="submitLessonAnswer()">Submit</button>
      <div id="lessonFeedback"></div>
    </div>
  `;
  const textarea = document.getElementById("lessonAnswer");
  if (textarea) textarea.focus();
}

function renderNoQuestions() {
  const body = document.getElementById("lessonBody");
  if (!body) return;
  body.innerHTML = `<div class="lesson-card">Nothing to practice in this unit yet. <a href="path.html">Back to path</a></div>`;
}

async function submitLessonAnswer() {
  const textarea = document.getElementById("lessonAnswer");
  if (!textarea) return;
  const answer = textarea.value.trim();
  if (!answer) return;

  const submitBtn = document.querySelector(".lesson-submit");
  if (submitBtn) submitBtn.disabled = true;

  try {
    const response = await apiFetch(`${BASE_URL}/lesson/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: getUsername(),
        drug: lessonState.drug,
        oid: lessonState.currentOid,
        answer: answer
      })
    });
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();

    // Figure out whether a heart was just lost so we can animate exactly that one.
    const lostIndex = (!data.correct && data.hearts < lessonState.currentHearts) ? data.hearts : undefined;
    updateHearts(data.hearts, lostIndex);
    updateProgress(lessonState.questionNumber, lessonState.totalQuestions);

    const lessonCard = document.getElementById("lessonCard");
    if (lessonCard) lessonCard.classList.add(data.correct ? "card-correct" : "card-wrong");

    const feedbackEl = document.getElementById("lessonFeedback");
    if (feedbackEl) {
      feedbackEl.innerHTML = `
        <div class="feedback-banner ${data.correct ? 'correct' : 'wrong'}">
          <div class="feedback-verdict">
            <span class="verdict-icon">${data.correct ? ICONS.check : ICONS.x}</span>
            <span class="verdict-text">${data.correct ? 'Correct!' : 'Incorrect'}</span>
            ${data.correct
              ? (data.xp_gained > 0 ? `<span class="xp-pop">+${data.xp_gained} XP</span>` : '')
              : `<span class="heart-pop">-1 heart</span>`}
          </div>
          <p class="feedback-flavor">${data.feedback}</p>
          <p class="feedback-detail">${data.detail}</p>
        </div>
      `;
    }

    textarea.disabled = true;
    if (submitBtn) {
      submitBtn.textContent = data.session_over ? "See summary" : "Continue";
      submitBtn.disabled = false;
      submitBtn.onclick = () => {
        if (data.session_over) {
          finishLesson();
        } else {
          lessonState.currentOid = data.next_question.oid;
          lessonState.questionNumber += 1;
          updateProgress(lessonState.questionNumber - 1, lessonState.totalQuestions);
          renderQuestion(data.next_question);
        }
      };
    }
  } catch (error) {
    console.error("Failed to submit answer:", error);
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function finishLesson() {
  const body = document.getElementById("lessonBody");
  try {
    const response = await apiFetch(`${BASE_URL}/lesson/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: getUsername(), drug: lessonState.drug })
    });
    if (!response.ok) throw new Error(`HTTP error ${response.status}`);
    const data = await response.json();

    updateProgress(lessonState.totalQuestions, lessonState.totalQuestions);

    const badgesHtml = (data.badges_earned || []).map(b =>
      `<span class="badge-pill">${b.replace(/_/g, ' ')}</span>`
    ).join("");

    const ranOutOfHearts = !!data.ran_out_of_hearts;
    const answered = data.questions_answered || 0;
    const correctCount = data.questions_correct || 0;
    const accuracy = answered > 0 ? correctCount / answered : 1;
    // Only celebrate a genuinely good result — running out of hearts, or
    // finishing but getting most of it wrong, gets an encouraging note
    // instead of confetti and "Lesson complete!".
    const mostlyWrong = !ranOutOfHearts && answered > 0 && accuracy < 0.6;
    const celebrate = !ranOutOfHearts && !mostlyWrong;

    const headline = ranOutOfHearts ? "Out of hearts" : (mostlyWrong ? "Lesson finished" : "Lesson complete!");
    const summaryIconClass = ranOutOfHearts ? "out-of-hearts" : (mostlyWrong ? "needs-review" : "complete");
    const summaryIcon = ranOutOfHearts ? ICONS.heartOutline : (mostlyWrong ? ICONS.book : ICONS.check);
    const note = ranOutOfHearts
      ? `<p class="summary-note">You answered ${data.questions_answered} of ${data.total_questions} questions before running out of hearts. Any crowns you earned are saved — this lesson will restart from the beginning next time.</p>`
      : mostlyWrong
      ? `<p class="summary-note">You got ${correctCount} of ${answered} right. Worth reviewing this unit again before moving on — practice will bring your crowns up.</p>`
      : "";

    const reviewItems = data.review_items || [];
    const reviewHtml = ranOutOfHearts
      ? `
        <div class="review-section">
          <h3 class="review-heading">Review before you retry</h3>
          <div class="review-list">
            ${reviewItems.map(item => `
              <div class="review-item">
                <p class="review-q">${item.question}</p>
                <p class="review-a">${item.remediation}</p>
              </div>
            `).join('') || '<p class="summary-note">No missed questions to review — you can try again.</p>'}
          </div>
        </div>
      `
      : "";

    const actionButton = ranOutOfHearts
      ? `<button class="continue-btn" id="reviewDoneBtn" onclick="completeReview()">I've reviewed this — try again</button>`
      : `<button class="continue-btn" onclick="window.location.href='path.html'">Back to path</button>`;

    if (body) {
      body.innerHTML = `
        <div class="lesson-card lesson-summary">
          <div class="summary-icon ${summaryIconClass}">${summaryIcon}</div>
          <h2>${headline}</h2>
          ${note}
          <div class="summary-stats">
            <div class="summary-stat"><span class="stat-icon">${ICONS.bolt}</span><span class="stat-value">+${data.xp_earned}</span><span class="stat-label">XP earned</span></div>
            <div class="summary-stat"><span class="stat-icon">${ICONS.flame}</span><span class="stat-value">${data.streak_current}</span><span class="stat-label">day streak</span></div>
            <div class="summary-stat"><span class="stat-icon">${ICONS.heartFilled}</span><span class="stat-value">${data.hearts_remaining}</span><span class="stat-label">hearts left</span></div>
          </div>
          ${badgesHtml ? `<div class="badge-row">${badgesHtml}</div>` : ''}
          ${reviewHtml}
          ${actionButton}
        </div>
      `;
    }

    if (celebrate) launchConfetti();
  } catch (error) {
    console.error("Failed to complete lesson:", error);
    if (body) body.innerHTML = `<div class="lesson-card">Lesson finished, but couldn't save the summary. <a href="path.html">Back to path</a></div>`;
  }
}

// Called after the user has read through their missed-question remediation
// on the "out of hearts" summary screen. Refills hearts server-side (the
// only way they get refilled) and sends them back to the path.
async function completeReview() {
  const btn = document.getElementById("reviewDoneBtn") || document.getElementById("pathReviewDoneBtn");
  if (btn) { btn.disabled = true; btn.textContent = "Refilling hearts..."; }
  try {
    await apiFetch(`${BASE_URL}/lesson/review-complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: getUsername() })
    });
  } catch (error) {
    console.error("Failed to complete review:", error);
  }
  window.location.href = "path.html";
}

function launchConfetti() {
  const colors = ['#2f855a', '#6bbf8e', '#f5b400', '#22c55e', '#f472b6'];
  const count = 40;
  for (let i = 0; i < count; i++) {
    const piece = document.createElement('div');
    piece.className = 'confetti-piece';
    piece.style.left = `${Math.random() * 100}vw`;
    piece.style.background = colors[Math.floor(Math.random() * colors.length)];
    piece.style.animationDuration = `${1.8 + Math.random() * 1.4}s`;
    piece.style.animationDelay = `${Math.random() * 0.35}s`;
    piece.style.transform = `rotate(${Math.random() * 360}deg)`;
    document.body.appendChild(piece);
    setTimeout(() => piece.remove(), 3800);
  }

  
}

