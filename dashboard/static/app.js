/* ── State ──────────────────────────────────────────────────── */
let allJobs = [];
let allChats = [];
let allEmails = [];

/* ── Init ───────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  loadAll();
  loadSettings();
});

async function loadAll() {
  await Promise.all([loadJobs(), loadChats(), loadEmails()]);
  loadStats();
  renderOverview();
}

/* ── Tab Navigation ─────────────────────────────────────────── */
function showTab(tab) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
  if (tab === 'resume') populateTailorJobSelect();
}

/* ── API Helpers ─────────────────────────────────────────────── */
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ── Settings ────────────────────────────────────────────────── */
async function loadSettings() {
  try {
    const s = await api('GET', '/api/settings');
    const el = document.getElementById('settings-status');
    if (s.workday_configured) {
      el.innerHTML = `<span style="color:var(--green)">&#10003; Workday configured</span>`;
    } else {
      el.innerHTML = `<span style="color:var(--yellow)">&#9888; Set credentials in .env</span>`;
    }
  } catch {}
}

/* ── Stats ───────────────────────────────────────────────────── */
async function loadStats() {
  try {
    const s = await api('GET', '/api/stats');
    document.getElementById('stat-total-jobs').textContent = s.jobs.total;
    document.getElementById('stat-active-jobs').textContent = s.jobs.active;
    document.getElementById('stat-chats').textContent = s.coffee_chats.total;
    document.getElementById('stat-follow-ups').textContent =
      s.coffee_chats.upcoming_follow_ups + s.emails.pending_follow_up;
  } catch {}
}

/* ══════════════════════════════════════════════════════════════
   JOBS
══════════════════════════════════════════════════════════════ */
async function loadJobs() {
  allJobs = await api('GET', '/api/jobs');
  renderJobs(allJobs);
}

function renderJobs(jobs) {
  const tbody = document.getElementById('jobs-tbody');
  if (!jobs.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">No jobs yet. Click "+ Add Job" to get started.</div></td></tr>`;
    return;
  }
  tbody.innerHTML = jobs.map(j => `
    <tr>
      <td>
        <div style="font-weight:600">${esc(j.company)}</div>
        ${j.source ? `<div style="font-size:11px;color:var(--text-muted)">${esc(j.source)}</div>` : ''}
      </td>
      <td>${esc(j.title)}${j.location ? `<br><span style="font-size:11px;color:var(--text-muted)">${esc(j.location)}</span>` : ''}</td>
      <td>${statusBadge(j.status)}</td>
      <td style="font-size:12px;color:var(--text-muted)">${j.salary_range || '—'}</td>
      <td style="font-size:12px;color:var(--text-muted)">${fmtDate(j.date_applied) || '—'}</td>
      <td style="font-size:12px;color:var(--text-muted)">${fmtDate(j.last_status_check) || '—'}</td>
      <td>
        <div class="action-btns">
          ${j.job_url ? `<a href="${j.job_url}" target="_blank" class="btn btn-sm btn-secondary">View</a>` : ''}
          <button class="btn btn-sm btn-secondary" onclick="editJob(${j.id})">Edit</button>
          <button class="btn btn-sm btn-secondary" onclick="checkStatus(${j.id})" title="Check Workday Status">&#8635;</button>
          <button class="btn btn-sm btn-danger" onclick="deleteJob(${j.id})">Del</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function filterJobs() {
  const q = document.getElementById('job-search').value.toLowerCase();
  const status = document.getElementById('job-status-filter').value;
  renderJobs(allJobs.filter(j =>
    (!q || j.company.toLowerCase().includes(q) || j.title.toLowerCase().includes(q)) &&
    (!status || j.status === status)
  ));
}

// Modal
function openJobModal(job = null) {
  const isEdit = !!job;
  document.getElementById('job-modal-title').textContent = isEdit ? 'Edit Job Application' : 'Add Job Application';
  document.getElementById('job-id').value = job?.id || '';
  document.getElementById('job-company').value = job?.company || '';
  document.getElementById('job-title').value = job?.title || '';
  document.getElementById('job-url').value = job?.job_url || '';
  document.getElementById('job-workday-url').value = job?.workday_url || '';
  document.getElementById('job-status').value = job?.status || 'To Apply';
  document.getElementById('job-location').value = job?.location || '';
  document.getElementById('job-salary').value = job?.salary_range || '';
  document.getElementById('job-source').value = job?.source || 'LinkedIn';
  document.getElementById('job-description').value = job?.job_description || '';
  document.getElementById('job-notes').value = job?.notes || '';
  document.getElementById('apply-btn').style.display = isEdit ? 'none' : 'inline-flex';
  document.getElementById('job-modal').classList.add('open');
}

function closeJobModal(e) {
  if (e && e.target !== document.getElementById('job-modal')) return;
  document.getElementById('job-modal').classList.remove('open');
}

function editJob(id) {
  const job = allJobs.find(j => j.id === id);
  if (job) openJobModal(job);
}

async function saveJob() {
  const id = document.getElementById('job-id').value;
  const payload = {
    company: document.getElementById('job-company').value.trim(),
    title: document.getElementById('job-title').value.trim(),
    job_url: document.getElementById('job-url').value.trim() || null,
    workday_url: document.getElementById('job-workday-url').value.trim() || null,
    status: document.getElementById('job-status').value,
    location: document.getElementById('job-location').value.trim() || null,
    salary_range: document.getElementById('job-salary').value.trim() || null,
    source: document.getElementById('job-source').value,
    job_description: document.getElementById('job-description').value.trim() || null,
    notes: document.getElementById('job-notes').value.trim() || null,
  };
  if (!payload.company || !payload.title) { showToast('Company and Title are required', 'error'); return; }
  try {
    if (id) {
      await api('PUT', `/api/jobs/${id}`, payload);
      showToast('Job updated!', 'success');
    } else {
      await api('POST', '/api/jobs', payload);
      showToast('Job added!', 'success');
    }
    document.getElementById('job-modal').classList.remove('open');
    await loadJobs();
    loadStats();
    renderOverview();
  } catch (e) { showToast(e.message, 'error'); }
}

async function saveJobAndApply() {
  await saveJob();
  // Find the newly created job and trigger apply
  if (allJobs.length > 0) {
    const newest = allJobs[0];
    if (newest.workday_url || newest.job_url) {
      await applyToJob(newest.id);
    }
  }
}

async function deleteJob(id) {
  if (!confirm('Delete this job application?')) return;
  await api('DELETE', `/api/jobs/${id}`);
  showToast('Deleted', 'info');
  await loadJobs();
  loadStats();
  renderOverview();
}

async function checkStatus(id) {
  showToast('Checking Workday status...', 'info');
  try {
    const result = await api('POST', `/api/jobs/${id}/check-status`);
    if (result.success) {
      showToast(`Status: ${result.status}`, 'success');
    } else {
      showToast(result.error || 'Check failed', 'error');
    }
    await loadJobs();
  } catch (e) { showToast(e.message, 'error'); }
}

async function applyToJob(id) {
  showToast('Launching Workday automation...', 'info');
  try {
    const result = await api('POST', `/api/jobs/${id}/apply`);
    if (result.success) {
      showToast(result.status, 'success');
    } else {
      showToast(result.error || 'Apply failed', 'error');
    }
    await loadJobs();
  } catch (e) { showToast(e.message, 'error'); }
}

async function refreshAllStatuses() {
  showToast('Refreshing all Workday statuses...', 'info');
  try {
    const result = await api('POST', '/api/jobs/check-all-statuses');
    showToast(`Checked ${result.checked} jobs`, 'success');
    await loadJobs();
    loadStats();
    renderOverview();
  } catch (e) { showToast(e.message, 'error'); }
}

/* ══════════════════════════════════════════════════════════════
   COFFEE CHATS
══════════════════════════════════════════════════════════════ */
async function loadChats() {
  allChats = await api('GET', '/api/coffee-chats');
  renderChats(allChats);
}

function renderChats(chats) {
  const tbody = document.getElementById('chats-tbody');
  if (!chats.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">No coffee chats yet.</div></td></tr>`;
    return;
  }
  tbody.innerHTML = chats.map(c => `
    <tr>
      <td>
        <div style="font-weight:600">${esc(c.person_name)}</div>
        ${c.linkedin_url ? `<a href="${c.linkedin_url}" target="_blank" style="font-size:11px;color:var(--accent)">LinkedIn</a>` : ''}
      </td>
      <td>${esc(c.company || '—')}</td>
      <td style="font-size:12px;color:var(--text-muted)">${esc(c.role || '—')}</td>
      <td>${chatStatusBadge(c.status)}</td>
      <td style="font-size:12px;color:var(--text-muted)">${esc(c.next_action || '—')}</td>
      <td style="font-size:12px;color:var(--text-muted)">${fmtDate(c.follow_up_date) || '—'}</td>
      <td>
        <div class="action-btns">
          <button class="btn btn-sm btn-secondary" onclick="editChat(${c.id})">Edit</button>
          <button class="btn btn-sm btn-danger" onclick="deleteChat(${c.id})">Del</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function filterChats() {
  const q = document.getElementById('chat-search').value.toLowerCase();
  const status = document.getElementById('chat-status-filter').value;
  renderChats(allChats.filter(c =>
    (!q || c.person_name.toLowerCase().includes(q) || (c.company || '').toLowerCase().includes(q)) &&
    (!status || c.status === status)
  ));
}

function openChatModal(chat = null) {
  const isEdit = !!chat;
  document.getElementById('chat-modal-title').textContent = isEdit ? 'Edit Coffee Chat' : 'Add Coffee Chat';
  document.getElementById('chat-id').value = chat?.id || '';
  document.getElementById('chat-name').value = chat?.person_name || '';
  document.getElementById('chat-company').value = chat?.company || '';
  document.getElementById('chat-role').value = chat?.role || '';
  document.getElementById('chat-linkedin').value = chat?.linkedin_url || '';
  document.getElementById('chat-email').value = chat?.email || '';
  document.getElementById('chat-status').value = chat?.status || 'To Reach Out';
  document.getElementById('chat-meeting-date').value = toDatetimeLocal(chat?.date_meeting);
  document.getElementById('chat-followup-date').value = toDatetimeLocal(chat?.follow_up_date);
  document.getElementById('chat-next-action').value = chat?.next_action || '';
  document.getElementById('chat-notes').value = chat?.notes || '';
  document.getElementById('chat-meeting-notes').value = chat?.meeting_notes || '';
  document.getElementById('chat-modal').classList.add('open');
}

function closeChatModal(e) {
  if (e && e.target !== document.getElementById('chat-modal')) return;
  document.getElementById('chat-modal').classList.remove('open');
}

function editChat(id) {
  const chat = allChats.find(c => c.id === id);
  if (chat) openChatModal(chat);
}

async function saveChat() {
  const id = document.getElementById('chat-id').value;
  const payload = {
    person_name: document.getElementById('chat-name').value.trim(),
    company: document.getElementById('chat-company').value.trim() || null,
    role: document.getElementById('chat-role').value.trim() || null,
    linkedin_url: document.getElementById('chat-linkedin').value.trim() || null,
    email: document.getElementById('chat-email').value.trim() || null,
    status: document.getElementById('chat-status').value,
    date_meeting: document.getElementById('chat-meeting-date').value || null,
    follow_up_date: document.getElementById('chat-followup-date').value || null,
    next_action: document.getElementById('chat-next-action').value.trim() || null,
    notes: document.getElementById('chat-notes').value.trim() || null,
    meeting_notes: document.getElementById('chat-meeting-notes').value.trim() || null,
  };
  if (!payload.person_name) { showToast('Name is required', 'error'); return; }
  try {
    if (id) {
      await api('PUT', `/api/coffee-chats/${id}`, payload);
      showToast('Updated!', 'success');
    } else {
      await api('POST', '/api/coffee-chats', payload);
      showToast('Coffee chat added!', 'success');
    }
    document.getElementById('chat-modal').classList.remove('open');
    await loadChats();
    loadStats();
    renderOverview();
  } catch (e) { showToast(e.message, 'error'); }
}

async function deleteChat(id) {
  if (!confirm('Delete this coffee chat?')) return;
  await api('DELETE', `/api/coffee-chats/${id}`);
  showToast('Deleted', 'info');
  await loadChats();
  loadStats();
  renderOverview();
}

/* ══════════════════════════════════════════════════════════════
   EMAILS
══════════════════════════════════════════════════════════════ */
async function loadEmails() {
  allEmails = await api('GET', '/api/emails');
  renderEmails(allEmails);
}

function renderEmails(emails) {
  const tbody = document.getElementById('emails-tbody');
  if (!emails.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">No email outreach tracked yet.</div></td></tr>`;
    return;
  }
  tbody.innerHTML = emails.map(e => `
    <tr>
      <td style="font-weight:600">${esc(e.recipient_name)}</td>
      <td style="font-size:12px"><a href="mailto:${e.recipient_email}">${esc(e.recipient_email)}</a></td>
      <td>${esc(e.company || '—')}</td>
      <td style="font-size:12px;color:var(--text-muted);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(e.subject || '—')}</td>
      <td>${emailStatusBadge(e.status)}</td>
      <td style="font-size:12px;color:var(--text-muted)">${fmtDate(e.date_sent) || '—'}</td>
      <td style="font-size:12px;color:var(--text-muted)">${fmtDate(e.follow_up_date) || '—'}</td>
      <td>
        <div class="action-btns">
          <button class="btn btn-sm btn-secondary" onclick="editEmail(${e.id})">Edit</button>
          <button class="btn btn-sm btn-danger" onclick="deleteEmail(${e.id})">Del</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function openEmailModal(email = null) {
  const isEdit = !!email;
  document.getElementById('email-modal-title').textContent = isEdit ? 'Edit Email' : 'Add Email Outreach';
  document.getElementById('email-id').value = email?.id || '';
  document.getElementById('email-recipient-name').value = email?.recipient_name || '';
  document.getElementById('email-recipient-email').value = email?.recipient_email || '';
  document.getElementById('email-company').value = email?.company || '';
  document.getElementById('email-status').value = email?.status || 'Draft';
  document.getElementById('email-subject').value = email?.subject || '';
  document.getElementById('email-date-sent').value = email?.date_sent?.split('T')[0] || '';
  document.getElementById('email-followup-date').value = email?.follow_up_date?.split('T')[0] || '';
  document.getElementById('email-body').value = email?.email_body || '';
  document.getElementById('email-notes').value = email?.notes || '';
  document.getElementById('email-modal').classList.add('open');
}

function closeEmailModal(e) {
  if (e && e.target !== document.getElementById('email-modal')) return;
  document.getElementById('email-modal').classList.remove('open');
}

function editEmail(id) {
  const email = allEmails.find(e => e.id === id);
  if (email) openEmailModal(email);
}

async function saveEmail() {
  const id = document.getElementById('email-id').value;
  const payload = {
    recipient_name: document.getElementById('email-recipient-name').value.trim(),
    recipient_email: document.getElementById('email-recipient-email').value.trim(),
    company: document.getElementById('email-company').value.trim() || null,
    subject: document.getElementById('email-subject').value.trim() || null,
    status: document.getElementById('email-status').value,
    date_sent: document.getElementById('email-date-sent').value || null,
    follow_up_date: document.getElementById('email-followup-date').value || null,
    email_body: document.getElementById('email-body').value.trim() || null,
    notes: document.getElementById('email-notes').value.trim() || null,
  };
  if (!payload.recipient_name || !payload.recipient_email) {
    showToast('Name and email are required', 'error'); return;
  }
  try {
    if (id) {
      await api('PUT', `/api/emails/${id}`, payload);
      showToast('Updated!', 'success');
    } else {
      await api('POST', '/api/emails', payload);
      showToast('Email tracked!', 'success');
    }
    document.getElementById('email-modal').classList.remove('open');
    await loadEmails();
    loadStats();
  } catch (e) { showToast(e.message, 'error'); }
}

async function deleteEmail(id) {
  if (!confirm('Delete this email record?')) return;
  await api('DELETE', `/api/emails/${id}`);
  showToast('Deleted', 'info');
  await loadEmails();
  loadStats();
}

/* ══════════════════════════════════════════════════════════════
   RESUME
══════════════════════════════════════════════════════════════ */
async function loadBaseResume() {
  try {
    const resumes = await api('GET', '/api/resumes');
    const base = resumes.find(r => r.is_base) || resumes[0];
    if (!base) { showToast('No resumes saved yet', 'info'); return; }
    const full = await api('GET', `/api/resumes/${base.id}`);
    document.getElementById('resume-name').value = full.name;
    document.getElementById('resume-content').value = full.content;
    showToast('Resume loaded!', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

async function saveResume() {
  const name = document.getElementById('resume-name').value.trim();
  const content = document.getElementById('resume-content').value.trim();
  if (!name || !content) { showToast('Name and content required', 'error'); return; }
  try {
    await api('POST', '/api/resumes', { name, content, is_base: true });
    showToast('Resume saved as base!', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

function populateTailorJobSelect() {
  const sel = document.getElementById('tailor-job-select');
  sel.innerHTML = '<option value="">-- Select job to link --</option>';
  allJobs.forEach(j => {
    const opt = document.createElement('option');
    opt.value = j.id;
    opt.textContent = `${j.company} - ${j.title}`;
    sel.appendChild(opt);
  });
}

async function tailorResume() {
  const jd = document.getElementById('jd-input').value.trim();
  if (!jd) { showToast('Paste a job description first', 'error'); return; }
  const jobId = document.getElementById('tailor-job-select').value || null;

  showToast('Tailoring resume with AI...', 'info');
  try {
    const result = await api('POST', '/api/resumes/tailor', {
      job_description: jd,
      job_id: jobId ? parseInt(jobId) : null,
    });
    document.getElementById('tailored-text').textContent = result.tailored_resume;
    document.getElementById('tailor-result').style.display = 'block';
    if (!result.ai_enabled) {
      showToast('AI not configured - showing base resume. Add ANTHROPIC_API_KEY to .env', 'info');
    } else {
      showToast('Resume tailored!', 'success');
    }
  } catch (e) { showToast(e.message, 'error'); }
}

function copyTailored() {
  const text = document.getElementById('tailored-text').textContent;
  navigator.clipboard.writeText(text).then(() => showToast('Copied!', 'success'));
}

/* ══════════════════════════════════════════════════════════════
   OVERVIEW
══════════════════════════════════════════════════════════════ */
function renderOverview() {
  // Recent jobs
  const recentEl = document.getElementById('recent-jobs-list');
  const recent = allJobs.slice(0, 5);
  if (!recent.length) {
    recentEl.innerHTML = '<div class="empty-state">No applications yet</div>';
  } else {
    recentEl.innerHTML = recent.map(j => `
      <div class="list-item">
        <div class="list-item-main">
          <div class="list-item-company">${esc(j.company)}</div>
          <div class="list-item-sub">${esc(j.title)}</div>
        </div>
        ${statusBadge(j.status)}
      </div>
    `).join('');
  }

  // Upcoming follow-ups (coffee chats)
  const followUpEl = document.getElementById('upcoming-followups-list');
  const now = new Date();
  const upcoming = allChats
    .filter(c => c.follow_up_date && new Date(c.follow_up_date) >= now)
    .sort((a, b) => new Date(a.follow_up_date) - new Date(b.follow_up_date))
    .slice(0, 5);

  if (!upcoming.length) {
    followUpEl.innerHTML = '<div class="empty-state">No upcoming follow-ups</div>';
  } else {
    followUpEl.innerHTML = upcoming.map(c => `
      <div class="list-item">
        <div class="list-item-main">
          <div class="list-item-company">${esc(c.person_name)}</div>
          <div class="list-item-sub">${esc(c.company || '')} · ${fmtDate(c.follow_up_date)}</div>
        </div>
        ${chatStatusBadge(c.status)}
      </div>
    `).join('');
  }

  // Pipeline
  const stages = ['To Apply', 'Applied', 'Phone Screen', 'Interview', 'Offer', 'Rejected'];
  const pipelineEl = document.getElementById('pipeline-view');
  const counts = {};
  allJobs.forEach(j => { counts[j.status] = (counts[j.status] || 0) + 1; });
  pipelineEl.innerHTML = stages.map(s => `
    <div class="pipeline-stage ${counts[s] ? 'has-items' : ''}">
      <div class="pipeline-stage-name">${s}</div>
      <div class="pipeline-count" style="color:${pipelineColor(s)}">${counts[s] || 0}</div>
    </div>
  `).join('');
}

/* ══════════════════════════════════════════════════════════════
   UTILITIES
══════════════════════════════════════════════════════════════ */
function esc(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d)) return null;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function toDatetimeLocal(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return '';
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function statusBadge(status) {
  const map = {
    'To Apply':     'badge-gray',
    'Applied':      'badge-blue',
    'Phone Screen': 'badge-yellow',
    'Interview':    'badge-orange',
    'Offer':        'badge-green',
    'Rejected':     'badge-red',
    'Withdrawn':    'badge-gray',
    'In Progress':  'badge-blue',
    'Under Review': 'badge-yellow',
  };
  return `<span class="badge ${map[status] || 'badge-gray'}">${esc(status)}</span>`;
}

function chatStatusBadge(status) {
  const map = {
    'To Reach Out': 'badge-gray',
    'Message Sent': 'badge-blue',
    'Scheduled':    'badge-yellow',
    'Completed':    'badge-green',
    'Follow Up':    'badge-orange',
    'No Response':  'badge-red',
  };
  return `<span class="badge ${map[status] || 'badge-gray'}">${esc(status)}</span>`;
}

function emailStatusBadge(status) {
  const map = {
    'Draft':       'badge-gray',
    'Sent':        'badge-blue',
    'Replied':     'badge-green',
    'Follow Up':   'badge-yellow',
    'No Response': 'badge-red',
  };
  return `<span class="badge ${map[status] || 'badge-gray'}">${esc(status)}</span>`;
}

function pipelineColor(stage) {
  const map = {
    'To Apply':     'var(--text-muted)',
    'Applied':      'var(--blue)',
    'Phone Screen': 'var(--yellow)',
    'Interview':    'var(--orange)',
    'Offer':        'var(--green)',
    'Rejected':     'var(--red)',
  };
  return map[stage] || 'var(--text)';
}

let toastTimer;
function showToast(msg, type = 'info') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast'; }, 3500);
}
