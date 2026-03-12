#!/usr/bin/env python3
import json
import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Shanghai")
STATE_DIR = Path(os.environ.get("OPENCLAW_STATE_DIR", str(Path.home() / ".openclaw")))
GROUP_ID = os.environ.get("OPENCLAW_GROUP_ID", "oc_replace_with_group_id")
PROJECT_DIR = Path(os.environ.get("OPENCLAW_PROJECT_DIR", str(Path.home() / "ai-agent-guide")))
ASSOCIATION_PATH = Path(__file__).with_name("company-project.json")

CONFIG_PATH = STATE_DIR / "openclaw.json"
CRON_PATH = STATE_DIR / "cron" / "jobs.json"
TEAM_PATH = Path(__file__).with_name("team-status.json")
BUSINESS_METRICS_PATH = Path(__file__).with_name("business-metrics.json")
OUT_PATH = Path(__file__).with_name("dashboard-data.json")

COMPANY_AGENT_IDS = [
    "rd-company",
    "role-product",
    "role-tech-director",
    "role-senior-dev",
    "role-code-reviewer",
    "role-qa-test",
    "role-growth",
]

ROLE_FALLBACK_AGENT = {
    "director": "rd-company",
    "product": "role-product",
    "tech_director": "role-tech-director",
    "senior_dev": "role-senior-dev",
    "code_reviewer": "role-code-reviewer",
    "qa_test": "role-qa-test",
    "growth": "role-growth",
}

OWNER_LABEL_TO_AGENT = {
    "owner:role-senior-dev": "role-senior-dev",
    "owner:role-product": "role-product",
    "owner:role-tech-director": "role-tech-director",
    "owner:role-code-reviewer": "role-code-reviewer",
    "owner:role-qa-test": "role-qa-test",
    "owner:role-growth": "role-growth",
}

PRIORITY_RANK = {
    "priority:p0": 0,
    "priority:p1": 1,
}

STATUS_LABELS = {
    "status:todo",
    "status:doing",
    "status:blocked",
    "status:done",
}

STATUS_RANK = {
    "todo": 0,
    "blocked": 1,
    "doing": 2,
    "done": 3,
}

TIMELINE_WINDOW_HOURS = 24
TIMELINE_WINDOW_MS = TIMELINE_WINDOW_HOURS * 60 * 60 * 1000


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def run_cmd(cmd, cwd: Optional[Path] = None, env: Optional[dict] = None):
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            shell=isinstance(cmd, str),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "code": proc.returncode,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }
    except Exception as e:
        return {"ok": False, "code": -1, "stdout": "", "stderr": str(e)}


def fmt_ms(ms):
    if not ms:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def format_local_datetime(iso_value: Optional[str]):
    if not iso_value:
        return None
    try:
        value = iso_value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        return dt.astimezone(TZ).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def parse_iso_ms(iso_value: Optional[str]):
    if not iso_value:
        return None
    try:
        value = str(iso_value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def resolve_group_binding(bindings):
    for item in bindings:
        match = item.get("match") or {}
        peer = match.get("peer") or {}
        if match.get("channel") == "feishu" and peer.get("kind") == "group" and peer.get("id") == GROUP_ID:
            return item
    return None


def status_level(job):
    if not job.get("enabled"):
        return "paused"
    state = job.get("state") or {}
    if state.get("lastRunStatus") in {"error", "failed"}:
        return "error"
    if state.get("lastDeliveryStatus") in {"failed", "error"}:
        return "warn"
    if (state.get("consecutiveErrors") or 0) > 0:
        return "warn"
    if not state.get("lastRunAtMs"):
        return "pending"
    return "ok"


def parse_repo_slug(remote: Optional[str]):
    if not remote:
        return None
    value = remote.strip()
    if value.startswith("https://github.com/"):
        slug = value[len("https://github.com/") :]
    elif value.startswith("git@github.com:"):
        slug = value[len("git@github.com:") :]
    else:
        return None
    if slug.endswith(".git"):
        slug = slug[:-4]
    return slug or None


def resolve_gh_bin():
    for p in ("/usr/local/bin/gh", "/opt/homebrew/bin/gh", "/usr/bin/gh"):
        if Path(p).exists():
            return p
    return "gh"


def get_config_gh_token(cfg: dict) -> Optional[str]:
    try:
        token = (((cfg.get("skills") or {}).get("entries") or {}).get("gh-issues") or {}).get("apiKey")
    except Exception:
        token = None
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def build_gh_env(cfg: dict):
    env = dict(os.environ)
    for k in ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
        env.pop(k, None)
    token = (env.get("GH_TOKEN") or env.get("GITHUB_TOKEN") or get_config_gh_token(cfg) or "").strip()
    if token:
        env["GH_TOKEN"] = token
        env["GITHUB_TOKEN"] = token
    return env


def build_project_info(project_dir: Path):
    exists = project_dir.exists()
    info = {
        "linked": exists,
        "path": str(project_dir),
        "repoUrl": None,
        "repoSlug": None,
        "branch": None,
        "dirtyFiles": None,
        "lastCommit": {
            "hash": None,
            "time": None,
            "message": None,
        },
    }
    if not exists:
        return info

    remote = run_cmd("git remote get-url origin", cwd=project_dir)
    info["repoUrl"] = remote["stdout"] if remote["ok"] else None
    info["repoSlug"] = parse_repo_slug(info["repoUrl"])

    branch = run_cmd("git branch --show-current", cwd=project_dir)
    info["branch"] = branch["stdout"] if branch["ok"] else None

    dirty = run_cmd("git status --short | wc -l", cwd=project_dir)
    try:
        info["dirtyFiles"] = int(dirty["stdout"]) if dirty["ok"] else None
    except Exception:
        info["dirtyFiles"] = None

    commit = run_cmd("git log -1 --pretty='%h|%ci|%s'", cwd=project_dir)
    if commit["ok"] and commit["stdout"]:
        parts = commit["stdout"].split("|", 2)
        if len(parts) == 3:
            info["lastCommit"] = {
                "hash": parts[0],
                "time": parts[1],
                "message": parts[2],
            }
    return info


def fallback_account_from_hosts():
    hosts = Path.home() / ".config" / "gh" / "hosts.yml"
    if not hosts.exists():
        return None
    try:
        text = hosts.read_text(encoding="utf-8")
    except Exception:
        return None
    m = re.search(r"github\.com:\n((?:[ \t].*\n?)*)", text)
    if not m:
        return None
    block = m.group(1)
    u = re.search(r"^\s*user:\s*([^\s]+)\s*$", block, flags=re.MULTILINE)
    return u.group(1) if u else None


def build_github_auth_info(gh_bin: str, gh_env: dict):
    # Prefer a real API probe because local gh login state can be stale.
    api_res = run_cmd([gh_bin, "api", "user", "--jq", ".login"], env=gh_env)
    if api_res["ok"] and api_res["stdout"]:
        return {
            "ok": True,
            "account": api_res["stdout"].strip(),
            "message": "GitHub API 已连通",
            "raw": "gh api user",
        }

    has_env_token = bool((gh_env.get("GH_TOKEN") or "").strip() or (gh_env.get("GITHUB_TOKEN") or "").strip())
    if has_env_token:
        raw = "\n".join([x for x in (api_res["stdout"], api_res["stderr"]) if x])
        return {
            "ok": False,
            "account": None,
            "message": "GH_TOKEN 无效或无仓库权限",
            "raw": raw,
        }

    result = run_cmd([gh_bin, "auth", "status", "-h", "github.com"], env=gh_env)
    raw = "\n".join([x for x in (result["stdout"], result["stderr"]) if x])
    account = None
    m = re.search(r"account\s+([^\s]+)", raw)
    if m:
        account = m.group(1)

    if "Failed to log in" in raw or "invalid" in raw.lower() or result["code"] != 0:
        fallback_account = fallback_account_from_hosts()
        if fallback_account:
            return {
                "ok": False,
                "account": account or fallback_account,
                "message": "GitHub 已配置但 token 失效",
                "raw": raw,
            }
        return {
            "ok": False,
            "account": account,
            "message": "GitHub token 失效，需要重新登录",
            "raw": raw,
        }

    if "Logged in to github.com" in raw or "Active account" in raw:
        return {
            "ok": True,
            "account": account,
            "message": "GitHub 已登录",
            "raw": raw,
        }

    return {
        "ok": False,
        "account": account,
        "message": "GitHub 状态未知",
        "raw": raw,
    }


def resolve_role_agent_id(role: dict, known_agent_ids: set[str]):
    owner = role.get("owner")
    if owner in known_agent_ids:
        return owner
    rid = role.get("id")
    fallback = ROLE_FALLBACK_AGENT.get(rid)
    if fallback in known_agent_ids:
        return fallback
    return None


def read_agent_activity(agent_workspace: Optional[str]):
    if not agent_workspace:
        return {"sessions": 0, "lastActiveMs": None, "lastActive": None, "latestSessionId": None}

    sessions_path = Path(agent_workspace) / "sessions" / "sessions.json"
    payload = read_json(sessions_path, {})
    if not isinstance(payload, dict):
        return {"sessions": 0, "lastActiveMs": None, "lastActive": None, "latestSessionId": None}

    latest = None
    latest_session_id = None
    for sid, item in payload.items():
        if not isinstance(item, dict):
            continue
        ts = item.get("updatedAt") or item.get("updatedAtMs")
        if isinstance(ts, int):
            if latest is None or ts > latest:
                latest = ts
                latest_session_id = item.get("id") or sid

    return {
        "sessions": len(payload),
        "lastActiveMs": latest,
        "lastActive": fmt_ms(latest),
        "latestSessionId": latest_session_id,
    }


def extract_assistant_text(content):
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    chunks = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and item.get("text"):
            chunks.append(str(item.get("text")).strip())
    return "\n".join([x for x in chunks if x]).strip()


def read_recent_session_note(agent_workspace: Optional[str], session_id: Optional[str]):
    if not agent_workspace or not session_id:
        return None
    path = Path(agent_workspace) / "sessions" / f"{session_id}.jsonl"
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    for raw in reversed(lines[-200:]):
        try:
            row = json.loads(raw)
        except Exception:
            continue
        msg = row.get("message") if isinstance(row, dict) else None
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "assistant":
            continue
        text = extract_assistant_text(msg.get("content"))
        if not text:
            continue
        compact = " ".join(text.split())
        if len(compact) > 96:
            compact = compact[:96].rstrip() + "..."
        return {
            "text": compact,
            "timestamp": row.get("timestamp"),
        }
    return None


def classify_activity(last_active_ms: Optional[int], now_ms: int):
    if not last_active_ms:
        return "no_data"
    delta = now_ms - last_active_ms
    if delta <= 60 * 60 * 1000:
        return "online"
    if delta <= 24 * 60 * 60 * 1000:
        return "recent"
    if delta <= 72 * 60 * 60 * 1000:
        return "idle"
    return "stale"


def role_health(progress_status: Optional[str], blocker_count: int, activity_level: str):
    if progress_status in {"blocked", "error"}:
        return "blocked"
    if blocker_count > 0 or progress_status == "watch":
        return "watch"
    if activity_level in {"stale", "no_data"}:
        return "watch"
    return "healthy"


def compute_progress_stall(
    bucket: Optional[dict],
    activity: dict,
    now_ms: int,
):
    def _to_ms(updated_at: Optional[str]):
        dt = parse_local_time(updated_at)
        if not dt:
            return None
        try:
            return int(dt.timestamp() * 1000)
        except Exception:
            return None

    if bucket and int(bucket.get("total") or 0) > 0:
        open_items = [x for x in (bucket.get("issues") or []) if x.get("state") == "open"]
        latest_ms = None
        for it in open_items:
            ts = _to_ms(it.get("updatedAt"))
            if ts and (latest_ms is None or ts > latest_ms):
                latest_ms = ts
        if latest_ms:
            stale_hours = max(0, int((now_ms - latest_ms) / 3600000))
            todo_only = bool(open_items) and all((x.get("status") or "todo") == "todo" for x in open_items)
            doing = int(bucket.get("doing") or 0)
            blocked = int(bucket.get("blocked") or 0)
            done = int(bucket.get("done") or 0)
            if todo_only and doing == 0 and blocked == 0 and done == 0:
                return {
                    "isStalled": True,
                    "hours": stale_hours,
                    "reason": "负责人事项均为 todo，尚未进入执行（无 doing/done）",
                    "level": "warn",
                    "source": "github-issues",
                }
            if stale_hours >= 12 and todo_only and doing == 0 and blocked == 0:
                return {
                    "isStalled": True,
                    "hours": stale_hours,
                    "reason": f"{stale_hours}h 无 Issue 状态变化（负责人任务仍为 todo）",
                    "level": "warn" if stale_hours < 24 else "err",
                    "source": "github-issues",
                }
        return {"isStalled": False, "hours": 0, "reason": None, "level": "ok", "source": "github-issues"}

    last_active_ms = activity.get("lastActiveMs")
    if isinstance(last_active_ms, int):
        stale_hours = max(0, int((now_ms - last_active_ms) / 3600000))
        if stale_hours >= 24:
            return {
                "isStalled": True,
                "hours": stale_hours,
                "reason": f"{stale_hours}h 无会话活跃，缺少可计算进度证据",
                "level": "warn" if stale_hours < 48 else "err",
                "source": "agent-sessions",
            }
    return {"isStalled": False, "hours": 0, "reason": None, "level": "ok", "source": "agent-sessions"}


def compute_team_milestones(team: dict):
    roles = team.get("roles") or []
    by_role = {r.get("id"): r for r in roles if r.get("id")}
    milestones = team.get("milestones") or []
    today = datetime.now(tz=TZ).strftime("%Y-%m-%d")

    enriched = []
    for m in milestones:
        if not isinstance(m, dict):
            continue
        linked_roles = [rid for rid in (m.get("linkedRoles") or []) if rid in by_role]

        progress_values = []
        for rid in linked_roles:
            role = by_role.get(rid) or {}
            p = (role.get("progress") or {}).get("percent")
            try:
                progress_values.append(int(p))
            except Exception:
                continue

        if progress_values:
            progress = int(sum(progress_values) / len(progress_values))
            progress_source = "computed"
        else:
            try:
                progress = int(m.get("progress") or 0)
            except Exception:
                progress = 0
            progress_source = "manual"

        deadline = m.get("deadline")
        if progress >= 100:
            status = "done"
        elif deadline and deadline < today:
            status = "delayed"
        elif progress > 0:
            status = "in_progress"
        else:
            status = "planned"

        enriched.append(
            {
                "name": m.get("name"),
                "deadline": deadline,
                "owner": m.get("owner"),
                "status": status,
                "progress": progress,
                "linkedRoles": linked_roles,
                "progressSource": progress_source,
                "source": "team-status",
            }
        )

    return enriched


def parse_schedule_due(text: str):
    matches = re.findall(r"(?:截止|Due)[:：]\s*(\d{4}-\d{2}-\d{2})", text, flags=re.IGNORECASE)
    if not matches:
        return None
    return matches[-1]


def get_issue_schedule_due(gh_bin: str, gh_env: dict, repo_slug: str, number: int):
    res = run_cmd(
        [
            gh_bin,
            "issue",
            "view",
            str(number),
            "--repo",
            repo_slug,
            "--json",
            "comments",
            "--jq",
            '[.comments[] | select(.body | startswith("[SCHEDULE]")) | .body] | .[-1] // ""',
        ],
        env=gh_env,
    )
    if not res["ok"] or not res["stdout"]:
        return None
    return parse_schedule_due(res["stdout"])


def parse_issue_status(labels: list[str], state: str):
    if state == "closed":
        return "done"
    status = None
    for label in labels:
        if label in STATUS_LABELS:
            status = label.split(":", 1)[1]
            break
    return status or "todo"


def parse_issue_priority(labels: list[str]):
    for label in labels:
        if label.startswith("priority:"):
            return label
    return None


def issue_sort_key(issue: dict):
    return (PRIORITY_RANK.get(issue.get("priority") or "", 9), issue.get("number") or 999999)


def fetch_github_tracker(repo_slug: Optional[str], gh_bin: str, gh_env: dict):
    empty = {
        "ok": False,
        "repo": repo_slug,
        "issues": [],
        "issueStats": {
            "total": 0,
            "open": 0,
            "closed": 0,
            "todo": 0,
            "doing": 0,
            "blocked": 0,
            "done": 0,
            "overdue": 0,
        },
        "byOwner": {},
        "milestones": [],
        "error": None,
        "source": "none",
    }
    if not repo_slug:
        empty["error"] = "missing repo slug"
        return empty

    issue_res = run_cmd(
        [
            gh_bin,
            "issue",
            "list",
            "--repo",
            repo_slug,
            "--state",
            "all",
            "--limit",
            "100",
            "--json",
            "number,title,state,labels,milestone,assignees,updatedAt,url",
        ],
        env=gh_env,
    )
    if not issue_res["ok"]:
        empty["error"] = issue_res["stderr"] or issue_res["stdout"] or "gh issue list failed"
        return empty

    try:
        raw_issues = json.loads(issue_res["stdout"] or "[]")
    except Exception:
        empty["error"] = "invalid issue json"
        return empty

    today = datetime.now(tz=TZ).strftime("%Y-%m-%d")
    issues = []

    for item in raw_issues:
        if not isinstance(item, dict):
            continue
        number = int(item.get("number") or 0)
        if not number:
            continue

        labels_raw = item.get("labels") or []
        labels = []
        for lbl in labels_raw:
            if isinstance(lbl, dict) and lbl.get("name"):
                labels.append(lbl.get("name"))

        state = str(item.get("state") or "").lower()
        status = parse_issue_status(labels, state)
        priority = parse_issue_priority(labels)
        owner_labels = [x for x in labels if x in OWNER_LABEL_TO_AGENT]
        owners = [OWNER_LABEL_TO_AGENT[x] for x in owner_labels if OWNER_LABEL_TO_AGENT.get(x)]
        if not owners:
            owners = ["rd-company"]

        due = get_issue_schedule_due(gh_bin, gh_env, repo_slug, number) if state == "open" else None
        overdue = bool(due and due < today and state != "closed")

        issues.append(
            {
                "number": number,
                "title": item.get("title"),
                "url": item.get("url"),
                "state": state,
                "status": status,
                "priority": priority,
                "labels": labels,
                "owners": owners,
                "ownerLabels": owner_labels,
                "milestone": ((item.get("milestone") or {}).get("title") if isinstance(item.get("milestone"), dict) else None),
                "assignees": [a.get("login") for a in (item.get("assignees") or []) if isinstance(a, dict) and a.get("login")],
                "updatedAt": format_local_datetime(item.get("updatedAt")),
                "updatedAtMs": parse_iso_ms(item.get("updatedAt")),
                "scheduleDue": due,
                "isOverdue": overdue,
            }
        )

    issues.sort(key=issue_sort_key)

    stats = {
        "total": len(issues),
        "open": sum(1 for x in issues if x["state"] == "open"),
        "closed": sum(1 for x in issues if x["state"] == "closed"),
        "todo": sum(1 for x in issues if x["status"] == "todo"),
        "doing": sum(1 for x in issues if x["status"] == "doing"),
        "blocked": sum(1 for x in issues if x["status"] == "blocked"),
        "done": sum(1 for x in issues if x["status"] == "done"),
        "overdue": sum(1 for x in issues if x["isOverdue"]),
    }

    by_owner = {}
    for aid in COMPANY_AGENT_IDS:
        by_owner[aid] = {
            "total": 0,
            "open": 0,
            "done": 0,
            "todo": 0,
            "doing": 0,
            "blocked": 0,
            "overdue": 0,
            "issues": [],
        }

    for issue in issues:
        for aid in issue["owners"]:
            if aid not in by_owner:
                by_owner[aid] = {
                    "total": 0,
                    "open": 0,
                    "done": 0,
                    "todo": 0,
                    "doing": 0,
                    "blocked": 0,
                    "overdue": 0,
                    "issues": [],
                }
            bucket = by_owner[aid]
            bucket["total"] += 1
            if issue["state"] == "open":
                bucket["open"] += 1
            if issue["status"] == "done":
                bucket["done"] += 1
            elif issue["status"] == "doing":
                bucket["doing"] += 1
            elif issue["status"] == "blocked":
                bucket["blocked"] += 1
            else:
                bucket["todo"] += 1
            if issue["isOverdue"]:
                bucket["overdue"] += 1
            bucket["issues"].append(issue)

    milestone_res = run_cmd([gh_bin, "api", f"repos/{repo_slug}/milestones?state=all&per_page=100"], env=gh_env)
    milestones = []
    if milestone_res["ok"]:
        try:
            raw_milestones = json.loads(milestone_res["stdout"] or "[]")
        except Exception:
            raw_milestones = []
        for m in raw_milestones:
            if not isinstance(m, dict):
                continue
            open_issues = int(m.get("open_issues") or 0)
            closed_issues = int(m.get("closed_issues") or 0)
            total = open_issues + closed_issues
            progress = int((closed_issues * 100) / total) if total > 0 else (100 if m.get("state") == "closed" else 0)
            due_on = m.get("due_on")
            deadline = due_on[:10] if isinstance(due_on, str) and len(due_on) >= 10 else None
            state = str(m.get("state") or "").lower()
            if state == "closed" or progress >= 100:
                milestone_status = "done"
            elif deadline and deadline < today:
                milestone_status = "delayed"
            elif total > 0:
                milestone_status = "in_progress"
            else:
                milestone_status = "planned"

            milestones.append(
                {
                    "name": m.get("title"),
                    "deadline": deadline,
                    "owner": "GitHub",
                    "status": milestone_status,
                    "progress": progress,
                    "progressSource": "github",
                    "source": "github",
                    "openIssues": open_issues,
                    "closedIssues": closed_issues,
                }
            )

    milestones.sort(key=lambda x: (x.get("deadline") or "9999-12-31", x.get("name") or ""))
    return {
        "ok": True,
        "repo": repo_slug,
        "issues": issues,
        "issueStats": stats,
        "byOwner": by_owner,
        "milestones": milestones,
        "error": None,
        "source": "github",
    }


def parse_issue_refs(text: Optional[str]):
    if not text:
        return []
    refs = []
    for token in re.findall(r"#(\d+)", str(text)):
        try:
            num = int(token)
        except Exception:
            continue
        if num > 0:
            refs.append(num)
    out = []
    seen = set()
    for num in refs:
        if num in seen:
            continue
        seen.add(num)
        out.append(num)
    return out


def fetch_github_timeline(repo_slug: Optional[str], gh_bin: str, gh_env: dict):
    empty = {
        "ok": False,
        "repo": repo_slug,
        "prs": [],
        "commits": [],
        "error": "timeline unavailable",
        "source": "none",
    }
    if not repo_slug:
        empty["error"] = "missing repo slug"
        return empty

    errors = []
    prs = []
    commits = []

    prs_res = run_cmd(
        [
            gh_bin,
            "pr",
            "list",
            "--repo",
            repo_slug,
            "--state",
            "all",
            "--limit",
            "100",
            "--json",
            "number,title,state,isDraft,updatedAt,mergedAt,url,body",
        ],
        env=gh_env,
    )
    if prs_res.get("ok"):
        try:
            raw_prs = json.loads(prs_res.get("stdout") or "[]")
        except Exception:
            raw_prs = []
            errors.append("invalid pr list json")
        for pr in raw_prs:
            if not isinstance(pr, dict):
                continue
            number = int(pr.get("number") or 0)
            if number <= 0:
                continue
            body = pr.get("body") or ""
            refs = parse_issue_refs(f"{pr.get('title') or ''}\n{body}")
            prs.append(
                {
                    "number": number,
                    "title": pr.get("title"),
                    "state": str(pr.get("state") or "").lower(),
                    "isDraft": bool(pr.get("isDraft")),
                    "url": pr.get("url"),
                    "issueRefs": refs,
                    "updatedAt": format_local_datetime(pr.get("updatedAt")),
                    "updatedAtMs": parse_iso_ms(pr.get("updatedAt")),
                    "mergedAt": format_local_datetime(pr.get("mergedAt")),
                    "mergedAtMs": parse_iso_ms(pr.get("mergedAt")),
                }
            )
    else:
        errors.append(prs_res.get("stderr") or prs_res.get("stdout") or "gh pr list failed")

    commits_res = run_cmd([gh_bin, "api", f"repos/{repo_slug}/commits?per_page=50"], env=gh_env)
    if commits_res.get("ok"):
        try:
            raw_commits = json.loads(commits_res.get("stdout") or "[]")
        except Exception:
            raw_commits = []
            errors.append("invalid commits json")
        for row in raw_commits:
            if not isinstance(row, dict):
                continue
            sha = str(row.get("sha") or "")[:7]
            commit_obj = row.get("commit") or {}
            if not isinstance(commit_obj, dict):
                continue
            msg = str(commit_obj.get("message") or "").strip()
            first_line = msg.splitlines()[0].strip() if msg else ""
            commit_time = ((commit_obj.get("committer") or {}).get("date")) or ((commit_obj.get("author") or {}).get("date"))
            refs = parse_issue_refs(msg)
            commits.append(
                {
                    "sha": sha,
                    "message": first_line,
                    "url": row.get("html_url"),
                    "author": (row.get("author") or {}).get("login") if isinstance(row.get("author"), dict) else None,
                    "issueRefs": refs,
                    "committedAt": format_local_datetime(commit_time),
                    "committedAtMs": parse_iso_ms(commit_time),
                }
            )
    else:
        errors.append(commits_res.get("stderr") or commits_res.get("stdout") or "gh api commits failed")

    prs.sort(key=lambda x: x.get("updatedAtMs") or 0, reverse=True)
    commits.sort(key=lambda x: x.get("committedAtMs") or 0, reverse=True)

    return {
        "ok": len(errors) == 0,
        "repo": repo_slug,
        "prs": prs[:100],
        "commits": commits[:100],
        "error": " | ".join([e for e in errors if e]) if errors else None,
        "source": "github",
    }


def build_owner_timeline_evidence(github_tracker: dict, issue_deltas: dict, github_timeline: dict):
    now_ms = int(datetime.now(tz=TZ).timestamp() * 1000)
    by_owner = github_tracker.get("byOwner") if github_tracker.get("ok") else {}
    owner_issues = {}
    for aid in COMPANY_AGENT_IDS:
        nums = set()
        bucket = by_owner.get(aid) if isinstance(by_owner, dict) else None
        for it in (bucket or {}).get("issues") or []:
            try:
                n = int(it.get("number") or 0)
            except Exception:
                n = 0
            if n > 0:
                nums.add(n)
        owner_issues[aid] = nums

    def new_evidence():
        return {
            "issueTransitions24h": 0,
            "issueUpdates24h": 0,
            "prEvents24h": 0,
            "commitEvents24h": 0,
            "totalEvents24h": 0,
            "lastEvidenceMs": None,
            "lastEvidenceAt": None,
            "lastEvidenceType": None,
            "noEvidenceHours": None,
            "summary": "",
            "eventHints": [],
        }

    def touch(rec: dict, kind: str, label: Optional[str], ts_ms: Optional[int]):
        if isinstance(ts_ms, int) and ts_ms > 0:
            last = rec.get("lastEvidenceMs")
            if not isinstance(last, int) or ts_ms > last:
                rec["lastEvidenceMs"] = ts_ms
                rec["lastEvidenceType"] = kind
        if label:
            hints = rec.get("eventHints") or []
            if label not in hints and len(hints) < 4:
                hints.append(label)
                rec["eventHints"] = hints

    evidence = {aid: new_evidence() for aid in COMPANY_AGENT_IDS}

    for tr in (issue_deltas or {}).get("statusTransitions") or []:
        if not isinstance(tr, dict):
            continue
        try:
            number = int(tr.get("number") or 0)
        except Exception:
            number = 0
        if number <= 0:
            continue
        ts_ms = None
        dt = parse_local_time(tr.get("updatedAt"))
        if dt:
            ts_ms = int(dt.timestamp() * 1000)

        owners = [x for x in (tr.get("owners") or []) if x in evidence]
        if not owners:
            owners = [aid for aid, nums in owner_issues.items() if number in nums]
        if not owners:
            owners = ["rd-company"]

        for aid in sorted(set(owners)):
            rec = evidence.setdefault(aid, new_evidence())
            if isinstance(ts_ms, int) and (now_ms - ts_ms) <= TIMELINE_WINDOW_MS:
                rec["issueTransitions24h"] += 1
                touch(rec, "issue", f"Issue #{number} {tr.get('from')}→{tr.get('to')}", ts_ms)
            else:
                touch(rec, "issue", None, ts_ms)

    if isinstance(by_owner, dict):
        for aid in COMPANY_AGENT_IDS:
            bucket = by_owner.get(aid) or {}
            for it in (bucket.get("issues") or []):
                if not isinstance(it, dict) or it.get("state") != "open":
                    continue
                ts_ms = None
                dt = parse_local_time(it.get("updatedAt"))
                if dt:
                    ts_ms = int(dt.timestamp() * 1000)
                rec = evidence.setdefault(aid, new_evidence())
                if isinstance(ts_ms, int) and (now_ms - ts_ms) <= TIMELINE_WINDOW_MS:
                    rec["issueUpdates24h"] += 1
                    try:
                        issue_num = int(it.get("number") or 0)
                    except Exception:
                        issue_num = 0
                    label = f"Issue #{issue_num} 更新时间" if issue_num > 0 else "Issue 更新时间"
                    touch(rec, "issue-update", label, ts_ms)
                else:
                    touch(rec, "issue-update", None, ts_ms)

    for pr in (github_timeline or {}).get("prs") or []:
        if not isinstance(pr, dict):
            continue
        refs = set()
        for x in pr.get("issueRefs") or []:
            try:
                n = int(x)
            except Exception:
                n = 0
            if n > 0:
                refs.add(n)
        if not refs:
            continue
        ts_ms = pr.get("mergedAtMs") or pr.get("updatedAtMs")
        owners = [aid for aid, nums in owner_issues.items() if nums.intersection(refs)]
        if not owners:
            owners = ["rd-company"]
        for aid in sorted(set(owners)):
            rec = evidence.setdefault(aid, new_evidence())
            if isinstance(ts_ms, int) and (now_ms - ts_ms) <= TIMELINE_WINDOW_MS:
                rec["prEvents24h"] += 1
                ref_text = ",".join([f"#{n}" for n in sorted(refs)[:2]])
                touch(rec, "pr", f"PR #{pr.get('number')} 关联 {ref_text}", ts_ms)
            else:
                touch(rec, "pr", None, ts_ms)

    for commit in (github_timeline or {}).get("commits") or []:
        if not isinstance(commit, dict):
            continue
        refs = set()
        for x in commit.get("issueRefs") or []:
            try:
                n = int(x)
            except Exception:
                n = 0
            if n > 0:
                refs.add(n)
        ts_ms = commit.get("committedAtMs")
        owners = [aid for aid, nums in owner_issues.items() if refs and nums.intersection(refs)]
        if not owners:
            owners = ["role-senior-dev"] if commit.get("message") else []
        for aid in sorted(set(owners)):
            rec = evidence.setdefault(aid, new_evidence())
            if isinstance(ts_ms, int) and (now_ms - ts_ms) <= TIMELINE_WINDOW_MS:
                rec["commitEvents24h"] += 1
                msg = str(commit.get("message") or "").strip()[:42]
                label = f"Commit {commit.get('sha') or '-'} {msg}".strip()
                touch(rec, "commit", label, ts_ms)
            else:
                touch(rec, "commit", None, ts_ms)

    company_rec = evidence.get("rd-company") or new_evidence()
    for aid in COMPANY_AGENT_IDS:
        if aid == "rd-company":
            continue
        rec = evidence.get(aid) or {}
        company_rec["issueTransitions24h"] += int(rec.get("issueTransitions24h") or 0)
        company_rec["issueUpdates24h"] += int(rec.get("issueUpdates24h") or 0)
        company_rec["prEvents24h"] += int(rec.get("prEvents24h") or 0)
        company_rec["commitEvents24h"] += int(rec.get("commitEvents24h") or 0)
        last_ms = rec.get("lastEvidenceMs")
        if isinstance(last_ms, int):
            curr_last = company_rec.get("lastEvidenceMs")
            if not isinstance(curr_last, int) or last_ms > curr_last:
                company_rec["lastEvidenceMs"] = last_ms
                company_rec["lastEvidenceType"] = rec.get("lastEvidenceType")
        for hint in rec.get("eventHints") or []:
            if hint not in (company_rec.get("eventHints") or []) and len(company_rec.get("eventHints") or []) < 6:
                company_rec.setdefault("eventHints", []).append(hint)
    evidence["rd-company"] = company_rec

    for aid, rec in evidence.items():
        rec["totalEvents24h"] = (
            int(rec.get("issueTransitions24h") or 0)
            + int(rec.get("issueUpdates24h") or 0)
            + int(rec.get("prEvents24h") or 0)
            + int(rec.get("commitEvents24h") or 0)
        )
        last_ms = rec.get("lastEvidenceMs")
        rec["lastEvidenceAt"] = fmt_ms(last_ms) if isinstance(last_ms, int) else None
        if isinstance(last_ms, int):
            rec["noEvidenceHours"] = max(0, int((now_ms - last_ms) / 3600000))
        else:
            rec["noEvidenceHours"] = None
        rec["summary"] = (
            f"24h 证据：Issue迁移 {rec.get('issueTransitions24h') or 0} · "
            f"Issue更新 {rec.get('issueUpdates24h') or 0} · "
            f"PR {rec.get('prEvents24h') or 0} · Commit {rec.get('commitEvents24h') or 0}"
        )

    return evidence


def build_issue_boards(github_tracker: dict, panel: list[dict]):
    if not github_tracker.get("ok") or not github_tracker.get("issues"):
        blockers_board = []
        risks_board = []
        for p in panel:
            if p.get("blockerCount", 0) > 0:
                target = blockers_board if p.get("health") == "blocked" else risks_board
                target.append({"agentId": p["id"], "name": p["name"], "items": p.get("blockers") or []})
        return blockers_board, risks_board, "team-status"

    name_by_agent = {x.get("id"): x.get("name") for x in panel}
    blockers_map = defaultdict(list)
    risks_map = defaultdict(list)

    for issue in github_tracker.get("issues") or []:
        if issue.get("state") != "open":
            continue
        base = f"#{issue.get('number')} {issue.get('title')}"
        if issue.get("scheduleDue"):
            base = f"{base} · 截止 {issue.get('scheduleDue')}"
        if issue.get("updatedAt"):
            base = f"{base} · 更新 {issue.get('updatedAt')}"

        if issue.get("status") == "blocked" or issue.get("isOverdue"):
            suffix = "（阻塞）" if issue.get("status") == "blocked" else "（已超期）"
            for aid in issue.get("owners") or ["rd-company"]:
                blockers_map[aid].append(f"{base} {suffix}")
        elif issue.get("priority") in {"priority:p0", "priority:p1"}:
            suffix = "（高优先级）" if issue.get("priority") == "priority:p0" else "（待推进）"
            for aid in issue.get("owners") or ["rd-company"]:
                risks_map[aid].append(f"{base} {suffix}")

    blockers_board = []
    for aid, items in blockers_map.items():
        blockers_board.append(
            {
                "agentId": aid,
                "name": name_by_agent.get(aid) or aid,
                "items": sorted(set(items)),
            }
        )

    risks_board = []
    for aid, items in risks_map.items():
        risks_board.append(
            {
                "agentId": aid,
                "name": name_by_agent.get(aid) or aid,
                "items": sorted(set(items)),
            }
        )

    blockers_board.sort(key=lambda x: (-len(x.get("items") or []), x.get("name") or ""))
    risks_board.sort(key=lambda x: (-len(x.get("items") or []), x.get("name") or ""))
    return blockers_board, risks_board, "github"


def build_agent_panel(cfg: dict, team: dict, github_tracker: dict, owner_evidence: Optional[dict] = None):
    now_ms = int(datetime.now(tz=TZ).timestamp() * 1000)

    agents = (cfg.get("agents") or {}).get("list") or []
    agents_by_id = {a.get("id"): a for a in agents if a.get("id")}
    known_ids = set(agents_by_id.keys())

    roles = team.get("roles") or []
    role_by_agent = {}
    for role in roles:
        aid = resolve_role_agent_id(role, known_ids)
        if aid:
            role_by_agent[aid] = role

    by_owner = github_tracker.get("byOwner") if github_tracker.get("ok") else {}
    issue_stats = github_tracker.get("issueStats") or {}
    all_issues = github_tracker.get("issues") or []

    panel = []
    for aid in COMPANY_AGENT_IDS:
        agent = agents_by_id.get(aid) or {}
        role = role_by_agent.get(aid) or {}
        evidence = (owner_evidence or {}).get(aid) if isinstance(owner_evidence, dict) else {}
        if not isinstance(evidence, dict):
            evidence = {}

        activity = read_agent_activity(agent.get("workspace"))
        activity_level = classify_activity(activity.get("lastActiveMs"), now_ms)
        recent_note = read_recent_session_note(agent.get("workspace"), activity.get("latestSessionId"))

        if activity_level == "online":
            progress_status = "on_track"
            progress_percent = 30
        elif activity_level == "recent":
            progress_status = "on_track"
            progress_percent = 20
        elif activity_level == "idle":
            progress_status = "watch"
            progress_percent = 10
        else:
            progress_status = "watch"
            progress_percent = 0

        progress_summary = f"实时会话 {int(activity.get('sessions') or 0)} · 最近活跃 {activity.get('lastActive') or '暂无'}"
        today_items = [f"最近输出：{recent_note.get('text')}"] if isinstance(recent_note, dict) and recent_note.get("text") else []
        blocker_items = []
        manual_today = list(role.get("today") or [])
        manual_blockers = list(role.get("blockers") or [])
        progress_manual = role.get("progress") or {}

        bucket = by_owner.get(aid) if isinstance(by_owner, dict) else None
        if aid == "rd-company" and github_tracker.get("ok") and issue_stats.get("total", 0) > 0:
            total = int(issue_stats.get("total") or 0)
            done = int(issue_stats.get("done") or 0)
            doing = int(issue_stats.get("doing") or 0)
            blocked = int(issue_stats.get("blocked") or 0)
            todo = int(issue_stats.get("todo") or 0)
            overdue = int(issue_stats.get("overdue") or 0)
            progress_percent = int(((done + 0.5 * doing) * 100) / total) if total > 0 else 0
            if total > 0 and done == total:
                progress_percent = 100
            elif doing > 0 and progress_percent < 10:
                progress_percent = 10
            if blocked > 0:
                progress_status = "blocked"
            elif doing > 0:
                progress_status = "on_track"
            elif todo > 0:
                progress_status = "watch"
            else:
                progress_status = "done"
            progress_summary = f"GitHub 总览：done {done}/{total} · todo {todo} · doing {doing} · blocked {blocked}"
            open_sorted = [x for x in all_issues if x.get("state") == "open"]
            open_sorted.sort(key=issue_sort_key)
            today_items = [f"#{x.get('number')} {x.get('title')}" for x in open_sorted[:2]]
            blocker_items = [
                f"#{x.get('number')} {x.get('title')}"
                for x in open_sorted
                if x.get("status") == "blocked" or x.get("isOverdue")
            ]
            if overdue > 0:
                blocker_items = blocker_items[:2] + [f"超期事项 {overdue} 项"]
        elif bucket and bucket.get("total", 0) > 0:
            total = int(bucket.get("total") or 0)
            done = int(bucket.get("done") or 0)
            doing = int(bucket.get("doing") or 0)
            blocked = int(bucket.get("blocked") or 0)
            todo = int(bucket.get("todo") or 0)
            progress_percent = int(((done + 0.5 * doing) * 100) / total) if total > 0 else 0
            if total > 0 and done == total:
                progress_percent = 100
            elif doing > 0 and progress_percent < 10:
                progress_percent = 10
            if blocked > 0:
                progress_status = "blocked"
            elif doing > 0:
                progress_status = "on_track"
            elif todo > 0:
                progress_status = "watch"
            else:
                progress_status = "done"
            progress_summary = f"GitHub：done {done}/{total} · todo {todo} · doing {doing} · blocked {blocked}"

            open_issues = [x for x in (bucket.get("issues") or []) if x.get("state") == "open"]
            open_issues.sort(key=issue_sort_key)
            if open_issues:
                today_items = [f"#{x.get('number')} {x.get('title')}" for x in open_issues[:2]]
            blocker_items = [
                f"#{x.get('number')} {x.get('title')}"
                for x in open_issues
                if x.get("status") == "blocked" or x.get("isOverdue")
            ]
        else:
            if not today_items and manual_today:
                today_items = [f"手动维护：{x}" for x in manual_today[:2]]
            if manual_blockers:
                blocker_items = [f"手动维护：{x}" for x in manual_blockers[:3]]
            if manual_blockers:
                progress_status = "watch"
            if progress_manual.get("summary"):
                progress_summary = f"{progress_summary} · 计划备注：{progress_manual.get('summary')}"

        stall = compute_progress_stall(bucket, activity, now_ms)
        strict_target = github_tracker.get("ok") and (aid == "rd-company" or (bucket and int(bucket.get("total") or 0) > 0))
        timeline_events = int(evidence.get("totalEvents24h") or 0)
        if strict_target and timeline_events <= 0:
            no_evidence_hours = evidence.get("noEvidenceHours")
            stall = {
                "isStalled": True,
                "hours": no_evidence_hours if isinstance(no_evidence_hours, int) else TIMELINE_WINDOW_HOURS,
                "reason": f"近{TIMELINE_WINDOW_HOURS}h 无 Issue 迁移 / PR / Commit 证据，进度按冻结处理",
                "level": "warn" if (not isinstance(no_evidence_hours, int) or no_evidence_hours < 48) else "err",
                "source": "github-timeline-strict",
            }
            if progress_status != "blocked":
                progress_status = "watch"
            progress_summary = f"{progress_summary} · 进度冻结：近{TIMELINE_WINDOW_HOURS}h无Issue迁移/PR/Commit"
            if not today_items:
                today_items = ["暂无可验证输出（需提交 PR / 更新 Issue 状态）"]
            if not blocker_items:
                blocker_items = ["缺少可追踪时间线证据（Issue迁移/PR/Commit）"]
        evidence_summary = evidence.get("summary") if evidence.get("summary") else stall.get("source")
        if evidence.get("lastEvidenceAt"):
            evidence_summary = f"{evidence_summary} · 最近证据 {evidence.get('lastEvidenceAt')}"

        blocker_count = len(blocker_items)
        panel.append(
            {
                "id": aid,
                "name": role.get("name") or agent.get("name") or aid,
                "agentName": agent.get("name") or aid,
                "workspace": agent.get("workspace"),
                "owner": role.get("owner") or aid,
                "focus": role.get("focus"),
                "progress": {
                    "percent": progress_percent,
                    "status": progress_status,
                    "summary": progress_summary,
                },
                "today": today_items,
                "dailyRoutine": role.get("daily_routine") or [],
                "blockers": blocker_items,
                "blockerCount": blocker_count,
                "sessions": activity.get("sessions") or 0,
                "lastActive": activity.get("lastActive"),
                "lastActiveMs": activity.get("lastActiveMs"),
                "activityLevel": activity_level,
                "recentNote": recent_note.get("text") if isinstance(recent_note, dict) else None,
                "progressStalled": stall.get("isStalled"),
                "progressStallHours": stall.get("hours"),
                "progressStallReason": stall.get("reason"),
                "progressStallLevel": stall.get("level"),
                "progressEvidence": evidence_summary,
                "health": role_health(progress_status, blocker_count, activity_level),
                "hasWorkspace": bool(agent.get("workspace")),
            }
        )

    active_agents = sum(1 for p in panel if p["activityLevel"] in {"online", "recent"})
    blocked_agents = sum(1 for p in panel if p["health"] == "blocked")
    avg_progress = int(sum(p["progress"]["percent"] for p in panel) / len(panel)) if panel else 0
    return {
        "agents": panel,
        "stats": {
            "totalAgents": len(panel),
            "activeAgents": active_agents,
            "blockedAgents": blocked_agents,
            "avgProgress": avg_progress,
        },
    }


def parse_launchd_status(label: str):
    cmd = f"uid=$(id -u); launchctl print gui/${{uid}}/{label}"
    res = run_cmd(cmd)
    if not res["ok"]:
        return {
            "enabled": False,
            "level": "error",
            "state": "not_loaded",
            "runs": None,
            "lastExitCode": None,
            "intervalSec": None,
        }
    text = "\n".join([res.get("stdout") or "", res.get("stderr") or ""])
    state_match = re.search(r"state = ([^\n]+)", text)
    runs_match = re.search(r"runs = (\d+)", text)
    exit_match = re.search(r"last exit code = (\d+)", text)
    interval_match = re.search(r"run interval = (\d+) seconds", text)
    state = state_match.group(1).strip() if state_match else "unknown"
    runs = int(runs_match.group(1)) if runs_match else None
    last_exit = int(exit_match.group(1)) if exit_match else None
    interval_sec = int(interval_match.group(1)) if interval_match else None

    if last_exit not in {None, 0}:
        level = "error"
    elif state == "running":
        level = "ok"
    elif runs in {None, 0}:
        level = "pending"
    else:
        level = "ok"

    return {
        "enabled": True,
        "level": level,
        "state": state,
        "runs": runs,
        "lastExitCode": last_exit,
        "intervalSec": interval_sec,
    }


def build_local_jobs():
    specs = [
        ("launchd-ai.openclaw.issue-sync", "Issue 同步纠偏", "system", "ai.openclaw.issue-sync"),
        ("launchd-ai.openclaw.rd-dashboard-refresh", "驾驶舱数据刷新", "system", "ai.openclaw.rd-dashboard-refresh"),
        ("launchd-ai.openclaw.gateway-watchdog", "网关稳定守护", "system", "ai.openclaw.gateway-watchdog"),
    ]
    rows = []
    for jid, name, agent_id, launchd_label in specs:
        st = parse_launchd_status(launchd_label)
        schedule = f"every {st['intervalSec']}s" if st.get("intervalSec") else "launchd"
        rows.append(
            {
                "id": jid,
                "name": name,
                "agentId": agent_id,
                "enabled": st.get("enabled", False),
                "schedule": schedule,
                "timezone": "local",
                "nextRun": "由 launchd 调度",
                "lastRun": None,
                "lastRunStatus": f"runs={st.get('runs') if st.get('runs') is not None else '-'}",
                "lastDeliveryStatus": f"state={st.get('state')}",
                "consecutiveErrors": 0 if st.get("lastExitCode") in {None, 0} else 1,
                "level": st.get("level") or "warn",
                "kind": "launchd",
            }
        )
    return rows


def parse_local_time(text: Optional[str]):
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=TZ)
        except Exception:
            continue
    return None


def file_mtime(path: Path):
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=TZ).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def to_float(value, default: float = 0.0):
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        return float(value)
    except Exception:
        return default


def clamp_value(value: float, min_value: float, max_value: float):
    return max(min_value, min(max_value, value))


def read_business_metrics():
    payload = read_json(BUSINESS_METRICS_PATH, None)
    if not isinstance(payload, dict):
        return {
            "isReal": False,
            "source": "proxy",
            "period": None,
            "updatedAt": None,
            "currency": "CNY",
            "leads": 0,
            "trialUsers": 0,
            "paidUsers": 0,
            "revenue": 0.0,
            "refundAmount": 0.0,
            "netRevenue": 0.0,
            "arpu": 0.0,
            "cac": 0.0,
            "cashInDays": 0.0,
            "leadToTrialRate": 0.0,
            "trialToPaidRate": 0.0,
            "leadToPaidRate": 0.0,
            "refundRate": 0.0,
            "notes": "未配置 business-metrics.json，当前为代理估算。",
        }

    leads = max(0, int(to_float(payload.get("leads"))))
    trial_users = max(0, int(to_float(payload.get("trialUsers"))))
    paid_users = max(0, int(to_float(payload.get("paidUsers"))))
    revenue = round(max(0.0, to_float(payload.get("revenue"))), 2)
    refund_amount = round(max(0.0, to_float(payload.get("refundAmount"))), 2)
    net_revenue = round(revenue - refund_amount, 2)

    # When explicit ARPU/CAC are absent, compute from available funnel values.
    arpu_raw = payload.get("arpu")
    cac_raw = payload.get("cac")
    arpu = round(to_float(arpu_raw), 2) if arpu_raw is not None else round((revenue / paid_users), 2) if paid_users > 0 else 0.0
    cac = round(to_float(cac_raw), 2) if cac_raw is not None else round((revenue / leads), 2) if leads > 0 else 0.0
    cash_in_days = round(max(0.0, to_float(payload.get("cashInDays"))), 1)

    lead_to_trial_rate = round((trial_users * 100 / leads), 2) if leads > 0 else 0.0
    trial_to_paid_rate = round((paid_users * 100 / trial_users), 2) if trial_users > 0 else 0.0
    lead_to_paid_rate = round((paid_users * 100 / leads), 2) if leads > 0 else 0.0
    refund_rate = round((refund_amount * 100 / revenue), 2) if revenue > 0 else 0.0

    period = str(payload.get("period") or "").strip() or None
    updated_at = str(payload.get("updatedAt") or "").strip() or file_mtime(BUSINESS_METRICS_PATH)
    currency = str(payload.get("currency") or "CNY").strip().upper()
    notes = str(payload.get("notes") or "").strip() or "经营数据已接入 business-metrics.json。"

    return {
        "isReal": True,
        "source": "business-metrics.json",
        "period": period,
        "updatedAt": updated_at,
        "currency": currency,
        "leads": leads,
        "trialUsers": trial_users,
        "paidUsers": paid_users,
        "revenue": revenue,
        "refundAmount": refund_amount,
        "netRevenue": net_revenue,
        "arpu": arpu,
        "cac": cac,
        "cashInDays": cash_in_days,
        "leadToTrialRate": clamp_value(lead_to_trial_rate, 0.0, 100.0),
        "trialToPaidRate": clamp_value(trial_to_paid_rate, 0.0, 100.0),
        "leadToPaidRate": clamp_value(lead_to_paid_rate, 0.0, 100.0),
        "refundRate": clamp_value(refund_rate, 0.0, 100.0),
        "notes": notes,
    }


def build_issue_deltas(current_issues: list[dict], previous_snapshot: dict):
    prev_issues = ((previous_snapshot or {}).get("github") or {}).get("issues") or []
    prev_map = {str(x.get("number")): x for x in prev_issues if isinstance(x, dict)}
    curr_map = {str(x.get("number")): x for x in current_issues if isinstance(x, dict)}

    new_open = 0
    newly_closed = 0
    status_changed = 0
    due_changed = 0
    promotions = 0
    regressions = []
    transitions = []

    for num, issue in curr_map.items():
        prev = prev_map.get(num)
        if not prev:
            if issue.get("state") == "open":
                new_open += 1
            continue
        if prev.get("state") != "closed" and issue.get("state") == "closed":
            newly_closed += 1
        if prev.get("status") != issue.get("status"):
            status_changed += 1
            prev_status = str(prev.get("status") or "todo")
            next_status = str(issue.get("status") or "todo")
            owners = issue.get("owners") or prev.get("owners") or []
            owner_text = ",".join([str(x) for x in owners if x]) or "-"
            transition = {
                "number": issue.get("number"),
                "title": issue.get("title") or prev.get("title") or "",
                "url": issue.get("url") or prev.get("url"),
                "owners": owners,
                "owner": owner_text,
                "priority": issue.get("priority") or prev.get("priority"),
                "from": prev_status,
                "to": next_status,
                "updatedAt": issue.get("updatedAt") or prev.get("updatedAt"),
            }
            transitions.append(transition)

            prev_rank = STATUS_RANK.get(prev_status, -1)
            next_rank = STATUS_RANK.get(next_status, -1)
            if next_rank > prev_rank:
                promotions += 1
            elif next_rank < prev_rank:
                severity = "high" if (prev_status in {"doing", "done"} and next_status == "todo") else "medium"
                regressions.append({**transition, "severity": severity})
        if (prev.get("scheduleDue") or "") != (issue.get("scheduleDue") or ""):
            due_changed += 1

    regressions.sort(key=lambda x: (0 if x.get("severity") == "high" else 1, x.get("number") or 999999))
    transitions.sort(key=lambda x: x.get("number") or 999999)
    hard_regression_count = sum(1 for x in regressions if x.get("severity") == "high")

    return {
        "newOpen": new_open,
        "newlyClosed": newly_closed,
        "statusChanged": status_changed,
        "dueChanged": due_changed,
        "promotions": promotions,
        "regressionCount": len(regressions),
        "hardRegressionCount": hard_regression_count,
        "regressions": regressions[:10],
        "statusTransitions": transitions[:20],
    }


def clean_radar_line(raw: str):
    line = (raw or "").strip()
    if not line:
        return ""
    if set(line) <= set("-|: "):
        return ""
    if line.count("|") >= 3:
        return ""
    line = line.replace("**", "")
    line = re.sub(r"^[#>\-\*\s]+", "", line).strip()
    line = re.sub(r"\s+", " ", line)
    return line


def read_latest_radar_brief():
    queue_dir = STATE_DIR / "delivery-queue"
    if not queue_dir.exists():
        return None

    try:
        files = sorted(queue_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:120]
    except Exception:
        return None

    for path in files:
        payload = read_json(path, {})
        if not isinstance(payload, dict):
            continue
        if payload.get("to") != GROUP_ID:
            continue
        if payload.get("accountId") and payload.get("accountId") != "hot-search":
            continue

        text = None
        for item in payload.get("payloads") or []:
            if isinstance(item, dict) and item.get("text"):
                text = str(item.get("text"))
                break
        if not text:
            mirror = payload.get("mirror") or {}
            if isinstance(mirror, dict) and mirror.get("text"):
                text = str(mirror.get("text"))
        if not text:
            continue
        if "简报" not in text and "情报" not in text:
            continue

        lines = []
        for raw in text.splitlines():
            line = clean_radar_line(raw)
            if not line:
                continue
            lines.append(line)
        if not lines:
            continue

        title = lines[0][:80]
        highlights = []
        for line in lines[1:]:
            if len(highlights) >= 6:
                break
            low = line.lower()
            if "简报生成时间" in line or "下次更新" in line or "项目：" in line or "周期" in line:
                continue
            if "序号" in line and "标题" in line:
                continue
            if low.startswith("http://") or low.startswith("https://"):
                continue
            highlights.append(line[:120])

        return {
            "title": title,
            "highlights": highlights,
            "generatedAt": file_mtime(path),
            "sourceFile": path.name,
        }
    return None


def build_activity_feed(group_jobs: list[dict], local_jobs: list[dict], github_tracker: dict, panel: list[dict]):
    events = []

    for j in group_jobs:
        ts = j.get("lastRunAtMs")
        if not ts:
            continue
        status = j.get("lastRunStatus") or "unknown"
        delivery = j.get("lastDeliveryStatus") or "unknown"
        if status in {"error", "failed"}:
            level = "err"
        elif delivery in {"failed", "error", "unknown"}:
            level = "warn"
        else:
            level = "ok"
        events.append(
            {
                "tsMs": ts,
                "time": fmt_ms(ts),
                "type": "cron",
                "level": level,
                "title": f"调度：{j.get('name')}",
                "detail": f"运行={status} · 投递={delivery}",
            }
        )

    for j in local_jobs:
        events.append(
            {
                "tsMs": int(datetime.now(tz=TZ).timestamp() * 1000),
                "time": datetime.now(tz=TZ).strftime("%Y-%m-%d %H:%M"),
                "type": "service",
                "level": "ok" if j.get("level") == "ok" else "warn",
                "title": f"服务：{j.get('name')}",
                "detail": f"{j.get('lastRunStatus')} · {j.get('lastDeliveryStatus')}",
            }
        )

    for issue in (github_tracker.get("issues") or [])[:8]:
        dt = parse_local_time(issue.get("updatedAt"))
        if not dt:
            continue
        if issue.get("status") == "blocked" or issue.get("isOverdue"):
            level = "err"
        elif issue.get("priority") == "priority:p0":
            level = "warn"
        else:
            level = "ok"
        events.append(
            {
                "tsMs": int(dt.timestamp() * 1000),
                "time": issue.get("updatedAt"),
                "type": "issue",
                "level": level,
                "title": f"Issue #{issue.get('number')} · {issue.get('status')}",
                "detail": issue.get("title"),
            }
        )

    for agent in panel:
        ts = agent.get("lastActiveMs")
        if not ts:
            continue
        detail = agent.get("recentNote") or f"会话 {agent.get('sessions') or 0} 个"
        events.append(
            {
                "tsMs": ts,
                "time": agent.get("lastActive"),
                "type": "agent",
                "level": "ok" if agent.get("activityLevel") in {"online", "recent"} else "warn",
                "title": f"{agent.get('name')} 最近活跃",
                "detail": detail,
            }
        )

    events.sort(key=lambda x: x.get("tsMs") or 0, reverse=True)
    return events[:24]


def build():
    cfg = read_json(CONFIG_PATH, {})
    cron = read_json(CRON_PATH, {})
    team = read_json(TEAM_PATH, {})
    association = read_json(ASSOCIATION_PATH, {})
    previous_snapshot = read_json(OUT_PATH, {})

    bindings = cfg.get("bindings") or []
    binding = resolve_group_binding(bindings)
    route_agent = binding.get("agentId") if binding else None

    jobs = cron.get("jobs") or []
    group_jobs = []
    for j in jobs:
        delivery = j.get("delivery") or {}
        if delivery.get("to") == GROUP_ID:
            state = j.get("state") or {}
            group_jobs.append(
                {
                    "id": j.get("id"),
                    "name": j.get("name"),
                    "agentId": j.get("agentId"),
                    "enabled": bool(j.get("enabled")),
                    "schedule": (j.get("schedule") or {}).get("expr"),
                    "timezone": (j.get("schedule") or {}).get("tz") or "local",
                    "nextRun": fmt_ms(state.get("nextRunAtMs")),
                    "lastRun": fmt_ms(state.get("lastRunAtMs")),
                    "nextRunAtMs": state.get("nextRunAtMs"),
                    "lastRunAtMs": state.get("lastRunAtMs"),
                    "lastRunStatus": state.get("lastRunStatus"),
                    "lastDeliveryStatus": state.get("lastDeliveryStatus"),
                    "consecutiveErrors": state.get("consecutiveErrors") or 0,
                    "level": status_level(j),
                    "kind": "openclaw-cron",
                }
            )

    local_jobs = build_local_jobs()
    all_jobs = list(group_jobs) + local_jobs
    enabled_jobs = sum(1 for j in group_jobs if j["enabled"])
    error_jobs = sum(1 for j in all_jobs if j["level"] == "error")
    warn_jobs = sum(1 for j in all_jobs if j["level"] == "warn")

    configured_project_path = association.get("projectPath") or str(PROJECT_DIR)
    project = build_project_info(Path(configured_project_path).expanduser())

    gh_bin = resolve_gh_bin()
    gh_env = build_gh_env(cfg)
    github_auth = build_github_auth_info(gh_bin, gh_env)
    repo_slug = project.get("repoSlug") or association.get("projectRepo")
    github_tracker = fetch_github_tracker(repo_slug, gh_bin, gh_env) if github_auth.get("ok") else {
        "ok": False,
        "repo": repo_slug,
        "issues": [],
        "issueStats": {
            "total": 0,
            "open": 0,
            "closed": 0,
            "todo": 0,
            "doing": 0,
            "blocked": 0,
            "done": 0,
            "overdue": 0,
        },
        "byOwner": {},
        "milestones": [],
        "error": "github auth unavailable",
        "source": "none",
    }

    issue_deltas = build_issue_deltas(github_tracker.get("issues") or [], previous_snapshot)
    github_timeline = fetch_github_timeline(repo_slug, gh_bin, gh_env) if github_tracker.get("ok") else {
        "ok": False,
        "repo": repo_slug,
        "prs": [],
        "commits": [],
        "error": "github timeline unavailable",
        "source": "none",
    }
    owner_evidence = build_owner_timeline_evidence(github_tracker, issue_deltas, github_timeline)
    company = build_agent_panel(cfg, team, github_tracker, owner_evidence)
    blockers_board, risks_board, blockers_source = build_issue_boards(github_tracker, company.get("agents") or [])
    milestones = github_tracker.get("milestones") if github_tracker.get("milestones") else compute_team_milestones(team)
    milestones_source = "github" if github_tracker.get("milestones") else "team-status"
    activity_feed = build_activity_feed(group_jobs, local_jobs, github_tracker, company.get("agents") or [])
    business_radar = read_latest_radar_brief()
    business_metrics = read_business_metrics()
    freshness = {
        "config": file_mtime(CONFIG_PATH),
        "cron": file_mtime(CRON_PATH),
        "teamStatus": file_mtime(TEAM_PATH),
        "association": file_mtime(ASSOCIATION_PATH),
        "businessMetrics": file_mtime(BUSINESS_METRICS_PATH),
    }

    data = {
        "generatedAt": datetime.now(tz=TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "Asia/Shanghai",
        "group": {
            "id": GROUP_ID,
            "routeAgent": route_agent,
            "bindingFound": bool(binding),
        },
        "overview": {
            "enabledJobs": enabled_jobs,
            "errorJobs": error_jobs,
            "warnJobs": warn_jobs,
            "allGroupJobs": len(group_jobs),
            "allJobs": len(all_jobs),
        },
        "project": project,
        "association": {
            "companyName": association.get("companyName") or "AI 转职一人公司",
            "projectPath": project.get("path"),
            "projectRepo": association.get("projectRepo") or project.get("repoSlug") or project.get("repoUrl"),
            "linkedAgents": association.get("linkedAgents") or COMPANY_AGENT_IDS,
            "updatedAt": association.get("updatedAt"),
        },
        "githubAuth": github_auth,
        "github": {
            "repo": repo_slug,
            "ok": github_tracker.get("ok"),
            "error": github_tracker.get("error"),
            "issueStats": github_tracker.get("issueStats") or {},
            "issues": github_tracker.get("issues") or [],
            "timeline": {
                "ok": github_timeline.get("ok"),
                "error": github_timeline.get("error"),
                "prCount": len(github_timeline.get("prs") or []),
                "commitCount": len(github_timeline.get("commits") or []),
            },
        },
        "company": {
            "name": association.get("companyName") or "AI 转职一人公司",
            "projectLinked": bool(project.get("linked")),
            "linkedProjectPath": project.get("path"),
            "linkedRepo": association.get("projectRepo") or project.get("repoSlug") or project.get("repoUrl"),
            "stats": company.get("stats") or {},
        },
        "agentPanel": company.get("agents") or [],
        "blockersBoard": blockers_board,
        "risksBoard": risks_board,
        "roles": team.get("roles") or [],
        "milestones": milestones,
        "activityFeed": activity_feed,
        "deltas": {
            "issues": issue_deltas,
        },
        "businessRadar": business_radar,
        "businessMetrics": business_metrics,
        "freshness": freshness,
        "cronJobs": sorted(all_jobs, key=lambda x: (x.get("kind") != "openclaw-cron", x.get("name") or "")),
        "dataSources": {
            "agentPanel": "github-issues+timeline-strict" if github_tracker.get("ok") else "session+team-status",
            "blockers": blockers_source,
            "milestones": milestones_source,
            "cronJobs": "openclaw-cron+launchd",
            "activityFeed": "cron+github+agent-sessions",
            "issueDeltas": "snapshot-diff",
            "businessRadar": "delivery-queue",
            "businessMetrics": "business-metrics.json" if business_metrics.get("isReal") else "proxy-estimation",
        },
    }

    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    build()
