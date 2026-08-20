const state = { user: null, authMode: 'login', view: 'profile' };
const $ = (selector) => document.querySelector(selector);

async function api(path, options = {}) {
    const response = await fetch(path, {
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
        ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || 'Something went wrong');
    return data;
}

function notice(message, error = false) {
    $('#notice').innerHTML = message ? `<div class="notice${error ? ' error' : ''}">${message}</div>` : '';
}

function setAuthMode(mode) {
    state.authMode = mode;
    document.querySelectorAll('[data-auth]').forEach((button) => button.classList.toggle('active', button.dataset.auth === mode));
    $('#name-field').hidden = mode !== 'signup';
    $('#name-field input').required = mode === 'signup';
    $('#auth-submit').textContent = mode === 'signup' ? 'Create account' : 'Log in';
}

async function submitAuth(event) {
    event.preventDefault();
    const form = new FormData(event.target);
    const payload = Object.fromEntries(form.entries());
    try {
        if (state.authMode === 'signup') await api('/api/auth/signup', { method: 'POST', body: JSON.stringify(payload) });
        await api('/api/auth/login', { method: 'POST', body: JSON.stringify(payload) });
        await loadApp();
        notice('');
    } catch (error) { notice(error.message, true); }
}

function showView(view) {
    state.view = view;
    document.querySelectorAll('.view').forEach((element) => { element.hidden = element.id !== `${view}-view`; });
    if (view === 'profile') renderProfile();
    if (view === 'matches') loadMatches();
    if (view === 'schedule') loadSchedule();
}

function renderProfile() {
    $('#profile-view').innerHTML = `
        <section class="section-heading"><p class="eyebrow">Function 01 / User & skills profile</p><h1>Your exchange profile</h1><p>Tell the community what you can teach and what you want to learn.</p></section>
        <form id="profile-form" class="panel form-grid">
            <div class="identity"><span class="avatar">${state.user.name[0].toUpperCase()}</span><div><strong>${state.user.name}</strong><small>${state.user.email}</small></div></div>
            <label>Skills you offer <span>comma-separated</span><input name="offered_skills" value="${state.user.offered_skills.join(', ')}" placeholder="e.g. Python, photography"></label>
            <label>Skills you want <span>comma-separated</span><input name="wanted_skills" value="${state.user.wanted_skills.join(', ')}" placeholder="e.g. Spanish, cooking"></label>
            <button type="submit">Save profile</button>
        </form>`;
    $('#profile-form').addEventListener('submit', saveProfile);
}

async function saveProfile(event) {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
        const data = await api('/api/profile', { method: 'PUT', body: JSON.stringify({
            offered_skills: form.get('offered_skills').split(','),
            wanted_skills: form.get('wanted_skills').split(','),
        }) });
        state.user = data.user;
        notice('Your skills have been updated.');
        renderProfile();
    } catch (error) { notice(error.message, true); }
}

async function loadMatches() {
    try {
        const data = await api('/api/matches');
        $('#matches-view').innerHTML = `<section class="section-heading"><p class="eyebrow">Function 02 / Matchmaking</p><h1>Mutual matches</h1><p>Both sides get something useful. Matches are ranked by exchanged skills.</p></section>
        ${data.matches.length ? `<div class="match-list">${data.matches.map(match => `<article class="panel"><div class="match-top"><div class="identity"><span class="avatar warm">${match.user.name[0].toUpperCase()}</span><div><h2>${match.user.name}</h2><small>Exchange score: ${match.score}</small></div></div><button class="button schedule-button" data-view="schedule">Schedule</button></div><div class="exchange"><div><span class="label">You learn</span><div class="tags">${match.you_can_learn.map(skill => `<span>${skill}</span>`).join('')}</div></div><div class="exchange-arrow">&harr;</div><div><span class="label">You teach</span><div class="tags">${match.they_can_learn.map(skill => `<span>${skill}</span>`).join('')}</div></div></div></article>`).join('')}</div>` : '<div class="panel empty"><h2>No mutual matches yet</h2><p>Update both skill lists. A match appears when both sides have a skill to exchange.</p><button class="button" data-view="profile">Update my skills</button></div>'}`;
        $('#matches-view').querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => { showView(button.dataset.view); }));
    } catch (error) { notice(error.message, true); }
}

async function loadSchedule() {
    try {
        const [usersData, sessionsData] = await Promise.all([api('/api/users'), api('/api/sessions')]);
        $('#schedule-view').innerHTML = `<section class="section-heading"><p class="eyebrow">Function 03 / Session scheduling</p><h1>Make the exchange real</h1><p>Propose a time to another user, then confirm incoming proposals.</p></section><div class="schedule-grid"><form id="session-form" class="panel stack"><h2>Propose a session</h2><label>Person<select name="recipient_id" required><option value="">Choose a person</option>${usersData.users.map(user => `<option value="${user.id}">${user.name}</option>`).join('')}</select></label><label>Suggested time<input type="datetime-local" name="proposed_time" required></label><button type="submit">Send proposal</button></form><section><h2>Your proposals</h2>${sessionsData.sessions.length ? `<div class="proposal-list">${sessionsData.sessions.map(item => `<article class="panel proposal"><div><strong>${item.proposer_name} &rarr; ${item.recipient_name}</strong><small>${item.proposed_time}</small></div><span class="status ${item.status}">${item.status}</span>${item.recipient_id === state.user.id && item.status === 'proposed' ? `<button class="button accept-button" data-id="${item.id}">Accept</button>` : ''}</article>`).join('')}</div>` : '<div class="panel empty"><p>No sessions proposed yet.</p></div>'}</section></div>`;
        $('#session-form').addEventListener('submit', createSession);
        $('#schedule-view').querySelectorAll('.accept-button').forEach((button) => button.addEventListener('click', () => acceptSession(button.dataset.id)));
    } catch (error) { notice(error.message, true); }
}

async function createSession(event) {
    event.preventDefault();
    const form = new FormData(event.target);
    try { await api('/api/sessions', { method: 'POST', body: JSON.stringify(Object.fromEntries(form.entries())) }); notice('Session proposal sent.'); loadSchedule(); } catch (error) { notice(error.message, true); }
}

async function acceptSession(id) {
    try { await api(`/api/sessions/${id}/accept`, { method: 'POST' }); notice('Session confirmed.'); loadSchedule(); } catch (error) { notice(error.message, true); }
}

async function loadApp() {
    const data = await api('/api/me');
    state.user = data.user;
    $('#auth-view').hidden = true;
    $('#app-view').hidden = false;
    $('#app-nav').hidden = false;
    showView(state.view);
}

async function logout() {
    await api('/api/auth/logout', { method: 'POST' });
    state.user = null;
    $('#auth-view').hidden = false;
    $('#app-view').hidden = true;
    $('#app-nav').hidden = true;
    setAuthMode('login');
}

document.querySelectorAll('[data-auth]').forEach((button) => button.addEventListener('click', () => setAuthMode(button.dataset.auth)));
document.querySelectorAll('[data-view]').forEach((button) => button.addEventListener('click', () => showView(button.dataset.view)));
$('#auth-form').addEventListener('submit', submitAuth);
$('#logout').addEventListener('click', logout);
setAuthMode('login');
loadApp().catch(() => { $('#auth-view').hidden = false; });
