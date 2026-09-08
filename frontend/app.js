/**
 * JobFinder.ai — Precision Matching Application Controller
 * Vanilla JS client with PBKDF2 bearer session tokens, XSS protection, and modular view handlers.
 */

// Application State Store
const state = {
  token: localStorage.getItem('jobfinder_token') || '',
  user: {
    id: 1,
    email: 'demo@jobfinder.ai',
    name: 'Alex Johnson',
    plan: 'free',
    role: 'candidate'
  },
  profile: {
    raw_text: '',
    hard_skills: [],
    soft_skills: [],
    target_categories: [],
    parse_ms: 0
  },
  matches: [],
  filteredMatches: [],
  allJobs: [],
  stats: null,
  activeStep: 1,
  activeView: 'match-view',
  selectedJob: null,
  activeMatchFilter: 'all',
  exploreFilters: {
    search: '',
    category: 'all',
    type: 'all'
  }
};

// 1-Click Realistic Persona Presets
const PERSONA_PRESETS = {
  frontend: {
    name: 'Senior Frontend Engineer',
    text: `Alex Johnson
Senior Frontend Engineer with 6+ years specializing in modern web architecture.
Deep expertise in React, Next.js, TypeScript, JavaScript, HTML5, and modern CSS/Tailwind CSS.
Experienced in GraphQL API consumption, component design systems, Web Vitals performance optimization, and accessibility.
Strong background collaborating with cross-functional product designers and backend engineers in fast-paced agile scrum environments.`
  },
  ai: {
    name: 'Machine Learning Engineer',
    text: `Dr. Maya Lin
Machine Learning Engineer & Applied AI Researcher with 5 years of industry experience.
Core technical proficiencies: Python, PyTorch, TensorFlow, Transformers (Hugging Face), LLM fine-tuning, and CUDA.
Hands-on experience deploying distributed training workflows with Ray and DeepSpeed, evaluation harnesses, and vector databases.
Skilled in statistical analysis, mathematical modeling, problem solving, and research paper implementation.`
  },
  devops: {
    name: 'DevOps & SRE Specialist',
    text: `David Chen
Site Reliability & Cloud Infrastructure Engineer with 7 years scaling distributed systems.
Key stack: Kubernetes, Docker, Terraform, Linux internals, Go, Python scripting, AWS, and GCP.
Built automated CI/CD pipelines using GitHub Actions and ArgoCD, multi-cluster Prometheus and Grafana telemetry, and zero-trust security postures.
Experienced with 24/7 on-call incident response, root cause analysis, and capacity planning.`
  },
  intern: {
    name: 'Full-Stack Developer Intern',
    text: `Jordan Taylor
Computer Science undergraduate candidate with strong passion for web development.
Proficient in JavaScript, React, Node.js, Express, Python, and SQL (PostgreSQL).
Completed projects building full-stack responsive web apps, RESTful APIs, and relational databases.
Quick learner, strong communication skills, eager to contribute and learn within an engineering mentorship program.`
  }
};

// Application Bootstrap
document.addEventListener('DOMContentLoaded', async () => {
  initTextareaWordCounter();
  initDragAndDrop();
  restoreSession();
  await loadInitialData();
});

/* ==========================================================================
   API Helper with Bearer Token Authorization
   ========================================================================== */
async function fetchApi(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  if (state.token) {
    headers['Authorization'] = `Bearer ${state.token}`;
  }

  try {
    const res = await fetch(path, { ...options, headers });
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      // If 401 Unauthorized, session token may have expired
      if (res.status === 401 && state.token) {
        state.token = '';
        localStorage.removeItem('jobfinder_token');
      }
      // Handle Pydantic validation errors where detail is an array of objects
      let errorMsg = `API Error (${res.status})`;
      if (data.detail) {
        if (typeof data.detail === 'string') {
          errorMsg = data.detail;
        } else if (Array.isArray(data.detail)) {
          errorMsg = data.detail.map(e => e.msg || JSON.stringify(e)).join('; ');
        } else {
          errorMsg = String(data.detail);
        }
      } else if (data.message) {
        errorMsg = data.message;
      }
      throw new Error(errorMsg);
    }
    return data;
  } catch (err) {
    console.error(`Request failed on ${path}:`, err);
    throw err;
  }
}

/* ==========================================================================
   Session & Authentication State Management
   ========================================================================== */
function restoreSession() {
  const savedUser = localStorage.getItem('jobfinder_user');
  const savedToken = localStorage.getItem('jobfinder_token');

  if (savedUser) {
    try {
      state.user = JSON.parse(savedUser);
    } catch (e) {
      console.warn('Could not parse stored user profile', e);
    }
  }

  if (savedToken) {
    state.token = savedToken;
  }

  updateUserDisplay();
}

function saveSession(user, token) {
  if (user) {
    state.user = user;
    localStorage.setItem('jobfinder_user', JSON.stringify(user));
  }
  if (token) {
    state.token = token;
    localStorage.setItem('jobfinder_token', token);
  }
}

async function loadInitialData() {
  try {
    const [jobsData, statsData] = await Promise.all([
      fetchApi('/api/jobs?limit=100').catch(() => ({ total: 0, jobs: [] })),
      fetchApi('/api/stats').catch(() => null)
    ]);

    state.allJobs = jobsData.jobs || [];
    state.stats = statsData;

    const totalCount = jobsData.total || state.allJobs.length;
    const headerCount = document.getElementById('header-job-count');
    if (headerCount) headerCount.textContent = `${totalCount} Roles Indexed`;

    const heroJobs = document.getElementById('hero-stat-jobs');
    if (heroJobs) heroJobs.textContent = totalCount;

    const sideJobs = document.getElementById('side-stat-jobs');
    if (sideJobs) sideJobs.textContent = `${totalCount} Jobs`;

    renderMarketJobs();
    renderSidebarDemandBars();
  } catch (err) {
    console.error('Initial catalog load failed:', err);
  }
}

function updateUserDisplay() {
  const u = state.user;
  const initials = (u.name || u.email || 'CJ').substring(0, 2).toUpperCase();

  // Header chip
  const avatarSm = document.getElementById('user-avatar-sm');
  if (avatarSm) avatarSm.textContent = initials;
  const nameSm = document.getElementById('user-chip-name');
  if (nameSm) nameSm.textContent = u.name || u.email;
  const chipId = document.getElementById('user-chip-id');
  if (chipId) chipId.textContent = u.role || 'candidate';

  // Step 1 Active Profile Card
  const avatarLg = document.getElementById('user-avatar-lg');
  if (avatarLg) avatarLg.textContent = initials;
  const nameLg = document.getElementById('active-user-name');
  if (nameLg) nameLg.textContent = u.name || 'Candidate';
  const roleLg = document.getElementById('active-user-role');
  if (roleLg) roleLg.textContent = u.role || 'candidate';
  const planLg = document.getElementById('active-user-plan');
  if (planLg) planLg.textContent = u.plan || 'free';
  const emailLg = document.getElementById('active-user-email');
  if (emailLg) emailLg.textContent = u.email;
  const idLg = document.getElementById('active-user-id-text');
  if (idLg) idLg.textContent = `User ID: #${u.id || 1} • Session Token Active`;

  const sideName = document.getElementById('side-stat-user');
  if (sideName) sideName.textContent = u.name || u.email;

  // Sync Input fields
  const inEmail = document.getElementById('input-email');
  if (inEmail) inEmail.value = u.email;
  const inName = document.getElementById('input-name');
  if (inName) inName.value = u.name || '';
}

/* ==========================================================================
   Authentication Handlers
   ========================================================================== */
async function handleAuthLogin() {
  const email = (document.getElementById('input-email')?.value || '').trim();
  const password = (document.getElementById('input-password')?.value || '').trim();

  if (!email || !password) {
    showToast('Please enter both email and password to sign in', 'error');
    return;
  }

  try {
    const res = await fetchApi('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });

    saveSession(res.user, res.token);
    updateUserDisplay();
    toggleEditAccountForm();
    showToast(`Signed in successfully as ${res.user.email}`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleAuthRegister() {
  const email = (document.getElementById('input-email')?.value || '').trim();
  const password = (document.getElementById('input-password')?.value || '').trim();
  const name = (document.getElementById('input-name')?.value || '').trim() || 'Candidate';

  if (!email || !password) {
    showToast('Please specify email and password to register', 'error');
    return;
  }

  if (password.length < 6) {
    showToast('Password must be at least 6 characters', 'error');
    return;
  }

  try {
    const res = await fetchApi('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name, role: 'candidate' })
    });

    saveSession(res.user, res.token);
    updateUserDisplay();
    toggleEditAccountForm();
    showToast(`Account registered successfully for ${res.user.email}`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleModalLogin() {
  const email = (document.getElementById('modal-email-input')?.value || '').trim();
  const password = (document.getElementById('modal-pass-input')?.value || '').trim();

  if (!email || !password) {
    showToast('Please provide both email and password', 'error');
    return;
  }

  try {
    const res = await fetchApi('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
    });

    saveSession(res.user, res.token);
    updateUserDisplay();
    toggleUserModal();
    showToast(`Welcome back, ${res.user.name || res.user.email}!`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function handleModalRegister() {
  const email = (document.getElementById('modal-email-input')?.value || '').trim();
  const password = (document.getElementById('modal-pass-input')?.value || '').trim();
  const name = (document.getElementById('modal-name-input')?.value || '').trim() || 'Candidate';

  if (!email || !password) {
    showToast('Please provide email and password', 'error');
    return;
  }

  try {
    const res = await fetchApi('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name, role: 'candidate' })
    });

    saveSession(res.user, res.token);
    updateUserDisplay();
    toggleUserModal();
    showToast('Account registered and session authenticated!', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function loadDemoUser() {
  try {
    const res = await fetchApi('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: 'demo@jobfinder.ai', password: 'DemoPassword123!' })
    });
    saveSession(res.user, res.token);
    updateUserDisplay();
    showToast('Loaded demo candidate session (Alex Johnson)', 'info');
  } catch {
    // If password mismatch, fallback to create_or_get_user
    try {
      const res2 = await fetchApi('/api/users', {
        method: 'POST',
        body: JSON.stringify({ email: 'demo@jobfinder.ai', name: 'Alex Johnson' })
      });
      saveSession(res2, res2.token);
      updateUserDisplay();
      showToast('Loaded demo candidate session', 'info');
    } catch (e) {
      showToast('Could not load demo account', 'error');
    }
  }
}

function toggleEditAccountForm() {
  const form = document.getElementById('account-edit-form');
  if (form) form.classList.toggle('hidden');
}

function toggleUserModal() {
  const modal = document.getElementById('user-modal-backdrop');
  if (modal) modal.classList.toggle('active');
}

/* ==========================================================================
   Navigation Views
   ========================================================================== */
function switchView(viewId) {
  state.activeView = viewId;

  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.classList.toggle('active', tab.getAttribute('data-view') === viewId);
  });

  document.querySelectorAll('.view-section').forEach(sec => {
    sec.classList.toggle('active', sec.id === viewId);
  });

  window.scrollTo({ top: 0, behavior: 'smooth' });

  if (viewId === 'explore-view') {
    renderMarketJobs();
  } else if (viewId === 'insights-view') {
    loadMarketStats();
  }
}

function jumpToStep(step) {
  proceedToStep(step);
}

function proceedToStep(step) {
  state.activeStep = step;

  // Update Stepper
  for (let i = 1; i <= 4; i++) {
    const node = document.getElementById(`step-node-${i}`);
    if (node) {
      node.classList.toggle('active', i === step);
    }
  }

  // Scroll to active panel
  const targetPanel = document.getElementById(`panel-step-${step}`);
  if (targetPanel) {
    targetPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

/* ==========================================================================
   Step 2: Resume Input & Persona Presets
   ========================================================================== */
function initTextareaWordCounter() {
  const ta = document.getElementById('resume-input-text');
  const counter = document.getElementById('char-word-counter');
  if (!ta || !counter) return;

  function update() {
    const text = ta.value.trim();
    const words = text ? text.split(/\s+/).length : 0;
    const chars = text.length;
    counter.textContent = `${words} words • ${chars} chars`;
  }

  ta.addEventListener('input', update);
  update();
}

function loadPersonaPreset(key) {
  const preset = PERSONA_PRESETS[key];
  if (!preset) return;
  const ta = document.getElementById('resume-input-text');
  if (ta) {
    ta.value = preset.text;
    ta.dispatchEvent(new Event('input'));
    showToast(`Loaded ${preset.name} persona`, 'success');
    proceedToStep(2);
  }
}

function clearResumeInput() {
  const ta = document.getElementById('resume-input-text');
  if (ta) {
    ta.value = '';
    ta.dispatchEvent(new Event('input'));
  }
}

function triggerFileInput() {
  const input = document.getElementById('file-upload-input');
  if (input) input.click();
}

function initDragAndDrop() {
  const dz = document.getElementById('resume-dropzone');
  if (!dz) return;

  ['dragenter', 'dragover'].forEach(name => {
    dz.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dz.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(name => {
    dz.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dz.classList.remove('dragover');
    });
  });

  dz.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      processResumeFile(files[0]);
    }
  });
}

function handleFileSelected(event) {
  const files = event.target.files;
  if (files && files.length > 0) {
    processResumeFile(files[0]);
  }
}

function processResumeFile(file) {
  const ALLOWED_TEXT_TYPES = [
    'text/plain', 'text/markdown', 'text/csv', 'text/html',
    'application/json', 'application/xml'
  ];
  const ALLOWED_EXTENSIONS = ['.txt', '.md', '.csv', '.json', '.xml', '.html', '.rtf'];
  const ext = '.' + (file.name.split('.').pop() || '').toLowerCase();

  if (!ALLOWED_TEXT_TYPES.includes(file.type) && !ALLOWED_EXTENSIONS.includes(ext)) {
    showToast(
      `"${file.name}" is not a supported text file. Please upload a .txt, .md, or other plain-text format, or paste your resume content directly.`,
      'error'
    );
    return;
  }

  if (file.size > 512 * 1024) {
    showToast('File is too large (max 512 KB). Please paste your resume text directly.', 'error');
    return;
  }

  const reader = new FileReader();
  reader.onerror = () => {
    showToast('Failed to read the file. Please paste your resume text directly.', 'error');
  };
  reader.onload = (e) => {
    const content = e.target.result;
    const ta = document.getElementById('resume-input-text');
    if (ta) {
      ta.value = content;
      ta.dispatchEvent(new Event('input'));
      showToast(`Loaded "${file.name}" (${(file.size / 1024).toFixed(1)} KB)`, 'success');
    }
  };
  reader.readAsText(file);
}

/* ==========================================================================
   Step 3: Analyze Resume & Extract Skills
   ========================================================================== */
async function handleAnalyzeResume() {
  const ta = document.getElementById('resume-input-text');
  const text = ta ? ta.value.trim() : '';

  if (!text || text.length < 15) {
    showToast('Please paste a resume or click a benchmark persona preset', 'error');
    return;
  }

  const btn = document.getElementById('btn-parse-resume');
  btn.disabled = true;
  btn.innerHTML = '<span>Parsing Skill Vectors...</span>';

  try {
    const userId = state.user.id || 1;
    const res = await fetchApi(`/api/users/${userId}/profile`, {
      method: 'POST',
      body: JSON.stringify({ raw_text: text })
    });

    state.profile = {
      raw_text: text,
      hard_skills: res.extracted.hard_skills || [],
      soft_skills: res.extracted.soft_skills || [],
      target_categories: res.extracted.target_categories || [],
      parse_ms: res.parse_ms || 25
    };

    renderExtractedSkills();
    proceedToStep(3);

    const badge2 = document.getElementById('badge-step-2');
    if (badge2) badge2.textContent = 'ANALYZED';
    const badge3 = document.getElementById('badge-step-3');
    if (badge3) badge3.textContent = 'VERIFIED';

    showToast(`Identified ${state.profile.hard_skills.length} technical skills in ${state.profile.parse_ms}ms`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
      <span>Extract Skills & Analyze Resume</span>
    `;
  }
}

function renderExtractedSkills() {
  const p = state.profile;

  // Badges & Counters
  const parsePill = document.getElementById('parse-speed-pill');
  if (parsePill) parsePill.textContent = `⚡ Latency: ${p.parse_ms}ms`;

  const totalPill = document.getElementById('skills-total-pill');
  if (totalPill) totalPill.textContent = `${p.hard_skills.length} Technical Skills Identified`;

  const hardCount = document.getElementById('hard-skills-count');
  if (hardCount) hardCount.textContent = p.hard_skills.length;

  const softCount = document.getElementById('soft-skills-count');
  if (softCount) softCount.textContent = p.soft_skills.length;

  const sideSkills = document.getElementById('side-stat-skills');
  if (sideSkills) sideSkills.textContent = `${p.hard_skills.length} Verified`;

  const heroSkills = document.getElementById('hero-stat-skills');
  if (heroSkills) heroSkills.textContent = p.hard_skills.length;

  // Hard Skills Container
  const hardCont = document.getElementById('container-hard-skills');
  if (hardCont) {
    if (p.hard_skills.length === 0) {
      hardCont.innerHTML = '<span class="tag-empty-msg">No skills identified yet.</span>';
    } else {
      hardCont.innerHTML = p.hard_skills.map(skill => `
        <span class="skill-tag">
          ${escapeHtml(skill)}
          <button style="background:none;border:none;color:var(--text-muted);cursor:pointer;margin-left:4px;" onclick="removeSkill('${escapeHtml(skill)}')">×</button>
        </span>
      `).join('');
    }
  }

  // Soft Skills
  const softCont = document.getElementById('container-soft-skills');
  if (softCont) {
    if (p.soft_skills.length === 0) {
      softCont.innerHTML = '<span class="tag-empty-msg">None detected</span>';
    } else {
      softCont.innerHTML = p.soft_skills.map(s => `
        <span class="skill-tag">${escapeHtml(s)}</span>
      `).join('');
    }
  }

  // Target Roles
  const targetCont = document.getElementById('container-role-targets');
  if (targetCont) {
    if (p.target_categories.length === 0) {
      targetCont.innerHTML = '<span class="tag-empty-msg">None detected</span>';
    } else {
      targetCont.innerHTML = p.target_categories.map(c => `
        <span class="skill-tag font-mono">${escapeHtml(c)}</span>
      `).join('');
    }
  }
}

function removeSkill(skill) {
  state.profile.hard_skills = state.profile.hard_skills.filter(s => s !== skill);
  renderExtractedSkills();
}

function addCustomSkill() {
  const input = document.getElementById('custom-skill-input');
  if (!input) return;
  const val = input.value.trim().toLowerCase();
  if (val && !state.profile.hard_skills.includes(val)) {
    state.profile.hard_skills.push(val);
    renderExtractedSkills();
    input.value = '';
    showToast(`Added custom skill: ${val}`, 'info');
  }
}

/* ==========================================================================
   Step 4: Execute Matching Engine & Display Ranked Opportunities
   ========================================================================== */
async function handleRunMatching() {
  const userId = state.user.id || 1;
  const btn = document.getElementById('btn-run-match');
  const overlay = document.getElementById('match-loading-overlay');

  if (!state.profile.raw_text && state.profile.hard_skills.length === 0) {
    proceedToStep(2);
    showToast('Please extract skills from your resume first in Step 2', 'error');
    return;
  }

  btn.disabled = true;
  overlay.classList.remove('hidden');
  proceedToStep(4);

  try {
    const res = await fetchApi(`/api/users/${userId}/match`, { method: 'POST' });
    state.matches = res.matches || [];
    state.filteredMatches = [...state.matches];

    const heroMatches = document.getElementById('hero-stat-matches');
    if (heroMatches) heroMatches.textContent = state.matches.length;

    const badge4 = document.getElementById('badge-step-4');
    if (badge4) badge4.textContent = `${state.matches.length} MATCHES`;

    if (state.matches.length > 0) {
      const topScore = state.matches[0].percentage || 0;
      const heroTop = document.getElementById('hero-stat-topscore');
      if (heroTop) heroTop.textContent = `${topScore}%`;

      const sideQuality = document.getElementById('side-stat-quality');
      if (sideQuality) sideQuality.textContent = `${state.matches[0].band.toUpperCase()}`;
    }

    renderMatches();
    showToast(`Calculated ${state.matches.length} ranked career alignments`, 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    overlay.classList.add('hidden');
    btn.disabled = false;
  }
}

function filterMatches(tier, btnEl) {
  state.activeMatchFilter = tier;
  if (btnEl) {
    document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
    btnEl.classList.add('active');
  }

  if (tier === 'all') {
    state.filteredMatches = [...state.matches];
  } else {
    state.filteredMatches = state.matches.filter(m => m.band.toLowerCase() === tier.toLowerCase());
  }

  renderMatches();
}

function renderMatches() {
  const deck = document.getElementById('matches-deck');
  const matches = state.filteredMatches;

  if (!matches || matches.length === 0) {
    deck.innerHTML = `
      <div class="empty-matches-state">
        <div class="empty-icon-box">🔍</div>
        <h3>No Listings in Selected Tier</h3>
        <p>Switch filter to "All Results" or add additional technologies to your profile.</p>
        <button class="btn btn-outline btn-sm" onclick="filterMatches('all', document.querySelector('.filter-pill'))">Show All Results</button>
      </div>
    `;
    return;
  }

  deck.innerHTML = matches.map(match => {
    const band = match.band || 'good';
    const percent = match.percentage || Math.round((match.similarity || 0) * 100);
    const matchedSkills = match.matched_skills || [];
    const missingSkills = match.missing_skills || [];

    return `
      <div class="match-item-card" onclick="openJobDrawer(${match.job_id})">
        <div class="match-main-col">
          <div class="match-card-header">
            <span class="match-company-pill font-mono">${escapeHtml(match.company || 'Tech Employer')}</span>
            <h3 class="match-job-title">${escapeHtml(match.job_title || 'Position')}</h3>
          </div>

          <div class="match-meta-specs font-mono">
            <span>💰 ${escapeHtml(match.salary || 'Competitive')}</span>
            <span>📍 ${escapeHtml(match.location || 'Remote')}</span>
            <span>🏷️ ${escapeHtml(match.category || 'Engineering')}</span>
            <span>💼 ${match.type === 'internship' ? 'Internship' : 'Full-Time'}</span>
          </div>

          <div class="match-why-box">
            <span><strong>Alignment:</strong> ${escapeHtml(match.why_matched || 'High semantic and skill overlap.')}</span>
          </div>

          <div class="match-skills-chips">
            ${matchedSkills.slice(0, 5).map(s => `<span class="pill-matched font-mono">✓ ${escapeHtml(s)}</span>`).join('')}
            ${missingSkills.slice(0, 3).map(s => `<span class="pill-gap font-mono">+${escapeHtml(s)}</span>`).join('')}
          </div>
        </div>

        <div class="match-score-col">
          <span class="match-pct font-mono ${band}">${percent}%</span>
          <span class="match-band-tag font-mono ${band}">${band}</span>
        </div>
      </div>
    `;
  }).join('');
}

/* ==========================================================================
   Slide-Over Drawer & Pitch Generator
   ========================================================================== */
function openJobDrawer(jobId) {
  const matchObj = state.matches.find(m => m.job_id === jobId);
  const catalogJob = state.allJobs.find(j => j.id === jobId);
  const job = matchObj || catalogJob;

  if (!job) return;
  state.selectedJob = job;

  // Populate drawer
  const compEl = document.getElementById('drawer-company-name');
  if (compEl) compEl.textContent = job.company || 'Employer';

  const titleEl = document.getElementById('drawer-job-title');
  if (titleEl) titleEl.textContent = job.job_title || job.title || 'Role';

  const salEl = document.getElementById('drawer-pill-salary');
  if (salEl) salEl.textContent = `💰 ${job.salary || 'Competitive'}`;

  const locEl = document.getElementById('drawer-pill-location');
  if (locEl) locEl.textContent = `📍 ${job.location || 'Remote'}`;

  const typEl = document.getElementById('drawer-pill-type');
  if (typEl) typEl.textContent = `💼 ${job.type === 'internship' ? 'Internship' : 'Full-time'}`;

  const catEl = document.getElementById('drawer-pill-category');
  if (catEl) catEl.textContent = `🏷️ ${job.category || 'Engineering'}`;

  const descEl = document.getElementById('drawer-description-text');
  if (descEl) descEl.textContent = job.description || 'No detailed description available.';

  // Match section
  const matchSection = document.getElementById('drawer-match-section');
  if (matchObj) {
    if (matchSection) matchSection.classList.remove('hidden');
    const pctEl = document.getElementById('drawer-match-percent');
    if (pctEl) pctEl.textContent = `${matchObj.percentage}%`;

    const bandTitle = document.getElementById('drawer-band-title');
    if (bandTitle) bandTitle.textContent = `${(matchObj.band || 'Good').toUpperCase()} Alignment`;

    const whyEl = document.getElementById('drawer-why-matched');
    if (whyEl) whyEl.textContent = matchObj.why_matched || 'Matches your technical profile.';

    const matchedTags = document.getElementById('drawer-matched-skills');
    if (matchedTags) {
      matchedTags.innerHTML = (matchObj.matched_skills || []).map(s => `<span class="pill-matched font-mono">✓ ${escapeHtml(s)}</span>`).join('') || '<span class="tag-empty-msg">No direct keyword overlap</span>';
    }

    const missingTags = document.getElementById('drawer-missing-skills');
    if (missingTags) {
      missingTags.innerHTML = (matchObj.missing_skills || []).map(s => `<span class="pill-gap font-mono">+${escapeHtml(s)}</span>`).join('') || '<span class="tag-empty-msg font-mono">Primary criteria fulfilled</span>';
    }
  } else {
    if (matchSection) matchSection.classList.add('hidden');
  }

  // Generate Tailored Pitch
  generateTailoredPitch();

  // Apply Link
  const applyLink = document.getElementById('drawer-apply-link');
  if (applyLink) {
    if (job.redirect_url) {
      applyLink.href = job.redirect_url;
      applyLink.classList.remove('hidden');
    } else {
      applyLink.href = '#';
      applyLink.onclick = (e) => {
        e.preventDefault();
        showToast('Application redirected to verified partner portal.', 'info');
      };
    }
  }

  // Open Drawer
  const backdrop = document.getElementById('job-drawer-backdrop');
  const drawer = document.getElementById('job-drawer');
  if (backdrop) backdrop.classList.add('active');
  if (drawer) {
    drawer.classList.add('active');
    drawer.setAttribute('aria-hidden', 'false');
  }
}

function closeJobDrawer() {
  const backdrop = document.getElementById('job-drawer-backdrop');
  const drawer = document.getElementById('job-drawer');
  if (backdrop) backdrop.classList.remove('active');
  if (drawer) {
    drawer.classList.remove('active');
    drawer.setAttribute('aria-hidden', 'true');
  }
}

function generateTailoredPitch() {
  const job = state.selectedJob;
  if (!job) return;

  const pitchTextarea = document.getElementById('drawer-pitch-textarea');
  const candidateName = state.user.name || 'Candidate';
  const jobTitle = job.job_title || job.title || 'the open position';
  const company = job.company || 'your engineering organization';
  const candidateSkills = state.profile.hard_skills.slice(0, 4).join(', ') || 'modern software engineering';

  const pitch = `Dear Hiring Team at ${company},

I am writing to express my strong interest in the ${jobTitle} opportunity. With core competencies in ${candidateSkills}, my technical background closely aligns with your team's architecture and performance requirements.

I would welcome the opportunity to discuss how my skill set and hands-on experience can immediately contribute to ${company}'s goals.

Best regards,
${candidateName}`;

  if (pitchTextarea) pitchTextarea.value = pitch;
}

function copyTailoredPitch() {
  const ta = document.getElementById('drawer-pitch-textarea');
  if (!ta) return;

  navigator.clipboard.writeText(ta.value).then(() => {
    showToast('Introduction note copied to clipboard', 'success');
  }).catch(() => {
    ta.select();
    document.execCommand('copy');
    showToast('Introduction note copied to clipboard', 'success');
  });
}

/* ==========================================================================
   View 2: Market Catalog Browsing
   ========================================================================== */
let searchDebounceTimer = null;
function debounceMarketSearch() {
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => {
    const input = document.getElementById('market-search-input');
    state.exploreFilters.search = input ? input.value.trim() : '';
    renderMarketJobs();
  }, 200);
}

function clearMarketSearch() {
  const input = document.getElementById('market-search-input');
  if (input) input.value = '';
  state.exploreFilters.search = '';
  renderMarketJobs();
}

function setExploreCategory(cat, btnEl) {
  state.exploreFilters.category = cat;
  if (btnEl) {
    document.querySelectorAll('#explore-category-chips .chip-filter').forEach(c => c.classList.remove('active'));
    btnEl.classList.add('active');
  }
  renderMarketJobs();
}

function setExploreType(type, btnEl) {
  state.exploreFilters.type = type;
  if (btnEl) {
    document.querySelectorAll('#explore-type-chips .chip-filter').forEach(c => c.classList.remove('active'));
    btnEl.classList.add('active');
  }
  renderMarketJobs();
}

function renderMarketJobs() {
  const grid = document.getElementById('market-jobs-grid');
  if (!grid) return;

  const { search, category, type } = state.exploreFilters;
  let list = state.allJobs;

  if (category !== 'all') {
    list = list.filter(j => (j.category || '').toLowerCase() === category.toLowerCase());
  }
  if (type !== 'all') {
    list = list.filter(j => (j.type || '').toLowerCase() === type.toLowerCase());
  }
  if (search) {
    const q = search.toLowerCase();
    list = list.filter(j =>
      (j.title || '').toLowerCase().includes(q) ||
      (j.company || '').toLowerCase().includes(q) ||
      (j.location || '').toLowerCase().includes(q) ||
      (j.required_skills || []).some(s => s.toLowerCase().includes(q))
    );
  }

  if (list.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 3rem 1rem;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">💼</div>
        <h3>No Listings Match Query</h3>
        <p style="color: var(--text-muted); margin-top: 0.25rem;">Adjust search filters or initiate a live sync.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = list.map(job => `
    <div class="market-job-card" onclick="openJobDrawer(${job.id})">
      <div>
        <div class="market-badge-row">
          <span class="market-company">${escapeHtml(job.company)}</span>
          <span class="market-cat-badge font-mono">${escapeHtml(job.category)}</span>
        </div>
        <h3 class="market-title">${escapeHtml(job.title)}</h3>
        <p class="market-desc-snippet">${escapeHtml(job.description)}</p>
      </div>

      <div>
        <div class="market-meta-row font-mono">
          <span class="market-salary">${escapeHtml(job.salary || 'Competitive')}</span>
          <span>📍 ${escapeHtml(job.location || 'Remote')}</span>
        </div>
        <div class="market-skills-row">
          ${(job.required_skills || []).slice(0, 4).map(s => `<span class="market-mini-pill font-mono">${escapeHtml(s)}</span>`).join('')}
        </div>
        <button class="btn btn-outline btn-sm w-full" onclick="event.stopPropagation(); matchSpecificJob(${job.id})">
          <span>Match With Resume</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
        </button>
      </div>
    </div>
  `).join('');
}

function matchSpecificJob(jobId) {
  switchView('match-view');
  if (state.matches.length > 0) {
    openJobDrawer(jobId);
  } else {
    proceedToStep(2);
    showToast('Upload or verify your credentials to calculate direct match alignment.', 'info');
  }
}

/* ==========================================================================
   View 3: Market Intelligence Stats
   ========================================================================== */
async function loadMarketStats() {
  try {
    const stats = await fetchApi('/api/stats');
    state.stats = stats;

    const barsCont = document.getElementById('insights-skills-bars');
    if (barsCont && stats.top_market_skills) {
      const maxDemand = Math.max(...stats.top_market_skills.map(s => s.demand), 1);
      barsCont.innerHTML = stats.top_market_skills.map(item => {
        const pct = Math.round((item.demand / maxDemand) * 100);
        return `
          <div class="demand-full-item">
            <div class="demand-full-header">
              <span class="font-mono">${escapeHtml(item.skill)}</span>
              <span style="color: var(--text-muted); font-family: var(--font-mono);">${item.demand} roles</span>
            </div>
            <div class="demand-full-track">
              <div class="demand-full-bar" style="width: ${pct}%;"></div>
            </div>
          </div>
        `;
      }).join('');
    }

    const catCont = document.getElementById('insights-category-list');
    if (catCont && stats.categories) {
      catCont.innerHTML = Object.entries(stats.categories).map(([cat, count]) => `
        <div class="cat-dist-row">
          <span>${escapeHtml(cat)}</span>
          <span class="cat-dist-count font-mono">${count} listings (${Math.round((count / stats.total_jobs) * 100)}%)</span>
        </div>
      `).join('');
    }
  } catch (err) {
    console.error('Stats load failed:', err);
  }
}

function renderSidebarDemandBars() {
  const cont = document.getElementById('sidebar-demand-bars');
  if (!cont || !state.stats?.top_market_skills) return;

  const top4 = state.stats.top_market_skills.slice(0, 4);
  const max = Math.max(...top4.map(s => s.demand), 1);

  cont.innerHTML = top4.map(item => `
    <div class="demand-row">
      <div style="display:flex; justify-content:space-between; font-size:0.75rem;">
        <span class="demand-name font-mono">${escapeHtml(item.skill)}</span>
        <span style="color:var(--text-muted); font-family:var(--font-mono);">${item.demand}</span>
      </div>
      <div class="demand-track">
        <div class="demand-fill" style="width: ${Math.round((item.demand / max) * 100)}%;"></div>
      </div>
    </div>
  `).join('');
}

/* ==========================================================================
   View 4: Live Market Ingestion (Adzuna Sync)
   ========================================================================== */
function setSyncQuery(q) {
  const input = document.getElementById('sync-query-input');
  if (input) input.value = q;
}

async function handleTriggerSync() {
  const query = document.getElementById('sync-query-input').value.trim() || 'software engineer';
  const btn = document.getElementById('btn-trigger-sync');
  const term = document.getElementById('sync-log-terminal');

  btn.disabled = true;
  btn.innerHTML = '<span>Ingesting Listings...</span>';
  term.textContent = `[${new Date().toLocaleTimeString()}] Initiating search: "${query}"...\nContacting API endpoint...`;

  try {
    const res = await fetchApi('/api/jobs/fetch', {
      method: 'POST',
      body: JSON.stringify({ query, limit: 20 })
    });

    term.textContent += `\n[${new Date().toLocaleTimeString()}] Query completed successfully!\n${res.message || `Synced ${res.synced} positions.`}`;
    showToast(res.message || 'Market sync completed', 'success');

    await loadInitialData();
  } catch (err) {
    term.textContent += `\n[${new Date().toLocaleTimeString()}] Error: ${err.message}`;
    showToast(err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
      <span>Sync Live Jobs</span>
    `;
  }
}

async function handleRefreshStale() {
  try {
    const res = await fetchApi('/api/jobs/refresh', { method: 'PUT' });
    showToast(res.message, 'info');
    await loadInitialData();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

/* ==========================================================================
   Toast Notification Utility & XSS Protection
   ========================================================================== */
function showToast(msg, type = 'info') {
  const cont = document.getElementById('toast-container');
  if (!cont) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  const icon = type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ';
  toast.innerHTML = `<span><strong>${icon}</strong></span><span>${escapeHtml(msg)}</span>`;
  cont.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => toast.remove(), 260);
  }, 3200);
}

function escapeHtml(text) {
  if (text == null) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}