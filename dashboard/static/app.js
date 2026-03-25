/* ══════════════════════════════════════════════════════════════
   STATE
══════════════════════════════════════════════════════════════ */
let allJobs    = [];
let allChats   = [];
let allEmails  = [];
let allAnswers = [];
let allCreds   = [];

/* ══════════════════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  loadAll();
  loadSettings();
  pollNotifications();   // check unread badge every 30s
});

async function loadAll() {
  await Promise.all([loadJobs(), loadChats(), loadEmails()]);
  loadStats();
  renderOverview();
}

/* ══════════════════════════════════════════════════════════════
   MOBILE SIDEBAR
══════════════════════════════════════════════════════════════ */
function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebar-overlay').classList.toggle('open');
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebar-overlay').classList.remove('open');
}

/* ══════════════════════════════════════════════════════════════
   TAB NAVIGATION
══════════════════════════════════════════════════════════════ */
function showTab(tab) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.getElementById(`tab-${tab}`).classList.add('active');
  const nav = document.querySelector(`[data-tab="${tab}"]`);
  if (nav) nav.classList.add('active');
  closeSidebar();
  if (tab === 'resume')  populateTailorJobSelect();
  if (tab === 'setup')   { loadNotifications(); loadAnswers(); loadCredentials(); }
}

/* ══════════════════════════════════════════════════════════════
   SETUP SUB-SECTIONS
══════════════════════════════════════════════════════════════ */
function switchSetupSection(name) {
  document.querySelectorAll('.setup-section').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.setup-tab').forEach(el => el.classList.remove('active'));
  document.getElementById(`setup-${name}`).style.display = 'block';
  document.querySelector(`[data-section="${name}"]`).classList.add('active');
}

/* ══════════════════════════════════════════════════════════════
   API HELPER
══════════════════════════════════════════════════════════════ */
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ══════════════════════════════════════════════════════════════
   SETTINGS
══════════════════════════════════════════════════════════════ */
async function loadSettings() {
  try {
    const s = await api('GET', '/api/settings');
    const el = document.getElementById('settings-status');
    el.innerHTML = s.workday_configured
      ? `<span style="color:var(--green)">&#10003; Workday configured</span>`
      : `<span style="color:var(--yellow)">&#9888; Add credentials in Job Setup</span>`;
  } catch {}
}

/* ══════════════════════════════════════════════════════════════
   STATS
══════════════════════════════════════════════════════════════ */
async function loadStats() {
  try {
    const s = await api('GET', '/api/stats');
    document.getElementById('stat-total-jobs').textContent  = s.jobs.total;
    document.getElementById('stat-active-jobs').textContent = s.jobs.active;
    document.getElementById('stat-chats').textContent       = s.coffee_chats.total;
    document.getElementById('stat-follow-ups').textContent  =
      s.coffee_chats.upcoming_follow_ups + s.emails.pending_follow_up;
    updateNotifBadge(s.unread_notifications);
  } catch {}
}

/* ══════════════════════════════════════════════════════════════
   NOTIFICATIONS
══════════════════════════════════════════════════════════════ */
function updateNotifBadge(count) {
  const badge1 = document.getElementById('notif-badge');
  const badge2 = document.getElementById('nav-notif-badge');
  const badge3 = document.getElementById('notif-count-inline');
  [badge1, badge2, badge3].forEach(b => {
    if (!b) return;
    if (count > 0) { b.textContent = count; b.style.display = 'flex'; }
    else           { b.style.display = 'none'; }
  });
}

async function pollNotifications() {
  try {
    const { count } = await api('GET', '/api/notifications/unread-count');
    updateNotifBadge(count);
  } catch {}
  setTimeout(pollNotifications, 30000);
}

async function loadNotifications() {
  try {
    const notifs = await api('GET', '/api/notifications');
    const el = document.getElementById('notifications-list');
    if (!notifs.length) {
      el.innerHTML = '<div class="empty-state">All clear — no notifications.</div>';
      return;
    }
    el.innerHTML = notifs.map(n => `
      <div class="notif-item ${n.is_read ? 'read' : 'unread'}" id="notif-${n.id}">
        <div class="notif-dot ${n.type}"></div>
        <div class="notif-content">
          <div class="notif-title">${esc(n.title)}</div>
          ${n.message ? `<div class="notif-msg">${esc(n.message)}</div>` : ''}
          <div class="notif-time">${fmtTimeAgo(n.created_at)}</div>
        </div>
        <div class="action-btns">
          ${!n.is_read ? `<button class="btn btn-sm btn-secondary" onclick="markNotifRead(${n.id})">Read</button>` : ''}
          <button class="btn btn-sm btn-danger" onclick="deleteNotif(${n.id})">&#215;</button>
        </div>
      </div>
    `).join('');
    updateNotifBadge(notifs.filter(n => !n.is_read).length);
  } catch (e) { showToast(e.message, 'error'); }
}

async function markNotifRead(id) {
  await api('PUT', `/api/notifications/${id}/read`);
  loadNotifications();
}
async function markAllRead() {
  await api('PUT', '/api/notifications/mark-all-read');
  loadNotifications();
  showToast('All notifications marked read', 'success');
}
async function deleteNotif(id) {
  await api('DELETE', `/api/notifications/${id}`);
  loadNotifications();
}

/* ══════════════════════════════════════════════════════════════
   APPLICATION ANSWERS (Questions)
══════════════════════════════════════════════════════════════ */
async function loadAnswers() {
  try {
    allAnswers = await api('GET', '/api/answers');
    renderQuestionsForm(allAnswers);
  } catch (e) { showToast(e.message, 'error'); }
}

function renderQuestionsForm(answers) {
  const el = document.getElementById('questions-form');
  // Group by category
  const cats = {};
  answers.forEach(a => {
    if (!cats[a.category]) cats[a.category] = [];
    cats[a.category].push(a);
  });
  el.innerHTML = Object.entries(cats).map(([cat, qs]) => `
    <div class="question-category">${esc(cat)}</div>
    ${qs.map(q => `
      <div class="form-group">
        <label>${esc(q.question_label)}</label>
        <input
          type="text"
          class="form-control answer-input"
          data-key="${esc(q.question_key)}"
          value="${esc(q.answer || '')}"
          placeholder="Your answer..."
        />
      </div>
    `).join('')}
  `).join('');
}

async function saveAllAnswers() {
  const inputs = document.querySelectorAll('.answer-input');
  const payload = Array.from(inputs).map(inp => ({
    question_key: inp.dataset.key,
    answer: inp.value.trim(),
  }));
  try {
    const result = await api('POST', '/api/answers/save-all', payload);
    showToast(`Saved ${result.saved} answers!`, 'success');
    await loadAnswers();
  } catch (e) { showToast(e.message, 'error'); }
}

/* ══════════════════════════════════════════════════════════════
   CREDENTIALS (Password Vault)
══════════════════════════════════════════════════════════════ */
async function loadCredentials() {
  try {
    allCreds = await api('GET', '/api/credentials');
    renderCredentials(allCreds);
  } catch (e) { showToast(e.message, 'error'); }
}

function renderCredentials(creds) {
  const el = document.getElementById('credentials-list');
  if (!creds.length) {
    el.innerHTML = '<div class="empty-state">No passwords saved yet. Add one above.</div>';
    return;
  }
  el.innerHTML = creds.map(c => `
    <div class="cred-item">
      <div>
        <div class="cred-company">${esc(c.company_name)}</div>
        <div class="cred-domain">${esc(c.workday_domain || '—')}</div>
        <div class="cred-email">${esc(c.email || '—')}</div>
      </div>
      <div class="action-btns">
        <button class="btn btn-sm btn-secondary" onclick="editCred(${c.id})">Edit</button>
        <button class="btn btn-sm btn-danger" onclick="deleteCred(${c.id})">Del</button>
      </div>
    </div>
  `).join('');
}

function openCredModal(cred = null) {
  const isEdit = !!cred;
  document.getElementById('cred-modal-title').textContent = isEdit ? 'Edit Password' : 'Add Workday Password';
  document.getElementById('cred-id').value       = cred?.id || '';
  document.getElementById('cred-company').value  = cred?.company_name || '';
  document.getElementById('cred-domain').value   = cred?.workday_domain || '';
  document.getElementById('cred-email').value    = cred?.email || '';
  document.getElementById('cred-password').value = '';
  document.getElementById('cred-notes').value    = cred?.notes || '';
  openModal('cred-modal');
}

function editCred(id) {
  const c = allCreds.find(x => x.id === id);
  if (c) openCredModal(c);
}

async function saveCredential() {
  const id       = document.getElementById('cred-id').value;
  const company  = document.getElementById('cred-company').value.trim();
  const password = document.getElementById('cred-password').value;
  const payload  = {
    company_name:   company,
    workday_domain: document.getElementById('cred-domain').value.trim() || null,
    email:          document.getElementById('cred-email').value.trim() || null,
    password:       password,
    notes:          document.getElementById('cred-notes').value.trim() || null,
  };
  if (!company)  { showToast('Company name required', 'error'); return; }
  if (!id && !password) { showToast('Password required', 'error'); return; }
  try {
    if (id) {
      if (!password) delete payload.password;
      await api('PUT', `/api/credentials/${id}`, payload);
      showToast('Password updated!', 'success');
    } else {
      await api('POST', '/api/credentials', payload);
      showToast('Password saved!', 'success');
    }
    closeModal('cred-modal');
    await loadCredentials();
  } catch (e) { showToast(e.message, 'error'); }
}

async function deleteCred(id) {
  if (!confirm('Delete this saved password?')) return;
  await api('DELETE', `/api/credentials/${id}`);
  showToast('Deleted', 'info');
  await loadCredentials();
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
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">No jobs yet. Click "+ Add Job" to start.</div></td></tr>`;
    return;
  }
  tbody.innerHTML = jobs.map(j => `
    <tr>
      <td>
        <div style="font-weight:600">${esc(j.company)}</div>
        ${j.source ? `<div style="font-size:11px;color:var(--text-muted)">${esc(j.source)}</div>` : ''}
      </td>
      <td>${esc(j.title)}</td>
      <td>${statusBadge(j.status)}</td>
      <td class="hide-sm" style="font-size:12px;color:var(--text-muted)">${esc(j.location || '—')}</td>
      <td class="hide-sm" style="font-size:12px;color:var(--text-muted)">${fmtDate(j.date_applied) || '—'}</td>
      <td class="hide-sm" style="font-size:12px;color:var(--text-muted)">${fmtDate(j.last_status_check) || '—'}</td>
      <td>
        <div class="action-btns">
          ${j.job_url ? `<a href="${j.job_url}" target="_blank" class="btn btn-sm btn-secondary">View</a>` : ''}
          <button class="btn btn-sm btn-outline" onclick="openApplyModal(${j.id})">Apply</button>
          <button class="btn btn-sm btn-secondary" onclick="editJob(${j.id})">Edit</button>
          <button class="btn btn-sm btn-secondary" onclick="checkStatus(${j.id})" title="Check Workday">&#8635;</button>
          <button class="btn btn-sm btn-danger" onclick="deleteJob(${j.id})">&#215;</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function filterJobs() {
  const q = document.getElementById('job-search').value.toLowerCase();
  const s = document.getElementById('job-status-filter').value;
  renderJobs(allJobs.filter(j =>
    (!q || j.company.toLowerCase().includes(q) || j.title.toLowerCase().includes(q)) &&
    (!s || j.status === s)
  ));
}

/* Job Modal */
function openJobModal(job = null) {
  const isEdit = !!job;
  document.getElementById('job-modal-title').textContent = isEdit ? 'Edit Job' : 'Add Job Application';
  document.getElementById('job-id').value          = job?.id || '';
  document.getElementById('job-company').value     = job?.company || '';
  document.getElementById('job-title').value       = job?.title || '';
  document.getElementById('job-url').value         = job?.job_url || '';
  document.getElementById('job-workday-url').value = job?.workday_url || '';
  document.getElementById('job-status').value      = job?.status || 'To Apply';
  document.getElementById('job-location').value    = job?.location || '';
  document.getElementById('job-salary').value      = job?.salary_range || '';
  document.getElementById('job-source').value      = job?.source || 'LinkedIn';
  document.getElementById('job-description').value = job?.job_description || '';
  document.getElementById('job-notes').value       = job?.notes || '';
  document.getElementById('apply-now-btn').style.display = isEdit ? 'none' : 'inline-flex';
  openModal('job-modal');
}
function editJob(id) { const j = allJobs.find(x => x.id === id); if (j) openJobModal(j); }

async function saveJob() {
  const id = document.getElementById('job-id').value;
  const payload = {
    company:         document.getElementById('job-company').value.trim(),
    title:           document.getElementById('job-title').value.trim(),
    job_url:         document.getElementById('job-url').value.trim() || null,
    workday_url:     document.getElementById('job-workday-url').value.trim() || null,
    status:          document.getElementById('job-status').value,
    location:        document.getElementById('job-location').value.trim() || null,
    salary_range:    document.getElementById('job-salary').value.trim() || null,
    source:          document.getElementById('job-source').value,
    job_description: document.getElementById('job-description').value.trim() || null,
    notes:           document.getElementById('job-notes').value.trim() || null,
  };
  if (!payload.company || !payload.title) { showToast('Company and Title required', 'error'); return; }
  try {
    if (id) { await api('PUT', `/api/jobs/${id}`, payload); showToast('Updated!', 'success'); }
    else    { await api('POST', '/api/jobs', payload);      showToast('Job added!', 'success'); }
    closeModal('job-modal');
    await loadJobs(); loadStats(); renderOverview();
  } catch (e) { showToast(e.message, 'error'); }
}

async function triggerApply() {
  // Save job first, then open apply modal
  await saveJob();
  if (allJobs.length) openApplyModal(allJobs[0].id);
}

async function deleteJob(id) {
  if (!confirm('Delete this job?')) return;
  await api('DELETE', `/api/jobs/${id}`);
  showToast('Deleted', 'info');
  await loadJobs(); loadStats(); renderOverview();
}

async function checkStatus(id) {
  showToast('Checking Workday...', 'info');
  try {
    const r = await api('POST', `/api/jobs/${id}/check-status`);
    if (r.success)          showToast(`Status: ${r.status}`, 'success');
    else if (r.wrong_password) showToast('Wrong password — check Job Setup > Passwords', 'error');
    else if (r.no_account)     showToast('No account found for this company', 'info');
    else                    showToast(r.error || 'Check failed', 'error');
    await loadJobs();
  } catch (e) { showToast(e.message, 'error'); }
}

async function refreshAllStatuses() {
  showToast('Checking all Workday statuses...', 'info');
  try {
    const r = await api('POST', '/api/jobs/check-all-statuses');
    showToast(`Checked ${r.checked} jobs`, 'success');
    await loadJobs(); loadStats(); renderOverview();
  } catch (e) { showToast(e.message, 'error'); }
}

/* ── Apply Modal ──────────────────────────────────────────────── */
function openApplyModal(jobId) {
  const job = allJobs.find(j => j.id === jobId);
  if (!job) return;
  document.getElementById('apply-job-id').value = jobId;
  document.getElementById('apply-company-name').textContent = job.company;
  // Pre-fill email from saved answers if available
  const emailAnswer = allAnswers.find(a => a.question_key === 'email');
  document.getElementById('apply-email').value    = emailAnswer?.answer || '';
  document.getElementById('apply-password').value = '';
  openModal('apply-modal');
}

async function confirmApply() {
  const jobId    = document.getElementById('apply-job-id').value;
  const email    = document.getElementById('apply-email').value.trim();
  const password = document.getElementById('apply-password').value;
  showToast('Launching Workday automation...', 'info');
  try {
    const r = await api('POST', `/api/jobs/${jobId}/apply`, { job_id: parseInt(jobId), email, password });
    closeModal('apply-modal');
    if (r.wrong_password) {
      showToast('Wrong password! Check Job Setup > Notifications for details.', 'error');
    } else if (r.no_account) {
      showToast('New account created — check the browser window to review & submit.', 'info');
    } else if (r.success) {
      showToast(r.status, 'success');
    } else {
      showToast(r.error || 'Apply failed', 'error');
    }
    await loadJobs(); loadStats(); renderOverview();
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
      <td class="hide-sm" style="font-size:12px;color:var(--text-muted)">${esc(c.role || '—')}</td>
      <td>${chatStatusBadge(c.status)}</td>
      <td class="hide-sm" style="font-size:12px;color:var(--text-muted)">${esc(c.next_action || '—')}</td>
      <td class="hide-sm" style="font-size:12px;color:var(--text-muted)">${fmtDate(c.follow_up_date) || '—'}</td>
      <td>
        <div class="action-btns">
          <button class="btn btn-sm btn-secondary" onclick="editChat(${c.id})">Edit</button>
          <button class="btn btn-sm btn-danger" onclick="deleteChat(${c.id})">&#215;</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function filterChats() {
  const q = document.getElementById('chat-search').value.toLowerCase();
  const s = document.getElementById('chat-status-filter').value;
  renderChats(allChats.filter(c =>
    (!q || c.person_name.toLowerCase().includes(q) || (c.company||'').toLowerCase().includes(q)) &&
    (!s || c.status === s)
  ));
}

function openChatModal(chat = null) {
  const isEdit = !!chat;
  document.getElementById('chat-modal-title').textContent = isEdit ? 'Edit Coffee Chat' : 'Add Coffee Chat';
  document.getElementById('chat-id').value             = chat?.id || '';
  document.getElementById('chat-name').value           = chat?.person_name || '';
  document.getElementById('chat-company').value        = chat?.company || '';
  document.getElementById('chat-role').value           = chat?.role || '';
  document.getElementById('chat-linkedin').value       = chat?.linkedin_url || '';
  document.getElementById('chat-email').value          = chat?.email || '';
  document.getElementById('chat-status').value         = chat?.status || 'To Reach Out';
  document.getElementById('chat-meeting-date').value   = toDatetimeLocal(chat?.date_meeting);
  document.getElementById('chat-followup-date').value  = toDatetimeLocal(chat?.follow_up_date);
  document.getElementById('chat-next-action').value    = chat?.next_action || '';
  document.getElementById('chat-notes').value          = chat?.notes || '';
  document.getElementById('chat-meeting-notes').value  = chat?.meeting_notes || '';
  openModal('chat-modal');
}
function editChat(id) { const c = allChats.find(x => x.id === id); if (c) openChatModal(c); }

async function saveChat() {
  const id = document.getElementById('chat-id').value;
  const payload = {
    person_name:   document.getElementById('chat-name').value.trim(),
    company:       document.getElementById('chat-company').value.trim() || null,
    role:          document.getElementById('chat-role').value.trim() || null,
    linkedin_url:  document.getElementById('chat-linkedin').value.trim() || null,
    email:         document.getElementById('chat-email').value.trim() || null,
    status:        document.getElementById('chat-status').value,
    date_meeting:  document.getElementById('chat-meeting-date').value || null,
    follow_up_date: document.getElementById('chat-followup-date').value || null,
    next_action:   document.getElementById('chat-next-action').value.trim() || null,
    notes:         document.getElementById('chat-notes').value.trim() || null,
    meeting_notes: document.getElementById('chat-meeting-notes').value.trim() || null,
  };
  if (!payload.person_name) { showToast('Name required', 'error'); return; }
  try {
    if (id) { await api('PUT', `/api/coffee-chats/${id}`, payload); showToast('Updated!', 'success'); }
    else    { await api('POST', '/api/coffee-chats', payload);      showToast('Added!', 'success'); }
    closeModal('chat-modal');
    await loadChats(); loadStats(); renderOverview();
  } catch (e) { showToast(e.message, 'error'); }
}

async function deleteChat(id) {
  if (!confirm('Delete this coffee chat?')) return;
  await api('DELETE', `/api/coffee-chats/${id}`);
  showToast('Deleted', 'info');
  await loadChats(); loadStats(); renderOverview();
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
      <td class="hide-sm" style="font-size:12px"><a href="mailto:${e.recipient_email}">${esc(e.recipient_email)}</a></td>
      <td>${esc(e.company || '—')}</td>
      <td class="hide-sm" style="font-size:12px;color:var(--text-muted);max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(e.subject || '—')}</td>
      <td>${emailStatusBadge(e.status)}</td>
      <td class="hide-sm" style="font-size:12px;color:var(--text-muted)">${fmtDate(e.date_sent) || '—'}</td>
      <td class="hide-sm" style="font-size:12px;color:var(--text-muted)">${fmtDate(e.follow_up_date) || '—'}</td>
      <td>
        <div class="action-btns">
          <button class="btn btn-sm btn-secondary" onclick="editEmail(${e.id})">Edit</button>
          <button class="btn btn-sm btn-danger" onclick="deleteEmail(${e.id})">&#215;</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function openEmailModal(email = null) {
  const isEdit = !!email;
  document.getElementById('email-modal-title').textContent   = isEdit ? 'Edit Email' : 'Add Email Outreach';
  document.getElementById('email-id').value                  = email?.id || '';
  document.getElementById('email-recipient-name').value      = email?.recipient_name || '';
  document.getElementById('email-recipient-email').value     = email?.recipient_email || '';
  document.getElementById('email-company').value             = email?.company || '';
  document.getElementById('email-status').value              = email?.status || 'Draft';
  document.getElementById('email-subject').value             = email?.subject || '';
  document.getElementById('email-date-sent').value           = email?.date_sent?.split('T')[0] || '';
  document.getElementById('email-followup-date').value       = email?.follow_up_date?.split('T')[0] || '';
  document.getElementById('email-body').value                = email?.email_body || '';
  document.getElementById('email-notes').value               = email?.notes || '';
  openModal('email-modal');
}
function editEmail(id) { const e = allEmails.find(x => x.id === id); if (e) openEmailModal(e); }

async function saveEmail() {
  const id = document.getElementById('email-id').value;
  const payload = {
    recipient_name:  document.getElementById('email-recipient-name').value.trim(),
    recipient_email: document.getElementById('email-recipient-email').value.trim(),
    company:         document.getElementById('email-company').value.trim() || null,
    subject:         document.getElementById('email-subject').value.trim() || null,
    status:          document.getElementById('email-status').value,
    date_sent:       document.getElementById('email-date-sent').value || null,
    follow_up_date:  document.getElementById('email-followup-date').value || null,
    email_body:      document.getElementById('email-body').value.trim() || null,
    notes:           document.getElementById('email-notes').value.trim() || null,
  };
  if (!payload.recipient_name || !payload.recipient_email) {
    showToast('Name and email required', 'error'); return;
  }
  try {
    if (id) { await api('PUT', `/api/emails/${id}`, payload); showToast('Updated!', 'success'); }
    else    { await api('POST', '/api/emails', payload);      showToast('Email tracked!', 'success'); }
    closeModal('email-modal');
    await loadEmails(); loadStats();
  } catch (e) { showToast(e.message, 'error'); }
}

async function deleteEmail(id) {
  if (!confirm('Delete this email?')) return;
  await api('DELETE', `/api/emails/${id}`);
  showToast('Deleted', 'info');
  await loadEmails(); loadStats();
}

/* ══════════════════════════════════════════════════════════════
   RESUME
══════════════════════════════════════════════════════════════ */
async function loadBaseResume() {
  try {
    const resumes = await api('GET', '/api/resumes');
    const base = resumes.find(r => r.is_base) || resumes[0];
    if (!base) { showToast('No resume saved yet', 'info'); return; }
    const full = await api('GET', `/api/resumes/${base.id}`);
    document.getElementById('resume-name').value    = full.name;
    document.getElementById('resume-content').value = full.content;
    showToast('Resume loaded!', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

async function saveResume() {
  const name    = document.getElementById('resume-name').value.trim();
  const content = document.getElementById('resume-content').value.trim();
  if (!name || !content) { showToast('Name and content required', 'error'); return; }
  try {
    await api('POST', '/api/resumes', { name, content, is_base: true });
    showToast('Resume saved!', 'success');
  } catch (e) { showToast(e.message, 'error'); }
}

function populateTailorJobSelect() {
  const sel = document.getElementById('tailor-job-select');
  sel.innerHTML = '<option value="">-- Select job --</option>';
  allJobs.forEach(j => {
    const opt = document.createElement('option');
    opt.value = j.id;
    opt.textContent = `${j.company} — ${j.title}`;
    sel.appendChild(opt);
  });
}

async function tailorResume() {
  const jd = document.getElementById('jd-input').value.trim();
  if (!jd) { showToast('Paste a job description first', 'error'); return; }
  const jobId = document.getElementById('tailor-job-select').value || null;
  showToast('Tailoring resume with AI...', 'info');
  try {
    const r = await api('POST', '/api/resumes/tailor', {
      job_description: jd,
      job_id: jobId ? parseInt(jobId) : null,
    });
    document.getElementById('tailored-text').textContent = r.tailored_resume;
    document.getElementById('tailor-result').style.display = 'block';
    showToast(r.ai_enabled ? 'Resume tailored!' : 'Showing base resume (add ANTHROPIC_API_KEY)', r.ai_enabled ? 'success' : 'info');
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
  recentEl.innerHTML = !recent.length
    ? '<div class="empty-state">No applications yet</div>'
    : recent.map(j => `
        <div class="list-item">
          <div class="list-item-main">
            <div class="list-item-company">${esc(j.company)}</div>
            <div class="list-item-sub">${esc(j.title)}</div>
          </div>
          ${statusBadge(j.status)}
        </div>
      `).join('');

  // Coffee chat follow-ups
  const now = new Date();
  const upcoming = allChats
    .filter(c => c.follow_up_date && new Date(c.follow_up_date) >= now)
    .sort((a, b) => new Date(a.follow_up_date) - new Date(b.follow_up_date))
    .slice(0, 5);
  const followEl = document.getElementById('upcoming-followups-list');
  followEl.innerHTML = !upcoming.length
    ? '<div class="empty-state">No upcoming follow-ups</div>'
    : upcoming.map(c => `
        <div class="list-item">
          <div class="list-item-main">
            <div class="list-item-company">${esc(c.person_name)}</div>
            <div class="list-item-sub">${esc(c.company || '')} · ${fmtDate(c.follow_up_date)}</div>
          </div>
          ${chatStatusBadge(c.status)}
        </div>
      `).join('');

  // Pipeline
  const stages = ['To Apply', 'Applied', 'Phone Screen', 'Interview', 'Offer', 'Rejected'];
  const counts = {};
  allJobs.forEach(j => { counts[j.status] = (counts[j.status] || 0) + 1; });
  document.getElementById('pipeline-view').innerHTML = stages.map(s => `
    <div class="pipeline-stage ${counts[s] ? 'has-items' : ''}">
      <div class="pipeline-stage-name">${s}</div>
      <div class="pipeline-count" style="color:${pipelineColor(s)}">${counts[s] || 0}</div>
    </div>
  `).join('');
}

/* ══════════════════════════════════════════════════════════════
   MODAL HELPERS
══════════════════════════════════════════════════════════════ */
function openModal(id)  { document.getElementById(id).classList.add('open'); }
function closeModal(id, e) {
  if (e && e.target !== document.getElementById(id)) return;
  document.getElementById(id).classList.remove('open');
}

function togglePwd(inputId) {
  const inp = document.getElementById(inputId);
  inp.type = inp.type === 'password' ? 'text' : 'password';
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

function fmtTimeAgo(iso) {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)   return 'just now';
  if (mins < 60)  return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)   return `${hrs}h ago`;
  return fmtDate(iso);
}

function toDatetimeLocal(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return '';
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function statusBadge(s) {
  const m = { 'To Apply':'badge-gray','Applied':'badge-blue','Phone Screen':'badge-yellow',
              'Interview':'badge-orange','Offer':'badge-green','Rejected':'badge-red',
              'Withdrawn':'badge-gray','In Progress':'badge-blue','Under Review':'badge-yellow' };
  return `<span class="badge ${m[s]||'badge-gray'}">${esc(s)}</span>`;
}
function chatStatusBadge(s) {
  const m = { 'To Reach Out':'badge-gray','Message Sent':'badge-blue','Scheduled':'badge-yellow',
              'Completed':'badge-green','Follow Up':'badge-orange','No Response':'badge-red' };
  return `<span class="badge ${m[s]||'badge-gray'}">${esc(s)}</span>`;
}
function emailStatusBadge(s) {
  const m = { 'Draft':'badge-gray','Sent':'badge-blue','Replied':'badge-green',
              'Follow Up':'badge-yellow','No Response':'badge-red' };
  return `<span class="badge ${m[s]||'badge-gray'}">${esc(s)}</span>`;
}
function pipelineColor(s) {
  const m = { 'To Apply':'var(--text-muted)','Applied':'var(--blue)','Phone Screen':'var(--yellow)',
              'Interview':'var(--orange)','Offer':'var(--green)','Rejected':'var(--red)' };
  return m[s] || 'var(--text)';
}

let toastTimer;
function showToast(msg, type = 'info') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = 'toast'; }, 3500);
}
