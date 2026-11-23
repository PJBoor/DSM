const state = { token: localStorage.getItem("holistic_token") || "", lang: localStorage.getItem("holistic_lang") || "fr", role: "" };

const I18N = {
  fr: { login: "Se connecter", overview: "Vue d'ensemble", err: "Erreur" },
  en: { login: "Sign in", overview: "Overview", err: "Error" },
};
const t = (k) => (I18N[state.lang] || I18N.fr)[k] || k;

async function api(path, opts = {}) {
  const headers = { "Accept-Language": state.lang, ...(opts.headers || {}) };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  const res = await fetch(path, { ...opts, headers });
  let body = null;
  try { body = await res.json(); } catch (e) { /* pas de JSON */ }
  if (!res.ok) {
    const msg = body && body.error ? body.error.message : `HTTP ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return body;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function flash(msg, ok = true) {
  const div = document.createElement("div");
  div.className = `flash ${ok ? "ok" : "err"}`;
  div.textContent = msg;
  document.body.appendChild(div);
  setTimeout(() => div.remove(), 5000);
}

function bar(pct, cls) {
  const c = pct > 100 ? "bad" : pct > 90 ? "warn" : cls || "ok";
  return `<div class="bar"><div class="${c}" style="width:${Math.min(100, Math.max(0, pct))}%"></div></div>`;
}

function pill(text, kind) {
  return `<span class="pill ${kind}">${esc(text)}</span>`;
}

async function login() {
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;
  try {
    const res = await fetch("/auth/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email, password }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error ? body.error.message : "401");
    state.token = body.access_token;
    localStorage.setItem("holistic_token", state.token);
    const me = await api("/auth/users/me");
    state.role = me.role;
    showApp();
  } catch (e) {
    document.getElementById("login-error").textContent = e.message;
  }
}

function logout() {
  state.token = "";
  localStorage.removeItem("holistic_token");
  location.reload();
}

function showApp() {
  document.getElementById("login-view").classList.add("hidden");
  document.getElementById("app-view").classList.remove("hidden");
  document.getElementById("nav").classList.remove("hidden");
  document.getElementById("logout").classList.remove("hidden");
  document.getElementById("whoami").textContent = `${state.role}`;
  loadTab("overview");
}

function setTab(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.add("hidden"));
  document.getElementById(`tab-${name}`).classList.remove("hidden");
  loadTab(name);
}

async function loadTab(name) {
  const el = document.getElementById(`tab-${name}`);
  el.innerHTML = `<p class="muted">Chargement…</p>`;
  try {
    if (name === "overview") await renderOverview(el);
    if (name === "market") await renderMarket(el);
    if (name === "strategy") await renderStrategy(el);
    if (name === "network") await renderNetwork(el);
    if (name === "finance") await renderFinance(el);
    if (name === "rai") await renderRai(el);
  } catch (e) {
    el.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

async function renderOverview(el) {
  const [rai, kpis, tl, cred, alerts] = await Promise.all([
    api("/responsible-ai/dashboard"),
    api("/kpis/dashboard"),
    api("/thought-leadership/index"),
    api("/advisory/credibility-dashboard"),
    api("/reengagement-alerts"),
  ]);
  el.innerHTML = `
    <div class="grid">
      <div class="kpi-card"><div class="value">${tl.index}</div><div class="label">Indice de leadership d'opinion (M3)</div></div>
      <div class="kpi-card"><div class="value">${cred.credibility_index}</div><div class="label">Indice de crédibilité des conseils (M6)</div></div>
      <div class="kpi-card"><div class="value">${rai.ethics_validated}/${rai.sector_solutions_total}</div><div class="label">Revues éthiques validées (IA responsable)</div></div>
      <div class="kpi-card"><div class="value" style="color:var(--${alerts.alerts.length ? "bad" : "ok"})">${alerts.alerts.length}</div><div class="label">Alertes de réengagement réseau (M7)</div></div>
    </div>
    <div class="card"><h2>Tableau de bord KPI (M8)</h2>
      <table><tr><th>Type</th><th>Période</th><th>Valeur</th><th>Cible</th><th>Écart</th><th>Tendance</th><th>Statut</th></tr>
      ${kpis.kpis.map((k) => `<tr>
        <td>${esc(k.type)}</td><td>${esc(k.period)}</td><td>${k.value}</td><td>${k.target}</td>
        <td>${k.deviation === null ? "∞" : (k.deviation * 100).toFixed(1) + "%"}</td><td>${esc(k.trend)}</td>
        <td>${k.alert ? pill("ALERTE", "bad") : pill("OK", "ok")}</td></tr>`).join("")}
      </table></div>
    <div class="card"><h2>Couverture IA responsable</h2>
      <div class="row">
        ${pill(`${rai.ethics_validated} éthiques validées`, "ok")}
        ${pill(`${rai.ethics_pending} éthiques en attente`, "warn")}
        ${pill(`${rai.privacy_impacts_open} impacts vie privée ouverts`, rai.privacy_impacts_open ? "bad" : "ok")}
        ${pill(`${rai.fairness_missing} bilans d'équité manquants`, rai.fairness_missing ? "warn" : "ok")}
      </div></div>`;
}

async function renderMarket(el) {
  const [competitors, signals, alerts, cases] = await Promise.all([
    api("/competitors"), api("/signals"), api("/signals/alerts"), api("/case-studies/count-by-keyword"),
  ]);
  el.innerHTML = `
    <div class="card"><h2>Concurrents (M1)</h2>
      <table><tr><th>Nom</th><th>Secteur</th><th>Part de marché</th><th>Offres</th></tr>
      ${competitors.map((c) => `<tr><td>${esc(c.name)}</td><td>${esc(c.sector)}</td><td>${bar(c.market_share * 100)}${(c.market_share * 100).toFixed(0)}%</td><td>${esc((c.offers || []).join(", "))}</td></tr>`).join("")}
      </table></div>
    <div class="card"><h2>Signaux de marché</h2>
      <table><tr><th>Date</th><th>Type</th><th>Source</th><th>Pertinence</th></tr>
      ${signals.map((s) => `<tr><td>${esc(s.date)}</td><td>${esc(s.type)}</td><td>${esc(s.source)}</td>
        <td>${bar(s.relevance_score, s.relevance_score >= 70 ? "warn" : "ok")} ${s.relevance_score}</td></tr>`).join("")}
      </table>
      <h3>Alertes (seuil dépassé)</h3>
      ${alerts.length ? `<ul>${alerts.map((a) => `<li>Signal #${a.signal_id} — seuil ${a.threshold}</li>`).join("")}</ul>` : '<p class="muted">Aucune alerte</p>'}
      <div class="formline">
        <label>Concurrent <select id="sig-comp">${competitors.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select></label>
        <label>Type <select id="sig-type"><option>investissement</option><option>lancement</option><option>partenariat</option><option>campagne</option></select></label>
        <label>Source <input id="sig-src" value="presse"></label>
        <label>Date <input id="sig-date" type="date" value="${new Date().toISOString().slice(0, 10)}"></label>
        <button class="btn primary" id="sig-add">Ingérer</button>
      </div></div>
    <div class="card"><h2>Études de cas par mot-clé</h2>
      <div class="row">${Object.entries(cases).map(([k, v]) => pill(`${k}: ${v}`, "info")).join(" ") || '<span class="muted">—</span>'}</div></div>`;
  document.getElementById("sig-add").onclick = async () => {
    try {
      const body = {
        competitor_id: Number(document.getElementById("sig-comp").value),
        type: document.getElementById("sig-type").value,
        source: document.getElementById("sig-src").value,
        date: document.getElementById("sig-date").value,
      };
      const s = await api("/signals", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      flash(`Signal ingéré, pertinence = ${s.relevance_score}`);
      loadTab("market");
    } catch (e) { flash(e.message, false); }
  };
}

async function renderStrategy(el) {
  const [adjs, runs] = await Promise.all([api("/strategy-adjustments"), api("/benchmark-runs")]);
  el.innerHTML = `
    <div class="card"><h2>Ajustements stratégiques (M5) — ${adjs.length}</h2>
      <table><tr><th>#</th><th>Déclencheur</th><th>Décision</th><th>Appliqué le</th><th></th></tr>
      ${adjs.map((a) => `<tr><td>${a.id}</td><td>${pill(a.trigger_type, "info")}</td><td>${esc(a.decision)}</td><td>${esc(a.applied_at)}</td>
        <td><button class="btn small" data-trace="${a.id}">Trace</button></td></tr>`).join("")}
      </table><pre id="trace-box" class="hidden"></pre></div>
    <div class="card"><h2>Benchmarks (M5)</h2>
      ${runs.map((r) => `<div class="row" style="margin-bottom:10px"><strong>${esc(r.solution_evaluated)}</strong>
        ${pill(`différenciation ${r.differentiation_score}`, r.differentiation_score < 0 ? "bad" : "ok")}
        ${r.axes.map((a) => `<span class="muted">${esc(a.axis)}: ${a.gap > 0 ? "+" : ""}${a.gap}</span>`).join(" ")}
        <button class="btn small" data-eval="${r.id}">Évaluer</button></div>`).join("") || '<p class="muted">Aucun benchmark</p>'}
      <h3>Conseils consultatifs (M6)</h3><div id="adv"></div></div>`;
  document.querySelectorAll("[data-trace]").forEach((b) => (b.onclick = async () => {
    const box = document.getElementById("trace-box");
    box.classList.remove("hidden");
    box.textContent = JSON.stringify(await api(`/strategy-adjustments/${b.dataset.trace}/trace`), null, 2);
  }));
  document.querySelectorAll("[data-eval]").forEach((b) => (b.onclick = async () => {
    try { await api(`/benchmark-runs/${b.dataset.eval}/evaluate`, { method: "POST" }); flash("Benchmark évalué"); loadTab("strategy"); }
    catch (e) { flash(e.message, false); }
  }));
  const cred = await api("/advisory/credibility-dashboard");
  document.getElementById("adv").innerHTML = `<div class="row">
    ${pill(`${cred.boards} conseils`, "info")} ${pill(`${cred.advisors} conseillers`, "info")}
    ${pill(`notoriété moy. ${cred.average_notability}/5`, "info")} ${pill(`${cred.insights_applied}/${cred.insights_total} avis appliqués`, "ok")}
    ${pill(`indice ${cred.credibility_index}`, "ok")}</div>`;
}

async function renderNetwork(el) {
  const [contacts, alerts] = await Promise.all([api("/network-contacts"), api("/reengagement-alerts")]);
  const scores = await Promise.all(contacts.map((c) => api(`/network-contacts/${c.id}/health-score`).catch(() => null)));
  el.innerHTML = `
    <div class="card"><h2>Alertes de réengagement (M7)</h2>
      ${alerts.alerts.length ? `<ul>${alerts.alerts.map((a) => `<li>Contact #${a.contact_id} — ${a.days_since_last_contact ?? "jamais"} jours sans contact (seuil ${a.required_delay} j) ${pill("RÉENGAGER", "bad")}</li>`).join("")}</ul>` : '<p class="muted">Aucune alerte</p>'}</div>
    <div class="card"><h2>Contacts réseau</h2>
      <table><tr><th>Organisation</th><th>Secteur</th><th>Influence</th><th>Santé de la relation</th></tr>
      ${contacts.map((c, i) => { const s = scores[i]; return `<tr><td>${esc(c.organization)}</td><td>${esc(c.sector)}</td>
        <td>${bar(c.influence * 100)} ${(c.influence * 100).toFixed(0)}%</td>
        <td>${s ? bar(s.health_score, s.health_score > 60 ? "ok" : s.health_score > 30 ? "warn" : "bad") + " " + s.health_score : "—"}</td></tr>`; }).join("")}
      </table></div>`;
}

async function renderFinance(el) {
  const [report, reserve] = await Promise.all([api("/budget/report?fiscal_year=2025"), api("/contingency/reserve")]);
  el.innerHTML = `
    <div class="grid">
      <div class="kpi-card"><div class="value">${reserve.total_provision}</div><div class="label">Provisions de contingence (M9)</div></div>
      <div class="kpi-card"><div class="value">${reserve.drawn}</div><div class="label">Tiré</div></div>
      <div class="kpi-card"><div class="value">${reserve.remaining}</div><div class="label">Réserve restante (plafond ${reserve.cap})</div></div>
    </div>
    <div class="card"><h2>Rapport budgétaire 2025 par pilier</h2>
      <table><tr><th>Pilier</th><th>Alloué</th><th>Consommé</th><th>Utilisation</th><th>Statut</th></tr>
      ${report.lines.map((l) => `<tr><td>M${l.pillar}</td><td>${l.allocated}</td><td>${l.consumed}</td>
        <td>${bar(l.utilization * 100)} ${(l.utilization * 100).toFixed(1)}%</td>
        <td>${l.alert === "over_budget" ? pill("DÉPASSEMENT", "bad") : l.alert === "high_utilization" ? pill("ÉLEVÉ", "warn") : pill("OK", "ok")}</td></tr>`).join("")}
      </table></div>`;
}

async function renderRai(el) {
  const [dash, solutions] = await Promise.all([api("/responsible-ai/dashboard"), api("/sector-solutions")]);
  el.innerHTML = `
    <div class="grid">
      <div class="kpi-card"><div class="value">${dash.ethics_validated}/${dash.sector_solutions_total}</div><div class="label">Revues éthiques validées</div></div>
      <div class="kpi-card"><div class="value" style="color:var(--${dash.privacy_impacts_open ? "bad" : "ok"})">${dash.privacy_impacts_open}</div><div class="label">Impacts vie privée ouverts</div></div>
      <div class="kpi-card"><div class="value" style="color:var(--${dash.fairness_missing ? "warn" : "ok"})">${dash.fairness_missing}</div><div class="label">Bilans d'équité manquants</div></div>
      <div class="kpi-card"><div class="value">${dash.pilots_missing_ethics}/${dash.pilots_total}</div><div class="label">Pilotes sans éthique validée</div></div>
    </div>
    <div class="card"><h2>Solutions sectorielles</h2>
      <table><tr><th>Secteur</th><th>Statut</th><th>Éthique</th><th>Vie privée</th><th>Équité</th><th></th></tr>
      ${solutions.map((s) => `<tr><td>${esc(s.sector)}</td><td>${pill(s.status, s.status === "published" ? "ok" : "info")}</td>
        <td>${pill(s.ethics_status, s.ethics_status === "validated" ? "ok" : "warn")}</td>
        <td>${pill(s.privacy_impact_level, s.privacy_impact_level === "high" ? "bad" : "info")}</td>
        <td>${pill(s.fairness_status, s.fairness_status === "done" ? "ok" : "warn")}</td>
        <td><button class="btn small" data-pub="${s.id}" ${s.status === "published" ? "disabled" : ""}>Publier</button></td></tr>`).join("")}
      </table></div>`;
  document.querySelectorAll("[data-pub]").forEach((b) => (b.onclick = async () => {
    try {
      await api(`/sector-solutions/${b.dataset.pub}/publish`, { method: "POST" });
      flash("Solution publiée");
      loadTab("rai");
    } catch (e) { flash(e.message, false); }
  }));
}

document.getElementById("login-btn").onclick = login;
document.getElementById("logout").onclick = logout;
document.getElementById("lang").onchange = (e) => {
  state.lang = e.target.value;
  localStorage.setItem("holistic_lang", state.lang);
  if (state.token) loadTab(document.querySelector(".tab.active").dataset.tab);
};
document.querySelectorAll(".tab").forEach((b) => (b.onclick = () => setTab(b.dataset.tab)));
document.getElementById("lang").value = state.lang;

if (state.token) {
  api("/auth/users/me").then((me) => { state.role = me.role; showApp(); }).catch(() => localStorage.removeItem("holistic_token"));
}
