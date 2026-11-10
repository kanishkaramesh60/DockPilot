#!/usr/bin/env python3
"""
DockPilot Alertmanager Configuration Synchronizer
Reads SMTP and receiver settings from .env (or environment variables)
and updates alertmanager/alertmanager.yml safely without exposing passwords.
"""

import os
import re
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_FILE = PROJECT_ROOT / "alertmanager" / "alertmanager.yml"


def load_env_file(path: Path) -> dict[str, str]:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            env[key.strip()] = val.strip().strip("'\"")
    return env


def main():
    file_env = load_env_file(ENV_FILE)
    merged_env = {**file_env, **os.environ}

    # Extract settings with fallback defaults
    smarthost = merged_env.get("SMTP_SMARTHOST", "smtp.gmail.com")
    port = merged_env.get("SMTP_PORT", "587")
    if ":" not in smarthost:
        full_smarthost = f"{smarthost}:{port}"
    else:
        full_smarthost = smarthost

    smtp_from = merged_env.get("SMTP_FROM", "dockpilot-alerts@gmail.com")
    smtp_user = merged_env.get("SMTP_AUTH_USERNAME", smtp_from)
    smtp_pass = merged_env.get("SMTP_AUTH_PASSWORD", "change_me_to_smtp_app_password")
    smtp_tls = merged_env.get("SMTP_REQUIRE_TLS", "true").lower() in ("true", "1", "yes")

    receiver_default = merged_env.get("ALERT_RECEIVER_EMAIL", "admin@dockpilot.local")
    receiver_critical = merged_env.get("ALERT_RECEIVER_CRITICAL_EMAIL", "devops-critical@dockpilot.local")
    receiver_warning = merged_env.get("ALERT_RECEIVER_WARNING_EMAIL", "devops-warning@dockpilot.local")

    if not CONFIG_FILE.exists():
        print(f"[ERROR] Config file not found: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    content = CONFIG_FILE.read_text(encoding="utf-8")

    # Update global SMTP settings
    content = re.sub(r"smtp_smarthost:\s*'.*?'", f"smtp_smarthost: '{full_smarthost}'", content)
    content = re.sub(r"smtp_from:\s*'.*?'", f"smtp_from: '{smtp_from}'", content)
    content = re.sub(r"smtp_auth_username:\s*'.*?'", f"smtp_auth_username: '{smtp_user}'", content)
    content = re.sub(r"smtp_auth_password:\s*'.*?'", f"smtp_auth_password: '{smtp_pass}'", content)
    content = re.sub(r"smtp_require_tls:\s*(true|false)", f"smtp_require_tls: {'true' if smtp_tls else 'false'}", content)

    # Update receivers email 'to:' fields
    # dockpilot-default-receiver
    pattern_default = r"(- name: 'dockpilot-default-receiver'[\s\S]*?to:\s*)'.*?'"
    content = re.sub(pattern_default, rf"\g<1>'{receiver_default}'", content, count=1)

    # dockpilot-critical-receiver
    pattern_critical = r"(- name: 'dockpilot-critical-receiver'[\s\S]*?to:\s*)'.*?'"
    content = re.sub(pattern_critical, rf"\g<1>'{receiver_critical}'", content, count=1)

    # dockpilot-warning-receiver
    pattern_warning = r"(- name: 'dockpilot-warning-receiver'[\s\S]*?to:\s*)'.*?'"
    content = re.sub(pattern_warning, rf"\g<1>'{receiver_warning}'", content, count=1)

    CONFIG_FILE.write_text(content, encoding="utf-8")
    masked_pass = f"{smtp_pass[:2]}****{smtp_pass[-2:]}" if len(smtp_pass) > 4 else "****"
    print(f"[SUCCESS] Updated {CONFIG_FILE.name} with:")
    print(f"  SMTP Smarthost: {full_smarthost}")
    print(f"  SMTP From:      {smtp_from}")
    print(f"  SMTP Username:  {smtp_user}")
    print(f"  SMTP Password:  {masked_pass} (masked)")
    print(f"  SMTP TLS:       {smtp_tls}")
    print(f"  Receivers:      default={receiver_default}, critical={receiver_critical}, warning={receiver_warning}")

    # Hot reload Alertmanager if running
    try:
        req = urllib.request.Request("http://localhost:9093/-/reload", method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                print("[SUCCESS] Hot-reloaded Alertmanager configuration via /-/reload")
    except Exception:
        print("[INFO] Alertmanager not currently running on localhost:9093 (reload skipped)")


if __name__ == "__main__":
    main()
