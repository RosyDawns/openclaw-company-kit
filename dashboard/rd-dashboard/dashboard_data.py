#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence
from zoneinfo import ZoneInfo


def read_env_int(name: str, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None):
    raw = os.environ.get(name)
    try:
        value = int(str(raw).strip()) if raw is not None else int(default)
    except Exception:
        value = int(default)
    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


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
CONTROL_TASK_HISTORY_PATH = STATE_DIR / "run" / "control-task-history.jsonl"
DASHBOARD_CACHE_DIR = STATE_DIR / "run" / "dashboard-cache"

GITHUB_TRACKER_CACHE_TTL_SEC = read_env_int("OPENCLAW_GITHUB_TRACKER_CACHE_TTL_SEC", 300, minimum=60, maximum=3600)
GITHUB_ISSUE_SCHEDULE_CACHE_TTL_SEC = read_env_int(
    "OPENCLAW_GITHUB_ISSUE_SCHEDULE_CACHE_TTL_SEC", 600, minimum=120, maximum=14400
)
GITHUB_ISSUE_EVIDENCE_CACHE_TTL_SEC = read_env_int(
    "OPENCLAW_GITHUB_ISSUE_EVIDENCE_CACHE_TTL_SEC", 1800, minimum=120, maximum=43200
)
GITHUB_API_BUDGET_LIMIT = read_env_int("OPENCLAW_GITHUB_API_BUDGET", 80, minimum=10, maximum=500)
DASHBOARD_DATA_SLA_MINUTES = read_env_int("DASHBOARD_DATA_SLA_MINUTES", 15, minimum=3, maximum=240)

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


def run_cmd(cmd: Sequence[str] | str, cwd: Optional[Path] = None, env: Optional[dict] = None):
    try:
        argv = shlex.split(cmd) if isinstance(cmd, str) else [str(part) for part in cmd]
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            shell=False,
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


def now_ms():
    return int(datetime.now(tz=TZ).timestamp() * 1000)


def repo_cache_path(prefix: str, repo_slug: Optional[str]):
    slug = (repo_slug or "unknown").strip().lower() or "unknown"
    safe_slug = re.sub(r"[^a-z0-9._-]+", "_", slug)
    return DASHBOARD_CACHE_DIR / f"{prefix}-{safe_slug}.json"


def read_json_cache(path: Path):
    raw = read_json(path, {})
    if not isinstance(raw, dict):
        return None
    payload = raw.get("data")
    if not isinstance(payload, dict):
        return None
    try:
        generated_at_ms = int(raw.get("generatedAtMs") or 0)
    except Exception:
        generated_at_ms = 0
    age_sec = None
    if generated_at_ms > 0:
        age_sec = max(0, int((now_ms() - generated_at_ms) / 1000))
    return {
        "generatedAtMs": generated_at_ms,
        "ageSec": age_sec,
        "data": payload,
    }


def write_json_cache(path: Path, payload: dict):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "generatedAtMs": now_ms(),
            "data": payload,
        }
        path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    except Exception:
        return


def read_fresh_cache(path: Path, ttl_sec: int):
    cached = read_json_cache(path)
    if not cached:
        return None
    age_sec = cached.get("ageSec")
    if not isinstance(age_sec, int) or age_sec > int(ttl_sec):
        return None
    return cached


def new_github_api_budget(limit: Optional[int] = None):
    bounded = int(limit if isinstance(limit, int) else GITHUB_API_BUDGET_LIMIT)
    if bounded < 1:
        bounded = 1
    return {"limit": bounded, "used": 0, "degraded": False, "skipped": 0}


def consume_api_budget(api_budget: Optional[dict], cost: int = 1):
    if not isinstance(api_budget, dict):
        return True
    try:
        limit = int(api_budget.get("limit") or 0)
    except Exception:
        limit = 0
    try:
        used = int(api_budget.get("used") or 0)
    except Exception:
        used = 0
    amount = max(1, int(cost))
    if used + amount > limit:
        api_budget["degraded"] = True
        api_budget["skipped"] = int(api_budget.get("skipped") or 0) + amount
        return False
    api_budget["used"] = used + amount
    return True


def run_gh_cmd(cmd: Sequence[str], gh_env: dict, api_budget: Optional[dict] = None, budget_tag: str = "github"):
    if not consume_api_budget(api_budget, 1):
        return {"ok": False, "code": -2, "stdout": "", "stderr": f"github api budget exceeded ({budget_tag})"}
    return run_cmd(cmd, env=gh_env)


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

    remote = run_cmd(["git", "remote", "get-url", "origin"], cwd=project_dir)
    info["repoUrl"] = remote["stdout"] if remote["ok"] else None
    info["repoSlug"] = parse_repo_slug(info["repoUrl"])

    branch = run_cmd(["git", "branch", "--show-current"], cwd=project_dir)
    info["branch"] = branch["stdout"] if branch["ok"] else None

    dirty = run_cmd(["git", "status", "--short"], cwd=project_dir)
    try:
        if dirty["ok"]:
            rows = [line for line in dirty["stdout"].splitlines() if line.strip()]
            info["dirtyFiles"] = len(rows)
        else:
            info["dirtyFiles"] = None
    except Exception:
        info["dirtyFiles"] = None

    commit = run_cmd(["git", "log", "-1", "--pretty=%h|%ci|%s"], cwd=project_dir)
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


def parse_auto_status_comment_body(text: Optional[str]):
    body = str(text or "")
    marker_match = re.search(r"^\[AUTO-STATUS\]\s*([^\n]+)", body, flags=re.MULTILINE)
    transition_match = re.search(r"^- Transition:\s*(.+)$", body, flags=re.MULTILINE)
    reason_match = re.search(r"^- Reason:\s*(.+)$", body, flags=re.MULTILINE)
    evidence_match = re.search(r"^- Evidence:\s*(.+)$", body, flags=re.MULTILINE)
    evidence_type_match = re.search(r"^- EvidenceType:\s*(.+)$", body, flags=re.MULTILINE)
    evidence_url_match = re.search(r"^- EvidenceURL:\s*(.+)$", body, flags=re.MULTILINE)
    issue_url_match = re.search(r"^- IssueURL:\s*(.+)$", body, flags=re.MULTILINE)
    synced_at_match = re.search(r"^- SyncedAt:\s*(.+)$", body, flags=re.MULTILINE)

    parsed = {
        "marker": (marker_match.group(1).strip() if marker_match else None),
        "transition": (transition_match.group(1).strip() if transition_match else None),
        "reason": (reason_match.group(1).strip() if reason_match else None),
        "evidenceText": (evidence_match.group(1).strip() if evidence_match else None),
        "evidenceType": (evidence_type_match.group(1).strip() if evidence_type_match else None),
        "evidenceUrl": (evidence_url_match.group(1).strip() if evidence_url_match else None),
        "issueUrl": (issue_url_match.group(1).strip() if issue_url_match else None),
        "syncedAt": (synced_at_match.group(1).strip() if synced_at_match else None),
    }

    json_match = re.search(r"^\[AUTO-EVIDENCE\]\s*(\{.*\})\s*$", body, flags=re.MULTILINE)
    if json_match:
        try:
            payload = json.loads(json_match.group(1))
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            if not parsed.get("evidenceType") and payload.get("evidenceType"):
                parsed["evidenceType"] = str(payload.get("evidenceType"))
            if not parsed.get("evidenceUrl") and payload.get("evidenceUrl"):
                parsed["evidenceUrl"] = str(payload.get("evidenceUrl"))
            if not parsed.get("issueUrl") and payload.get("issueUrl"):
                parsed["issueUrl"] = str(payload.get("issueUrl"))
            if not parsed.get("syncedAt") and payload.get("syncedAt"):
                parsed["syncedAt"] = str(payload.get("syncedAt"))
    return parsed


def get_issue_status_comment(gh_bin: str, gh_env: dict, repo_slug: str, number: int, api_budget: Optional[dict] = None):
    res = run_gh_cmd(
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
            '[.comments[] | select(.body | startswith("[AUTO-STATUS]")) | {url,createdAt,body}] | .[-1] // {}',
        ],
        gh_env,
        api_budget=api_budget,
        budget_tag="issue-evidence-comment",
    )
    if not res["ok"]:
        return {"ok": False, "comment": None, "budgetExceeded": int(res.get("code") or 0) == -2}

    parsed = {}
    if res.get("stdout"):
        try:
            parsed = json.loads(res.get("stdout") or "{}")
        except Exception:
            parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    created_iso = parsed.get("createdAt") if isinstance(parsed.get("createdAt"), str) else None
    created_at_ms = parse_iso_ms(created_iso)
    created_at = format_local_datetime(created_iso)
    body = parsed.get("body") if isinstance(parsed.get("body"), str) else ""
    fields = parse_auto_status_comment_body(body)
    summary = fields.get("transition") or fields.get("reason") or fields.get("evidenceText")
    comment = {
        "url": parsed.get("url") if isinstance(parsed.get("url"), str) and parsed.get("url") else None,
        "createdAt": created_at,
        "createdAtMs": created_at_ms,
        "marker": fields.get("marker"),
        "transition": fields.get("transition"),
        "reason": fields.get("reason"),
        "summary": summary,
        "evidenceType": fields.get("evidenceType"),
        "evidenceUrl": fields.get("evidenceUrl"),
        "issueUrl": fields.get("issueUrl"),
        "syncedAt": fields.get("syncedAt"),
    }
    has_signal = bool(comment.get("marker") or comment.get("summary") or comment.get("url"))
    return {"ok": True, "comment": (comment if has_signal else None), "budgetExceeded": False}


def resolve_issue_status_comment_map(
    issues: list[dict], repo_slug: str, gh_bin: str, gh_env: dict, api_budget: Optional[dict] = None
):
    cache_path = repo_cache_path("github-issue-status-evidence", repo_slug)
    cached = read_json_cache(cache_path)
    cached_issues = {}
    if cached and isinstance(cached.get("data"), dict):
        cached_issues = (cached.get("data") or {}).get("issues") or {}
    if not isinstance(cached_issues, dict):
        cached_issues = {}

    current_ms = now_ms()
    ttl_ms = GITHUB_ISSUE_EVIDENCE_CACHE_TTL_SEC * 1000
    comment_by_issue = {}
    refreshed = 0
    cache_hits = 0
    stale_hits = 0
    budget_skips = 0
    budget_exhausted = False
    active_done_keys = set()

    for issue in issues:
        if not isinstance(issue, dict):
            continue
        if str(issue.get("status") or "") != "done":
            continue
        try:
            number = int(issue.get("number") or 0)
        except Exception:
            number = 0
        if number <= 0:
            continue

        key = str(number)
        active_done_keys.add(key)
        updated_at = str(issue.get("updatedAt") or "")
        status = str(issue.get("status") or "")
        entry = cached_issues.get(key) if isinstance(cached_issues.get(key), dict) else {}
        cached_comment = entry.get("comment") if isinstance(entry.get("comment"), dict) else None
        cached_updated_at = str(entry.get("updatedAt") or "")
        cached_status = str(entry.get("status") or "")
        try:
            cached_at_ms = int(entry.get("cachedAtMs") or 0)
        except Exception:
            cached_at_ms = 0

        is_fresh = (
            cached_at_ms > 0
            and cached_updated_at == updated_at
            and cached_status == status
            and (current_ms - cached_at_ms) <= ttl_ms
        )
        if is_fresh:
            if cached_comment:
                comment_by_issue[number] = cached_comment
            cache_hits += 1
            continue

        if budget_exhausted:
            if key in cached_issues:
                stale_hits += 1
            if cached_comment:
                comment_by_issue[number] = cached_comment
            budget_skips += 1
            continue

        comment_res = get_issue_status_comment(gh_bin, gh_env, repo_slug, number, api_budget=api_budget)
        if comment_res.get("budgetExceeded"):
            budget_exhausted = True
            if key in cached_issues:
                stale_hits += 1
            if cached_comment:
                comment_by_issue[number] = cached_comment
            budget_skips += 1
            continue

        comment_value = comment_res.get("comment") if isinstance(comment_res.get("comment"), dict) else None
        if comment_value:
            comment_by_issue[number] = comment_value
        refreshed += 1
        cached_issues[key] = {
            "updatedAt": updated_at,
            "status": status,
            "comment": comment_value,
            "cachedAtMs": current_ms,
        }

    keep_after_ms = current_ms - (14 * 24 * 3600 * 1000)
    compacted = {}
    for key, row in cached_issues.items():
        if not isinstance(row, dict):
            continue
        try:
            cached_at_ms = int(row.get("cachedAtMs") or 0)
        except Exception:
            cached_at_ms = 0
        if key in active_done_keys or (cached_at_ms > 0 and cached_at_ms >= keep_after_ms):
            compacted[key] = row

    write_json_cache(cache_path, {"issues": compacted})
    return {
        "commentByIssue": comment_by_issue,
        "cacheHits": cache_hits,
        "staleHits": stale_hits,
        "refreshed": refreshed,
        "budgetSkips": budget_skips,
    }


def get_issue_schedule_due(gh_bin: str, gh_env: dict, repo_slug: str, number: int, api_budget: Optional[dict] = None):
    res = run_gh_cmd(
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
        gh_env,
        api_budget=api_budget,
        budget_tag="issue-schedule",
    )
    if not res["ok"]:
        return {"ok": False, "due": None, "budgetExceeded": int(res.get("code") or 0) == -2}
    due = parse_schedule_due(res["stdout"]) if res.get("stdout") else None
    return {"ok": True, "due": due, "budgetExceeded": False}


def resolve_issue_schedule_due_map(
    raw_issues: list[dict], repo_slug: str, gh_bin: str, gh_env: dict, api_budget: Optional[dict] = None
):
    cache_path = repo_cache_path("github-issue-schedule", repo_slug)
    cached = read_json_cache(cache_path)
    cached_issues = {}
    if cached and isinstance(cached.get("data"), dict):
        cached_issues = (cached.get("data") or {}).get("issues") or {}
    if not isinstance(cached_issues, dict):
        cached_issues = {}

    current_ms = now_ms()
    ttl_ms = GITHUB_ISSUE_SCHEDULE_CACHE_TTL_SEC * 1000
    due_by_issue = {}
    refreshed = 0
    cache_hits = 0
    stale_hits = 0
    budget_skips = 0
    budget_exhausted = False
    active_open_keys = set()

    for item in raw_issues:
        if not isinstance(item, dict):
            continue
        if str(item.get("state") or "").lower() != "open":
            continue
        try:
            number = int(item.get("number") or 0)
        except Exception:
            number = 0
        if number <= 0:
            continue

        key = str(number)
        active_open_keys.add(key)
        updated_at = str(item.get("updatedAt") or "")
        entry = cached_issues.get(key) if isinstance(cached_issues.get(key), dict) else {}
        cached_due = entry.get("due")
        cached_updated_at = str(entry.get("updatedAt") or "")
        try:
            cached_at_ms = int(entry.get("cachedAtMs") or 0)
        except Exception:
            cached_at_ms = 0

        if cached_due and not isinstance(cached_due, str):
            cached_due = None

        is_fresh = (
            cached_at_ms > 0
            and cached_updated_at == updated_at
            and (current_ms - cached_at_ms) <= ttl_ms
        )
        if is_fresh:
            due_by_issue[number] = cached_due
            cache_hits += 1
            continue

        if budget_exhausted:
            if key in cached_issues:
                stale_hits += 1
            due_by_issue[number] = cached_due
            budget_skips += 1
            continue

        due_res = get_issue_schedule_due(gh_bin, gh_env, repo_slug, number, api_budget=api_budget)
        if due_res.get("budgetExceeded"):
            budget_exhausted = True
            if key in cached_issues:
                stale_hits += 1
            due_by_issue[number] = cached_due
            budget_skips += 1
            continue

        due_value = due_res.get("due")
        if due_value and not isinstance(due_value, str):
            due_value = None
        due_by_issue[number] = due_value
        refreshed += 1
        cached_issues[key] = {
            "updatedAt": updated_at,
            "due": due_value,
            "cachedAtMs": current_ms,
        }

    # Keep current open issues + recent entries (7 days) to avoid unlimited growth.
    keep_after_ms = current_ms - (7 * 24 * 3600 * 1000)
    compacted = {}
    for key, row in cached_issues.items():
        if not isinstance(row, dict):
            continue
        try:
            cached_at_ms = int(row.get("cachedAtMs") or 0)
        except Exception:
            cached_at_ms = 0
        if key in active_open_keys or (cached_at_ms > 0 and cached_at_ms >= keep_after_ms):
            compacted[key] = row

    write_json_cache(cache_path, {"issues": compacted})
    return {
        "dueByIssue": due_by_issue,
        "cacheHits": cache_hits,
        "staleHits": stale_hits,
        "refreshed": refreshed,
        "budgetSkips": budget_skips,
    }


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


def fetch_github_tracker(repo_slug: Optional[str], gh_bin: str, gh_env: dict, api_budget: Optional[dict] = None):
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
        "cache": {},
    }
    if not repo_slug:
        empty["error"] = "missing repo slug"
        return empty

    tracker_cache_path = repo_cache_path("github-tracker", repo_slug)
    fresh_cache = read_fresh_cache(tracker_cache_path, GITHUB_TRACKER_CACHE_TTL_SEC)
    if fresh_cache and isinstance(fresh_cache.get("data"), dict):
        payload = dict(fresh_cache.get("data") or {})
        cache_meta = dict(payload.get("cache") or {})
        cache_meta.update(
            {
                "trackerCacheHit": True,
                "trackerCacheAgeSec": fresh_cache.get("ageSec"),
                "trackerCacheTtlSec": GITHUB_TRACKER_CACHE_TTL_SEC,
            }
        )
        payload["cache"] = cache_meta
        payload["source"] = "github-cache"
        payload["error"] = payload.get("error")
        return payload

    stale_cache = read_json_cache(tracker_cache_path)
    issue_res = run_gh_cmd(
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
        gh_env,
        api_budget=api_budget,
        budget_tag="issue-list",
    )
    if not issue_res["ok"]:
        if int(issue_res.get("code") or 0) == -2 and stale_cache and isinstance(stale_cache.get("data"), dict):
            payload = dict(stale_cache.get("data") or {})
            cache_meta = dict(payload.get("cache") or {})
            cache_meta.update(
                {
                    "trackerCacheHit": True,
                    "trackerCacheAgeSec": stale_cache.get("ageSec"),
                    "trackerCacheTtlSec": GITHUB_TRACKER_CACHE_TTL_SEC,
                    "trackerStaleFallback": True,
                }
            )
            payload["cache"] = cache_meta
            payload["source"] = "github-cache-stale"
            payload["error"] = None
            return payload
        empty["error"] = issue_res["stderr"] or issue_res["stdout"] or "gh issue list failed"
        return empty

    try:
        raw_issues = json.loads(issue_res["stdout"] or "[]")
    except Exception:
        empty["error"] = "invalid issue json"
        return empty

    schedule_meta = resolve_issue_schedule_due_map(raw_issues, repo_slug, gh_bin, gh_env, api_budget=api_budget)
    due_by_issue = schedule_meta.get("dueByIssue") or {}
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

        due = due_by_issue.get(number) if state == "open" else None
        if due and not isinstance(due, str):
            due = None
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
                "statusComment": None,
            }
        )

    issues.sort(key=issue_sort_key)
    evidence_meta = resolve_issue_status_comment_map(issues, repo_slug, gh_bin, gh_env, api_budget=api_budget)
    comment_by_issue = evidence_meta.get("commentByIssue") or {}
    for issue in issues:
        try:
            num = int(issue.get("number") or 0)
        except Exception:
            num = 0
        if num > 0 and isinstance(comment_by_issue.get(num), dict):
            issue["statusComment"] = comment_by_issue.get(num)

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

    milestone_res = run_gh_cmd(
        [gh_bin, "api", f"repos/{repo_slug}/milestones?state=all&per_page=100"],
        gh_env,
        api_budget=api_budget,
        budget_tag="milestones",
    )
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
    result = {
        "ok": True,
        "repo": repo_slug,
        "issues": issues,
        "issueStats": stats,
        "byOwner": by_owner,
        "milestones": milestones,
        "error": None,
        "source": "github",
        "cache": {
            "trackerCacheHit": False,
            "trackerCacheTtlSec": GITHUB_TRACKER_CACHE_TTL_SEC,
            "scheduleCacheTtlSec": GITHUB_ISSUE_SCHEDULE_CACHE_TTL_SEC,
            "scheduleCacheHits": int(schedule_meta.get("cacheHits") or 0),
            "scheduleStaleHits": int(schedule_meta.get("staleHits") or 0),
            "scheduleRefreshed": int(schedule_meta.get("refreshed") or 0),
            "scheduleBudgetSkips": int(schedule_meta.get("budgetSkips") or 0),
            "evidenceCacheTtlSec": GITHUB_ISSUE_EVIDENCE_CACHE_TTL_SEC,
            "evidenceCacheHits": int(evidence_meta.get("cacheHits") or 0),
            "evidenceStaleHits": int(evidence_meta.get("staleHits") or 0),
            "evidenceRefreshed": int(evidence_meta.get("refreshed") or 0),
            "evidenceBudgetSkips": int(evidence_meta.get("budgetSkips") or 0),
        },
    }
    write_json_cache(tracker_cache_path, result)
    return result


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


def fetch_github_timeline(repo_slug: Optional[str], gh_bin: str, gh_env: dict, api_budget: Optional[dict] = None):
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

    prs_res = run_gh_cmd(
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
        gh_env,
        api_budget=api_budget,
        budget_tag="pr-list",
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

    commits_res = run_gh_cmd(
        [gh_bin, "api", f"repos/{repo_slug}/commits?per_page=50"],
        gh_env,
        api_budget=api_budget,
        budget_tag="commits",
    )
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


def build_role_evidence_chains(github_tracker: dict, issue_deltas: dict, github_timeline: dict):
    issues = github_tracker.get("issues") or []
    issue_map = {}
    owner_issue_nums = {aid: set() for aid in COMPANY_AGENT_IDS}
    events_by_issue = defaultdict(list)
    dedupe_by_issue = defaultdict(set)

    def add_event(issue_num: int, event: dict):
        if issue_num <= 0 or not isinstance(event, dict):
            return
        url = event.get("url")
        if not isinstance(url, str) or not url.strip():
            return
        at_ms = event.get("atMs")
        if not isinstance(at_ms, int):
            at_ms = parse_iso_ms(event.get("at")) or None
        at_text = event.get("at")
        if not isinstance(at_text, str) or not at_text.strip():
            at_text = fmt_ms(at_ms) if isinstance(at_ms, int) else None
        if at_text and not isinstance(at_ms, int):
            dt = parse_local_time(at_text)
            if dt:
                at_ms = int(dt.timestamp() * 1000)
        key = (
            str(event.get("type") or ""),
            str(url),
            str(at_text or ""),
            str(event.get("summary") or ""),
        )
        seen = dedupe_by_issue.setdefault(issue_num, set())
        if key in seen:
            return
        seen.add(key)
        row = {
            "issueNumber": issue_num,
            "issueTitle": event.get("issueTitle") or "",
            "type": event.get("type") or "issue",
            "url": url,
            "at": at_text,
            "atMs": at_ms,
            "summary": event.get("summary") or "",
        }
        events_by_issue.setdefault(issue_num, []).append(row)

    for issue in issues:
        if not isinstance(issue, dict):
            continue
        try:
            number = int(issue.get("number") or 0)
        except Exception:
            number = 0
        if number <= 0:
            continue
        issue_map[number] = issue
        owners = [x for x in (issue.get("owners") or []) if x in owner_issue_nums]
        if not owners:
            owners = ["rd-company"]
        for aid in owners:
            owner_issue_nums.setdefault(aid, set()).add(number)
        owner_issue_nums.setdefault("rd-company", set()).add(number)

        title = str(issue.get("title") or "")
        add_event(
            number,
            {
                "issueTitle": title,
                "type": "issue",
                "url": issue.get("url"),
                "at": issue.get("updatedAt"),
                "atMs": issue.get("updatedAtMs"),
                "summary": f"Issue #{number} · {issue.get('status') or '-'} · {title}".strip(" ·"),
            },
        )

        status_comment = issue.get("statusComment")
        if isinstance(status_comment, dict):
            comment_url = status_comment.get("url") or status_comment.get("evidenceUrl") or issue.get("url")
            comment_at = status_comment.get("createdAt") or status_comment.get("syncedAt")
            comment_ms = status_comment.get("createdAtMs")
            summary = status_comment.get("transition") or status_comment.get("summary") or status_comment.get("reason")
            marker = status_comment.get("marker")
            if marker and summary:
                summary = f"{marker} · {summary}"
            elif marker:
                summary = marker
            add_event(
                number,
                {
                    "issueTitle": title,
                    "type": "comment",
                    "url": comment_url,
                    "at": comment_at,
                    "atMs": comment_ms,
                    "summary": summary or f"Issue #{number} 状态评论",
                },
            )

    for pr in (github_timeline or {}).get("prs") or []:
        if not isinstance(pr, dict):
            continue
        refs = set()
        for item in pr.get("issueRefs") or []:
            try:
                num = int(item)
            except Exception:
                num = 0
            if num > 0 and num in issue_map:
                refs.add(num)
        if not refs:
            continue
        pr_no = int(pr.get("number") or 0)
        title = str(pr.get("title") or "").strip()
        pr_state = str(pr.get("state") or "").strip().lower()
        for num in refs:
            add_event(
                num,
                {
                    "issueTitle": issue_map.get(num, {}).get("title") or "",
                    "type": "pr",
                    "url": pr.get("url"),
                    "at": pr.get("mergedAt") or pr.get("updatedAt"),
                    "atMs": pr.get("mergedAtMs") or pr.get("updatedAtMs"),
                    "summary": f"PR #{pr_no} ({pr_state or '-'}) · {title}".strip(" ·"),
                },
            )

    for commit in (github_timeline or {}).get("commits") or []:
        if not isinstance(commit, dict):
            continue
        refs = set()
        for item in commit.get("issueRefs") or []:
            try:
                num = int(item)
            except Exception:
                num = 0
            if num > 0 and num in issue_map:
                refs.add(num)
        if not refs:
            continue
        sha = str(commit.get("sha") or "-")
        msg = str(commit.get("message") or "").strip()
        for num in refs:
            add_event(
                num,
                {
                    "issueTitle": issue_map.get(num, {}).get("title") or "",
                    "type": "commit",
                    "url": commit.get("url"),
                    "at": commit.get("committedAt"),
                    "atMs": commit.get("committedAtMs"),
                    "summary": f"Commit {sha} · {msg}".strip(" ·"),
                },
            )

    for tr in (issue_deltas or {}).get("statusTransitions") or []:
        if not isinstance(tr, dict):
            continue
        try:
            number = int(tr.get("number") or 0)
        except Exception:
            number = 0
        if number <= 0 or number not in issue_map:
            continue
        issue = issue_map.get(number) or {}
        add_event(
            number,
            {
                "issueTitle": issue.get("title") or "",
                "type": "comment",
                "url": issue.get("url"),
                "at": tr.get("updatedAt"),
                "summary": f"状态变更 {tr.get('from') or '-'} -> {tr.get('to') or '-'}",
            },
        )

    chains = {}
    for aid in COMPANY_AGENT_IDS:
        nums = owner_issue_nums.get(aid) or set()
        if aid == "rd-company":
            nums = set(issue_map.keys())
        rows = []
        for num in nums:
            rows.extend(events_by_issue.get(num) or [])
        rows.sort(key=lambda x: ((x.get("atMs") or 0), x.get("issueNumber") or 0), reverse=True)
        rows = rows[:24]
        stats = {
            "total": len(rows),
            "issue": sum(1 for x in rows if x.get("type") == "issue"),
            "pr": sum(1 for x in rows if x.get("type") == "pr"),
            "commit": sum(1 for x in rows if x.get("type") == "commit"),
            "comment": sum(1 for x in rows if x.get("type") == "comment"),
        }
        chains[aid] = {"items": rows, "stats": stats}
    return chains


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


def build_agent_panel(
    cfg: dict,
    team: dict,
    github_tracker: dict,
    owner_evidence: Optional[dict] = None,
    role_evidence_chains: Optional[dict] = None,
):
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
        chain_payload = (role_evidence_chains or {}).get(aid) if isinstance(role_evidence_chains, dict) else {}
        if not isinstance(chain_payload, dict):
            chain_payload = {}
        evidence_chain = chain_payload.get("items") if isinstance(chain_payload.get("items"), list) else []
        evidence_stats = chain_payload.get("stats") if isinstance(chain_payload.get("stats"), dict) else {}

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
                "evidenceChain": evidence_chain,
                "evidenceStats": {
                    "total": int(evidence_stats.get("total") or len(evidence_chain)),
                    "issue": int(evidence_stats.get("issue") or 0),
                    "pr": int(evidence_stats.get("pr") or 0),
                    "commit": int(evidence_stats.get("commit") or 0),
                    "comment": int(evidence_stats.get("comment") or 0),
                },
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
    cmd = ["launchctl", "print", f"gui/{os.getuid()}/{label}"]
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


def read_control_task_metrics(path: Optional[Path] = None, window_days: int = 7):
    target = path or CONTROL_TASK_HISTORY_PATH
    window_days = max(1, int(window_days))
    now_dt = datetime.now(tz=TZ)
    start_day = (now_dt - timedelta(days=window_days - 1)).date()

    day_keys = [(start_day + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(window_days)]
    day_map = {
        day: {"day": day, "total": 0, "success": 0, "failed": 0, "_durationSum": 0.0, "_durationCount": 0}
        for day in day_keys
    }

    summary = {
        "windowDays": window_days,
        "total": 0,
        "success": 0,
        "failed": 0,
        "successRate": 0.0,
        "avgDurationSec": 0.0,
    }
    failures_by_task: dict[str, int] = defaultdict(int)
    latest_failures: list[dict] = []
    duration_sum = 0.0
    duration_count = 0

    if target.exists():
        try:
            lines = target.read_text(encoding="utf-8").splitlines()
        except Exception:
            lines = []

        for raw in lines[-5000:]:
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue

            status = str(row.get("status") or "").lower()
            if status not in {"success", "failed"}:
                continue

            when = row.get("finishedAt") or row.get("startedAt")
            dt = parse_local_time(str(when)) if when else None
            if not dt:
                continue
            day = dt.strftime("%Y-%m-%d")
            if day not in day_map:
                continue

            rec = day_map[day]
            rec["total"] += 1
            summary["total"] += 1

            if status == "success":
                rec["success"] += 1
                summary["success"] += 1
            else:
                rec["failed"] += 1
                summary["failed"] += 1
                task_name = str(row.get("name") or "unknown")
                failures_by_task[task_name] += 1
                latest_failures.append(
                    {
                        "id": row.get("id"),
                        "name": task_name,
                        "finishedAt": row.get("finishedAt"),
                        "failedStep": row.get("failedStep"),
                        "failedCode": row.get("failedCode"),
                        "error": row.get("error"),
                        "_ts": int(dt.timestamp() * 1000),
                    }
                )

            try:
                duration = float(row.get("durationSec"))
            except Exception:
                duration = -1.0
            if duration >= 0:
                rec["_durationSum"] += duration
                rec["_durationCount"] += 1
                duration_sum += duration
                duration_count += 1

    if summary["total"] > 0:
        summary["successRate"] = round(summary["success"] * 100.0 / summary["total"], 2)
    if duration_count > 0:
        summary["avgDurationSec"] = round(duration_sum / duration_count, 2)

    daily = []
    for day in day_keys:
        rec = day_map[day]
        total = rec["total"]
        success = rec["success"]
        success_rate = round(success * 100.0 / total, 2) if total > 0 else 0.0
        avg_duration = round(rec["_durationSum"] / rec["_durationCount"], 2) if rec["_durationCount"] > 0 else 0.0
        daily.append(
            {
                "day": day,
                "total": total,
                "success": success,
                "failed": rec["failed"],
                "successRate": success_rate,
                "avgDurationSec": avg_duration,
            }
        )

    failures_top = [
        {"name": name, "count": count}
        for name, count in sorted(failures_by_task.items(), key=lambda x: x[1], reverse=True)[:5]
    ]
    latest_failures.sort(key=lambda x: x.get("_ts") or 0, reverse=True)
    latest_failures = [
        {k: v for k, v in item.items() if k != "_ts"}
        for item in latest_failures[:6]
    ]

    return {
        "summary": summary,
        "daily": daily,
        "failuresByTask": failures_top,
        "latestFailures": latest_failures,
        "generatedAt": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "sourceFile": str(target),
    }


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
    github_api_budget = new_github_api_budget()
    repo_slug = project.get("repoSlug") or association.get("projectRepo")
    github_tracker = fetch_github_tracker(repo_slug, gh_bin, gh_env, api_budget=github_api_budget) if github_auth.get("ok") else {
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
        "cache": {},
    }

    issue_deltas = build_issue_deltas(github_tracker.get("issues") or [], previous_snapshot)
    github_timeline = (
        fetch_github_timeline(repo_slug, gh_bin, gh_env, api_budget=github_api_budget)
        if github_tracker.get("ok")
        else {
            "ok": False,
            "repo": repo_slug,
            "prs": [],
            "commits": [],
            "error": "github timeline unavailable",
            "source": "none",
        }
    )
    owner_evidence = build_owner_timeline_evidence(github_tracker, issue_deltas, github_timeline)
    role_evidence_chains = build_role_evidence_chains(github_tracker, issue_deltas, github_timeline)
    company = build_agent_panel(cfg, team, github_tracker, owner_evidence, role_evidence_chains)
    blockers_board, risks_board, blockers_source = build_issue_boards(github_tracker, company.get("agents") or [])
    milestones = github_tracker.get("milestones") if github_tracker.get("milestones") else compute_team_milestones(team)
    milestones_source = "github" if github_tracker.get("milestones") else "team-status"
    activity_feed = build_activity_feed(group_jobs, local_jobs, github_tracker, company.get("agents") or [])
    control_tasks = read_control_task_metrics()
    business_radar = read_latest_radar_brief()
    business_metrics = read_business_metrics()
    freshness = {
        "config": file_mtime(CONFIG_PATH),
        "cron": file_mtime(CRON_PATH),
        "teamStatus": file_mtime(TEAM_PATH),
        "association": file_mtime(ASSOCIATION_PATH),
        "businessMetrics": file_mtime(BUSINESS_METRICS_PATH),
        "controlTaskHistory": file_mtime(CONTROL_TASK_HISTORY_PATH),
    }
    api_budget_limit = int(github_api_budget.get("limit") or 0)
    api_budget_used = int(github_api_budget.get("used") or 0)
    api_budget_remaining = max(0, api_budget_limit - api_budget_used)

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
            "controlTask7dTotal": ((control_tasks.get("summary") or {}).get("total") or 0),
            "controlTask7dSuccessRate": ((control_tasks.get("summary") or {}).get("successRate") or 0.0),
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
            "cache": github_tracker.get("cache") or {},
            "apiBudget": {
                "limit": api_budget_limit,
                "used": api_budget_used,
                "remaining": api_budget_remaining,
                "degraded": bool(github_api_budget.get("degraded")),
                "skipped": int(github_api_budget.get("skipped") or 0),
            },
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
        "controlTasks": control_tasks,
        "deltas": {
            "issues": issue_deltas,
        },
        "businessRadar": business_radar,
        "businessMetrics": business_metrics,
        "freshness": freshness,
        "sla": {
            "dashboardDataMaxAgeMinutes": DASHBOARD_DATA_SLA_MINUTES,
        },
        "cronJobs": sorted(all_jobs, key=lambda x: (x.get("kind") != "openclaw-cron", x.get("name") or "")),
        "dataSources": {
            "agentPanel": "github-issues+timeline-strict" if github_tracker.get("ok") else "session+team-status",
            "github": "gh-cli+ttl-cache+api-budget",
            "blockers": blockers_source,
            "milestones": milestones_source,
            "cronJobs": "openclaw-cron+launchd",
            "activityFeed": "cron+github+agent-sessions",
            "issueDeltas": "snapshot-diff",
            "roleEvidence": "issue+pr+commit+auto-status-comment",
            "businessRadar": "delivery-queue",
            "businessMetrics": "business-metrics.json" if business_metrics.get("isReal") else "proxy-estimation",
            "controlTasks": "run/control-task-history.jsonl",
        },
    }

    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    build()
