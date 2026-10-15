import os
import random
import socket
from flask import Flask, jsonify, render_template_string, request

# Illustrative us-east-1 on-demand prices (USD). Always check current AWS pricing.
PRICES = {
    "ec2": {"t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416},
    "alb_hour": 0.0225,
    "fargate_vcpu_hour": 0.04048,
    "fargate_gb_hour": 0.004445,
    "nat_hour": 0.045,
    "s3_gb_month": 0.023,
}
PREVIEW_VCPU = 0.25
PREVIEW_GB = 0.5

QUESTIONS = [
    {"topic": "Linux", "q": "Which command lists files with their permissions?",
     "options": ["pwd", "ls -l", "cd -", "echo $PATH"], "answer": 1,
     "explain": "ls -l gives the long listing, including permissions, owner and size."},
    {"topic": "Linux", "q": "What does chmod 755 file set?",
     "options": ["Everyone can read, write and execute", "Only root can read it",
                 "Owner rwx, group and others r-x", "Owner r-x, others rwx"], "answer": 2,
     "explain": "7 is rwx for the owner, and each 5 is r-x for group and others."},
    {"topic": "Git", "q": "Which command creates a new branch and switches to it?",
     "options": ["git branch -d feature", "git merge feature",
                 "git stash feature", "git checkout -b feature"], "answer": 3,
     "explain": "git checkout -b (or git switch -c) creates and switches in one step."},
    {"topic": "Git", "q": "What is the main purpose of a pull request?",
     "options": ["Propose changes for review before merging", "Delete a branch",
                 "Download the repo", "Rewrite history"], "answer": 0,
     "explain": "A PR is where changes are reviewed and checks run before they reach main."},
    {"topic": "Docker", "q": "Why run a container as a non-root user?",
     "options": ["It starts faster", "It limits the damage if the app is compromised",
                 "It uses less memory", "Docker requires it"], "answer": 1,
     "explain": "If an attacker gets in, they do not have root inside the container."},
    {"topic": "Docker", "q": "Which Dockerfile order speeds up rebuilds?",
     "options": ["Copy all code, then install dependencies",
                 "Run the app first, install later",
                 "Copy the dependency file and install before copying app code",
                 "Install dependencies at container start"], "answer": 2,
     "explain": "The dependency layer stays cached until requirements change."},
    {"topic": "Docker", "q": "Why deploy an image digest instead of a tag?",
     "options": ["Digests are shorter", "Tags cannot be pushed",
                 "Digests are faster to pull",
                 "A digest is immutable, so you deploy exactly the image you scanned"],
     "answer": 3,
     "explain": "Tags can be overwritten. A digest always points to the same image content."},
    {"topic": "Terraform", "q": "What does terraform plan do?",
     "options": ["Shows the changes it would make without applying them",
                 "Creates all resources", "Deletes the state file", "Formats the code"],
     "answer": 0,
     "explain": "plan is a preview. Nothing changes until you run apply."},
    {"topic": "Terraform", "q": "Why use remote state with locking?",
     "options": ["It makes plans faster",
                 "It prevents two runs from corrupting state and lets a team share it",
                 "It hides secrets automatically", "It removes the need for providers"],
     "answer": 1,
     "explain": "Locking blocks concurrent writes, and a shared backend keeps one source of truth."},
    {"topic": "AWS", "q": "What does a security group do?",
     "options": ["Stores access keys", "Encrypts S3 buckets",
                 "Acts as a virtual firewall for inbound and outbound traffic",
                 "Assigns IAM roles"], "answer": 2,
     "explain": "Security groups allow or deny traffic to and from resources like EC2 and ALB."},
    {"topic": "AWS", "q": "Why is OIDC better than stored access keys in CI?",
     "options": ["It is cheaper", "It runs builds faster", "It removes the need for IAM",
                 "It issues short-lived credentials, so nothing long-lived can leak"],
     "answer": 3,
     "explain": "The pipeline gets temporary credentials that expire, so there is no key to steal."},
    {"topic": "CI/CD", "q": "A scan finds a critical vulnerability. What should the pipeline do?",
     "options": ["Fail and block the deploy", "Deploy anyway and email someone",
                 "Skip the scan next time", "Delete the repository"], "answer": 0,
     "explain": "Security gates only work if a failure stops the release."},
    {"topic": "CI/CD", "q": "Why use a concurrency group per pull request?",
     "options": ["To run more jobs in parallel",
                 "So two runs for the same PR do not apply Terraform at the same time",
                 "To cache Docker layers", "To skip tests"], "answer": 1,
     "explain": "It queues runs for the same PR, which avoids racing changes to one environment."},
    {"topic": "Cost", "q": "What mainly costs money if a preview stack runs overnight?",
     "options": ["IAM roles", "Git commits",
                 "The load balancer hourly charge and running Fargate tasks",
                 "Terraform itself"], "answer": 2,
     "explain": "ALBs and Fargate tasks bill by the hour, so forgotten stacks add up."},
]

PRACTICES = [
    {"name": "Version control", "items": [
        {"id": "vc1", "title": "Small, reviewed pull requests",
         "why": "Easier to review and safer to merge."},
        {"id": "vc2", "title": "Branch protection with required checks",
         "why": "Nothing reaches main without passing CI."},
        {"id": "vc3", "title": "No secrets in Git",
         "why": "A leaked key stays in history even after you delete the file."}]},
    {"name": "Continuous integration", "items": [
        {"id": "ci1", "title": "Run tests on every PR", "why": "Catch breakage before merge."},
        {"id": "ci2", "title": "Lint Dockerfiles and infrastructure code",
         "why": "Catches bad practice early and cheaply."},
        {"id": "ci3", "title": "Fail the build on critical findings",
         "why": "A gate that never blocks is just a report."}]},
    {"name": "Infrastructure as code", "items": [
        {"id": "iac1", "title": "All infrastructure in Terraform",
         "why": "Repeatable, reviewable and easy to destroy."},
        {"id": "iac2", "title": "Remote state with locking",
         "why": "Prevents corrupted state from concurrent runs."},
        {"id": "iac3", "title": "Separate shared and per-PR state",
         "why": "A PR destroy can never touch the network or load balancer."},
        {"id": "iac4", "title": "Review the plan before apply",
         "why": "You see exactly what will change."}]},
    {"name": "Containers", "items": [
        {"id": "c1", "title": "Run as a non-root user", "why": "Limits blast radius."},
        {"id": "c2", "title": "Pin base image and dependencies",
         "why": "Builds are repeatable."},
        {"id": "c3", "title": "Deploy by image digest",
         "why": "You ship exactly what you scanned."},
        {"id": "c4", "title": "Add a health check",
         "why": "The platform can tell when the app is unhealthy."}]},
    {"name": "Security", "items": [
        {"id": "s1", "title": "Short-lived credentials with OIDC",
         "why": "No long-lived keys to leak."},
        {"id": "s2", "title": "Least-privilege IAM",
         "why": "A compromised role can do less."},
        {"id": "s3", "title": "Scan images for vulnerabilities",
         "why": "Known issues are found before deploy."},
        {"id": "s4", "title": "No credentials for untrusted fork code",
         "why": "Pull requests from forks cannot reach AWS."}]},
    {"name": "Reliability and observability", "items": [
        {"id": "r1", "title": "A health endpoint", "why": "Load balancers and humans can check it."},
        {"id": "r2", "title": "Central logs", "why": "Debug without logging in to servers."},
        {"id": "r3", "title": "Alarms with notifications",
         "why": "You hear about problems before users do."},
        {"id": "r4", "title": "Automatic cleanup of leftovers",
         "why": "Failed destroys do not become surprise bills."}]},
    {"name": "Cost control", "items": [
        {"id": "k1", "title": "Budget alerts", "why": "Early warning on spend."},
        {"id": "k2", "title": "Destroy temporary environments",
         "why": "You pay only while you use them."},
        {"id": "k3", "title": "Tag every resource", "why": "You can see what costs what."},
        {"id": "k4", "title": "Lifecycle policy for old images",
         "why": "Registry storage does not grow forever."}]},
]


class PrefixMiddleware:
    """Lets the app live under a path like /pr-42 behind the load balancer."""

    def __init__(self, wsgi_app, prefix=""):
        self.wsgi_app = wsgi_app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        if not self.prefix:
            return self.wsgi_app(environ, start_response)
        path = environ.get("PATH_INFO", "")
        if path == self.prefix or path.startswith(self.prefix + "/"):
            environ["SCRIPT_NAME"] = self.prefix
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
            return self.wsgi_app(environ, start_response)
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found"]


def read_num(name, default, maximum):
    raw = request.args.get(name, default)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(name + " must be a number")
    if value < 0:
        raise ValueError(name + " must not be negative")
    if value > maximum:
        raise ValueError(name + " must be at most " + str(maximum))
    return value


PAGE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DevOps Toolkit</title>
<style>
:root{--bg:#f6f7fb;--card:#fff;--text:#1b1f2a;--muted:#5b6475;--accent:#2f6fed;--ok:#1a9d5c;--warn:#d98a00;--bad:#d64545;--border:#e3e6ee}
@media (prefers-color-scheme:dark){:root{--bg:#12141a;--card:#1b1e27;--text:#eceef4;--muted:#9aa3b5;--accent:#6c9bff;--border:#2a2e3a}}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,Segoe UI,Arial,sans-serif;line-height:1.5}
main{max-width:820px;margin:0 auto;padding:24px 16px 48px}
header{display:flex;flex-wrap:wrap;gap:12px;justify-content:space-between;align-items:flex-start;margin-bottom:16px}
h1{margin:0;font-size:1.6rem}
h3{margin:0 0 10px}
.muted{color:var(--muted);margin:2px 0 0}
.badges{display:flex;flex-wrap:wrap;gap:8px}
.badge{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border:1px solid var(--border);border-radius:999px;font-size:.8rem;background:var(--card)}
#dot{width:8px;height:8px;border-radius:50%;background:var(--muted);display:inline-block}
.tabs{display:flex;gap:6px;margin-bottom:14px;flex-wrap:wrap}
.tabs button{padding:8px 16px;border-radius:10px;border:1px solid var(--border);background:var(--card);color:var(--text);cursor:pointer;font-size:.95rem}
.tabs button[aria-selected=true]{background:var(--accent);border-color:var(--accent);color:#fff}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:18px;margin-bottom:16px}
label{display:block;font-weight:600;margin-bottom:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px 20px}
.field output{font-weight:600;color:var(--accent);margin-left:6px}
.field input[type=range]{width:100%;accent-color:var(--accent)}
.field select,.field input[type=number]{width:100%;padding:7px 9px;border:1px solid var(--border);border-radius:8px;background:var(--bg);color:var(--text)}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
button.btn,.actions button,.opt{padding:8px 14px;border-radius:10px;border:1px solid var(--border);background:var(--bg);color:var(--text);cursor:pointer;font-size:.95rem}
.actions .primary{background:var(--accent);border-color:var(--accent);color:#fff}
.result{display:flex;flex-wrap:wrap;gap:20px;align-items:center;justify-content:space-between}
.big{font-size:2.8rem;font-weight:700;line-height:1}
.unit{font-size:1rem;color:var(--muted);margin-left:4px}
.rating{display:inline-block;padding:4px 12px;border-radius:999px;color:#fff;font-weight:600;background:var(--muted)}
.rating[data-level=low]{background:var(--ok)}
.rating[data-level=moderate]{background:var(--warn)}
.rating[data-level=high]{background:var(--bad)}
.bar{display:grid;grid-template-columns:130px 1fr 70px;gap:10px;align-items:center;margin:6px 0;font-size:.9rem}
.bar b{text-align:right}
.track{background:var(--border);border-radius:6px;height:12px;overflow:hidden}
.track i{display:block;height:100%;background:var(--accent);border-radius:6px}
#cmsg{color:var(--bad);min-height:1.2em;margin:8px 0 0}
.chk{display:flex;gap:10px;align-items:flex-start;margin:8px 0;font-weight:400;cursor:pointer}
.chk input{margin-top:5px}
.chk small{display:block;color:var(--muted)}
.progress{background:var(--border);border-radius:8px;height:10px;overflow:hidden;margin:6px 0 16px}
.progress i{display:block;height:100%;width:0;background:var(--ok);transition:width .2s}
.qmeta{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;margin-bottom:10px;color:var(--muted);font-size:.9rem}
.opts{display:grid;gap:8px}
.opt{text-align:left}
.opt.right{background:var(--ok);border-color:var(--ok);color:#fff}
.opt.wrong{background:var(--bad);border-color:var(--bad);color:#fff}
footer{color:var(--muted);font-size:.85rem;margin-top:12px}
a{color:var(--accent)}
@media (max-width:520px){.bar{grid-template-columns:100px 1fr 60px}}
</style>
</head>
<body>
<main id="app"
  data-estimate="{{ url_for('estimate') }}"
  data-quiz="{{ url_for('quiz') }}"
  data-answer="{{ url_for('quiz_answer') }}"
  data-practices="{{ url_for('practices') }}"
  data-health="{{ url_for('health') }}">
  <header>
    <div>
      <h1>DevOps Toolkit</h1>
      <p class="muted">Cost estimator, best practices and a quiz. Live preview build of this pull request.</p>
    </div>
    <div class="badges">
      <span class="badge">prefix: {{ prefix or "none" }}</span>
      <span class="badge">commit: {{ sha }}</span>
      <span class="badge">host: {{ host }}</span>
      <span class="badge"><i id="dot"></i><span id="hs">checking</span></span>
    </div>
  </header>

  <nav class="tabs">
    <button type="button" data-tab="cost" aria-selected="true">Cost estimator</button>
    <button type="button" data-tab="prac" aria-selected="false">DevOps practices</button>
    <button type="button" data-tab="quiz" aria-selected="false">Quiz</button>
  </nav>

  <section class="panel" id="tab-cost">
    <div class="card">
      <h3>Monthly AWS cost estimate</h3>
      <div class="actions" style="margin:0 0 14px">
        <button type="button" class="btn" data-preset="plan">Destroy between sessions</button>
        <button type="button" class="btn" data-preset="always">Always on</button>
        <button type="button" class="btn" data-preset="nat">Always on + NAT</button>
      </div>
      <div class="grid">
        <div class="field"><label for="ec2_type">EC2 instance type</label>
          <select id="ec2_type"><option>t3.micro</option><option selected>t3.small</option><option>t3.medium</option></select></div>
        <div class="field"><label for="ec2_count">EC2 instances</label>
          <input type="number" id="ec2_count" min="0" max="20" value="0"></div>
        <div class="field"><label for="ec2_hours">EC2 hours per month<output id="v_ec2_hours">0</output></label>
          <input type="range" id="ec2_hours" min="0" max="730" step="10" value="0"></div>
        <div class="field"><label for="alb_hours">Load balancer hours<output id="v_alb_hours">40</output></label>
          <input type="range" id="alb_hours" min="0" max="730" step="10" value="40"></div>
        <div class="field"><label for="previews">Preview environments<output id="v_previews">3</output></label>
          <input type="range" id="previews" min="0" max="20" step="1" value="3"></div>
        <div class="field"><label for="preview_hours">Hours each preview runs<output id="v_preview_hours">20</output></label>
          <input type="range" id="preview_hours" min="0" max="730" step="5" value="20"></div>
        <div class="field"><label for="nat_hours">NAT gateway hours<output id="v_nat_hours">0</output></label>
          <input type="range" id="nat_hours" min="0" max="730" step="10" value="0"></div>
        <div class="field"><label for="s3_gb">S3 storage GB<output id="v_s3_gb">1</output></label>
          <input type="range" id="s3_gb" min="0" max="500" step="1" value="1"></div>
        <div class="field"><label for="credits">AWS credits left (USD)</label>
          <input type="number" id="credits" min="0" value="155"></div>
      </div>
    </div>
    <div class="card">
      <div class="result">
        <div><span class="big" id="total">--</span><span class="unit">per month</span></div>
        <div>Credits last <b id="runway">--</b></div>
        <span class="rating" id="crating" data-level="none">calculating</span>
      </div>
      <div id="bars" style="margin-top:14px"></div>
      <p id="cmsg"></p>
    </div>
  </section>

  <section class="panel" id="tab-prac" hidden>
    <div class="card">
      <h3>Practices this project follows</h3>
      <p class="muted" id="pdone">Loading</p>
      <div class="progress"><i id="pfill"></i></div>
      <p class="muted">Tick the ones you have actually applied in your own project.</p>
    </div>
    <div id="prac"></div>
  </section>

  <section class="panel" id="tab-quiz" hidden>
    <div class="card" id="quiz">
      <h3>DevOps quiz</h3>
      <p class="muted">8 random questions on Linux, Git, Docker, Terraform, AWS, CI/CD and cost.</p>
      <div class="actions"><button type="button" class="primary" id="startq">Start quiz</button></div>
    </div>
  </section>

  <footer>Prices are illustrative us-east-1 on-demand estimates. Check AWS pricing before relying on them.
    <a href="{{ url_for('health') }}">/health</a></footer>
</main>

<script>
const root = document.getElementById("app");
const U = {
  estimate: root.dataset.estimate, quiz: root.dataset.quiz,
  answer: root.dataset.answer, practices: root.dataset.practices,
  health: root.dataset.health
};
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

/* ---------- tabs ---------- */
let pracLoaded = false;
document.querySelectorAll(".tabs button").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((x) =>
      x.setAttribute("aria-selected", x === b ? "true" : "false"));
    document.querySelectorAll(".panel").forEach((p) => {
      p.hidden = p.id !== "tab-" + b.dataset.tab;
    });
    if (b.dataset.tab === "prac" && !pracLoaded) loadPractices();
  });
});

/* ---------- cost estimator ---------- */
const costIds = ["ec2_type", "ec2_count", "ec2_hours", "alb_hours", "previews",
  "preview_hours", "nat_hours", "s3_gb", "credits"];
let timer = null;

function showVal(id) {
  const o = $("v_" + id);
  if (o) o.textContent = $(id).value;
}
function schedule() {
  clearTimeout(timer);
  timer = setTimeout(estimate, 150);
}
costIds.forEach((id) => {
  $(id).addEventListener("input", () => { showVal(id); schedule(); });
});

const presets = {
  plan: {ec2_type: "t3.small", ec2_count: 0, ec2_hours: 0, alb_hours: 40,
    previews: 3, preview_hours: 20, nat_hours: 0, s3_gb: 1},
  always: {ec2_type: "t3.small", ec2_count: 1, ec2_hours: 730, alb_hours: 730,
    previews: 3, preview_hours: 730, nat_hours: 0, s3_gb: 1},
  nat: {ec2_type: "t3.small", ec2_count: 1, ec2_hours: 730, alb_hours: 730,
    previews: 3, preview_hours: 730, nat_hours: 730, s3_gb: 1}
};
document.querySelectorAll("[data-preset]").forEach((b) => {
  b.addEventListener("click", () => {
    const p = presets[b.dataset.preset];
    Object.keys(p).forEach((id) => { $(id).value = p[id]; showVal(id); });
    estimate();
  });
});

async function estimate() {
  const q = costIds.map((id) => id + "=" + encodeURIComponent($(id).value)).join("&");
  try {
    const r = await fetch(U.estimate + "?" + q);
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || "Request failed");
    renderCost(d);
  } catch (e) {
    $("cmsg").textContent = e.message;
  }
}

function renderCost(d) {
  $("cmsg").textContent = "";
  $("total").textContent = "$" + d.total.toFixed(2);
  $("runway").textContent = d.runway_months === null ? "n/a" : d.runway_months + " months";
  const max = Math.max(...d.items.map((i) => i.cost), 0.01);
  $("bars").innerHTML = d.items.map((i) =>
    '<div class="bar"><span>' + esc(i.name) + '</span><div class="track"><i style="width:' +
    (i.cost / max * 100) + '%"></i></div><b>$' + i.cost.toFixed(2) + "</b></div>").join("");
  const level = d.total < 20 ? "low" : d.total < 80 ? "moderate" : "high";
  const text = {low: "Low spend", moderate: "Moderate spend", high: "High spend"};
  $("crating").dataset.level = level;
  $("crating").textContent = text[level];
}

/* ---------- practices ---------- */
let pracTotal = 0;
async function loadPractices() {
  try {
    const r = await fetch(U.practices);
    const d = await r.json();
    pracLoaded = true;
    pracTotal = 0;
    $("prac").innerHTML = d.categories.map((c) => {
      const items = c.items.map((it) => {
        pracTotal++;
        return '<label class="chk"><input type="checkbox"><span><b>' + esc(it.title) +
          "</b><small>" + esc(it.why) + "</small></span></label>";
      }).join("");
      return '<div class="card"><h3>' + esc(c.name) + "</h3>" + items + "</div>";
    }).join("");
    $("prac").querySelectorAll("input").forEach((i) => i.addEventListener("change", updateProg));
    updateProg();
  } catch (e) {
    $("pdone").textContent = "Could not load practices.";
  }
}
function updateProg() {
  const done = $("prac").querySelectorAll("input:checked").length;
  $("pdone").textContent = done + " of " + pracTotal + " practices applied";
  $("pfill").style.width = (pracTotal ? done / pracTotal * 100 : 0) + "%";
}

/* ---------- quiz ---------- */
const qs = {list: [], i: 0, score: 0, streak: 0, best: 0, missed: [], locked: false};

async function startQuiz() {
  try {
    const r = await fetch(U.quiz + "?n=8");
    const d = await r.json();
    Object.assign(qs, {list: d.questions, i: 0, score: 0, streak: 0, best: 0, missed: [], locked: false});
    showQ();
  } catch (e) {
    $("quiz").innerHTML = '<p class="muted">Could not load the quiz.</p>';
  }
}
function showQ() {
  const q = qs.list[qs.i];
  qs.locked = false;
  $("quiz").innerHTML =
    '<div class="qmeta"><span class="badge">' + esc(q.topic) + "</span><span>Question " +
    (qs.i + 1) + " of " + qs.list.length + "</span><span>Score " + qs.score +
    " | Streak " + qs.streak + "</span></div><h3>" + esc(q.q) + '</h3><div class="opts">' +
    q.options.map((o, k) => '<button type="button" class="opt" data-k="' + k + '">' + esc(o) + "</button>").join("") +
    '</div><p id="exp" class="muted"></p><div class="actions"><button type="button" class="primary" id="next" hidden>Next</button></div>';
  document.querySelectorAll(".opt").forEach((b) => b.addEventListener("click", () => pick(b)));
}
async function pick(btn) {
  if (qs.locked) return;
  qs.locked = true;
  const q = qs.list[qs.i];
  const k = Number(btn.dataset.k);
  try {
    const r = await fetch(U.answer + "?id=" + q.id + "&choice=" + k);
    const d = await r.json();
    const opts = document.querySelectorAll(".opt");
    opts.forEach((o) => { o.disabled = true; });
    opts[d.answer].classList.add("right");
    if (d.correct) {
      qs.score++; qs.streak++; qs.best = Math.max(qs.best, qs.streak);
    } else {
      btn.classList.add("wrong"); qs.streak = 0; qs.missed.push(q.topic);
    }
    $("exp").textContent = (d.correct ? "Correct. " : "Not quite. ") + d.explain;
    const nx = $("next");
    nx.hidden = false;
    nx.textContent = qs.i + 1 < qs.list.length ? "Next" : "See results";
    nx.addEventListener("click", () => {
      qs.i++;
      if (qs.i < qs.list.length) showQ(); else finish();
    });
  } catch (e) {
    qs.locked = false;
    $("exp").textContent = "Could not check the answer. Try again.";
  }
}
function finish() {
  const pct = Math.round(qs.score / qs.list.length * 100);
  const topics = Array.from(new Set(qs.missed));
  $("quiz").innerHTML = "<h3>" + pct + "% (" + qs.score + " of " + qs.list.length +
    ")</h3><p>Best streak: " + qs.best + '</p><p class="muted">' +
    (topics.length ? "Review: " + topics.map((t) => esc(t)).join(", ") : "No topics to review. Nice work.") +
    '</p><div class="actions"><button type="button" class="primary" id="again">Play again</button></div>';
  $("again").addEventListener("click", startQuiz);
}
$("startq").addEventListener("click", startQuiz);

/* ---------- health ---------- */
async function checkHealth() {
  try {
    const r = await fetch(U.health);
    $("dot").style.background = r.ok ? "var(--ok)" : "var(--bad)";
    $("hs").textContent = r.ok ? "healthy" : "unhealthy";
  } catch (e) {
    $("dot").style.background = "var(--bad)";
    $("hs").textContent = "offline";
  }
}
checkHealth();
setInterval(checkHealth, 10000);
estimate();
</script>
</body>
</html>
"""


def create_app(prefix=None):
    app = Flask(__name__)
    if prefix is None:
        prefix = os.environ.get("APP_PREFIX", "")
    app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix)

    @app.get("/")
    def index():
        return render_template_string(
            PAGE,
            prefix=prefix,
            sha=os.environ.get("GIT_SHA", "local"),
            host=socket.gethostname(),
        )

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/api/estimate")
    def estimate():
        try:
            ec2_type = request.args.get("ec2_type", "t3.small")
            if ec2_type not in PRICES["ec2"]:
                raise ValueError("ec2_type must be one of " + ", ".join(PRICES["ec2"]))
            ec2_count = read_num("ec2_count", 0, 20)
            ec2_hours = read_num("ec2_hours", 0, 744)
            alb_hours = read_num("alb_hours", 0, 744)
            previews = read_num("previews", 0, 50)
            preview_hours = read_num("preview_hours", 0, 744)
            nat_hours = read_num("nat_hours", 0, 744)
            s3_gb = read_num("s3_gb", 0, 10000)
            credits = read_num("credits", 0, 100000)
        except ValueError as err:
            return jsonify(error=str(err)), 400
        per_preview_hour = (
            PREVIEW_VCPU * PRICES["fargate_vcpu_hour"]
            + PREVIEW_GB * PRICES["fargate_gb_hour"]
        )
        items = [
            ("EC2", ec2_count * ec2_hours * PRICES["ec2"][ec2_type]),
            ("Load balancer", alb_hours * PRICES["alb_hour"]),
            ("Fargate previews", previews * preview_hours * per_preview_hour),
            ("NAT gateway", nat_hours * PRICES["nat_hour"]),
            ("S3 storage", s3_gb * PRICES["s3_gb_month"]),
        ]
        total = sum(cost for _, cost in items)
        runway = round(credits / total, 1) if total > 0 and credits > 0 else None
        return jsonify(
            items=[{"name": n, "cost": round(c, 2)} for n, c in items],
            total=round(total, 2),
            runway_months=runway,
        )

    @app.get("/api/practices")
    def practices():
        return jsonify(categories=PRACTICES)

    @app.get("/api/quiz")
    def quiz():
        try:
            n = int(request.args.get("n", 8))
        except ValueError:
            n = 8
        n = max(1, min(n, len(QUESTIONS)))
        picked = random.sample(range(len(QUESTIONS)), n)
        questions = [
            {
                "id": i,
                "topic": QUESTIONS[i]["topic"],
                "q": QUESTIONS[i]["q"],
                "options": QUESTIONS[i]["options"],
            }
            for i in picked
        ]
        return jsonify(questions=questions)

    @app.get("/api/quiz/answer")
    def quiz_answer():
        try:
            qid = int(request.args.get("id", ""))
            choice = int(request.args.get("choice", ""))
        except ValueError:
            return jsonify(error="id and choice must be integers"), 400
        if not 0 <= qid < len(QUESTIONS):
            return jsonify(error="unknown question"), 404
        q = QUESTIONS[qid]
        if not 0 <= choice < len(q["options"]):
            return jsonify(error="choice out of range"), 400
        return jsonify(
            correct=choice == q["answer"], answer=q["answer"], explain=q["explain"]
        )

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
