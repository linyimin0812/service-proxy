#!/usr/bin/env python3
"""
服务健康状态监控脚本
定时访问 /api/monitor/status，当存在 unhealthy 服务时发送 ntfy 通知。
支持疲劳度控制：每小时最多发送 10 次通知。

用法:
    python3 monitor_ntfy.py

环境变量:
    MONITOR_URL      - 监控接口地址（默认: https://proxy.banzhe.top/api/monitor/status）
    NTFY_URL         - ntfy 服务地址（默认: https://ntfy.sh）
    NTFY_TOPIC       - ntfy 通知主题（必填）
    MAX_ALERTS_HOUR  - 每小时最大通知次数（默认: 10）
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import ssl
from datetime import datetime
from pathlib import Path

MONITOR_URL = os.getenv("MONITOR_URL", "https://proxy.banzhe.top/api/monitor/status")
NTFY_URL = os.getenv("NTFY_URL", "https://ntfy.sh")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "9xjK12pv995OXYl1")
MAX_ALERTS_PER_HOUR = int(os.getenv("MAX_ALERTS_HOUR", "10"))

STATE_FILE = Path("/tmp/monitor_ntfy_state.json")


def load_state():
    """加载疲劳度控制状态"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"alerts": [], "last_unhealthy": []}


def save_state(state):
    """保存疲劳度控制状态"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def is_rate_limited(state):
    """检查是否超过每小时通知上限"""
    now = time.time()
    one_hour_ago = now - 3600
    recent_alerts = [t for t in state.get("alerts", []) if t > one_hour_ago]
    state["alerts"] = recent_alerts
    return len(recent_alerts) >= MAX_ALERTS_PER_HOUR


def record_alert(state):
    """记录一次通知发送"""
    state["alerts"].append(time.time())


def fetch_monitor_status():
    """获取监控状态"""
    ctx = ssl.create_default_context()
    request = urllib.request.Request(MONITOR_URL, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30, context=ctx) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        print(f"[{datetime.now()}] 请求监控接口失败: {error}")
        return None
    except Exception as error:
        print(f"[{datetime.now()}] 未知错误: {error}")
        return None


def build_notification_body(status_data):
    """构建 Markdown 格式的通知内容"""
    unhealthy = status_data.get("unhealthy_services", [])
    total = status_data.get("total", 0)
    healthy_count = status_data.get("healthy", 0)
    unhealthy_count = status_data.get("unhealthy", 0)

    lines = [
        f"**总服务数**: {total} | ✅ 健康: {healthy_count} | ❌ 异常: {unhealthy_count}",
        "",
    ]

    for service in unhealthy:
        path = service.get("path", "unknown")
        target = service.get("target", "unknown")
        description = service.get("description", "")
        error_message = service.get("error", "未知错误")
        label = f"{description} ({path})" if description else path
        lines.append(f"- **{label}** → `{target}`")
        lines.append(f"  错误: {error_message}")

    return "\n".join(lines)


def send_ntfy_notification(title, body, priority="high", tags="warning,server"):
    """发送 ntfy 通知（Markdown 格式）"""
    url = f"{NTFY_URL}/{NTFY_TOPIC}"

    # HTTP Header 仅支持 latin-1 编码，将 emoji 从 title 中移除
    ascii_title = title.encode("ascii", errors="ignore").decode("ascii").strip()
    headers = {
        "Title": ascii_title,
        "Priority": priority,
        "Tags": tags,
        "Markdown": "yes",
    }

    request = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=15, context=ctx) as response:
            print(f"[{datetime.now()}] ntfy 通知发送成功 (HTTP {response.status})")
            return True
    except Exception as error:
        print(f"[{datetime.now()}] ntfy 通知发送失败: {error}")
        return False


def send_recovery_notification(recovered_services):
    """发送恢复通知"""
    lines = ["以下服务已恢复正常：", ""]
    for service_path in recovered_services:
        lines.append(f"- **{service_path}**")

    body = "\n".join(lines)
    send_ntfy_notification("服务已恢复", body, priority="default", tags="white_check_mark,server")


def main():
    if not NTFY_TOPIC:
        print("错误: 请设置 NTFY_TOPIC 环境变量")
        sys.exit(1)

    state = load_state()
    status_data = fetch_monitor_status()

    if status_data is None:
        if not is_rate_limited(state):
            send_ntfy_notification(
                "监控接口不可达",
                f"无法访问监控接口: `{MONITOR_URL}`\n\n请检查服务是否正常运行。",
                priority="urgent",
                tags="rotating_light,server",
            )
            record_alert(state)
            save_state(state)
        else:
            print(f"[{datetime.now()}] 监控接口不可达，但已达到通知频率上限，跳过通知")
        return

    overall_status = status_data.get("overall_status", "unknown")
    unhealthy_services = status_data.get("unhealthy_services", [])
    current_unhealthy_paths = {s.get("path", "") for s in unhealthy_services}
    previous_unhealthy_paths = set(state.get("last_unhealthy", []))

    # 检查是否有服务恢复
    recovered = previous_unhealthy_paths - current_unhealthy_paths
    if recovered and not is_rate_limited(state):
        send_recovery_notification(recovered)
        record_alert(state)

    # 检查是否有异常服务
    if overall_status != "healthy" and unhealthy_services:
        new_unhealthy = current_unhealthy_paths - previous_unhealthy_paths
        is_new_alert = bool(new_unhealthy)

        if is_rate_limited(state):
            remaining = MAX_ALERTS_PER_HOUR - len(state["alerts"])
            print(
                f"[{datetime.now()}] 存在 {len(unhealthy_services)} 个异常服务，"
                f"但已达到通知频率上限（剩余 {remaining} 次），跳过通知"
            )
        else:
            if is_new_alert:
                title = "服务异常告警"
                alert_tags = "rotating_light,server"
            else:
                title = "服务持续异常"
                alert_tags = "warning,server"
            body = build_notification_body(status_data)
            send_ntfy_notification(title, body, tags=alert_tags)
            record_alert(state)
    else:
        print(f"[{datetime.now()}] 所有服务正常 ✅ (共 {status_data.get('total', 0)} 个)")

    # 更新状态
    state["last_unhealthy"] = list(current_unhealthy_paths)
    save_state(state)


if __name__ == "__main__":
    main()
