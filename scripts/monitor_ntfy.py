#!/usr/bin/env python3
"""
服务健康状态监控脚本（常驻运行）
每分钟检查一次 /api/monitor/status，根据服务状态发送 ntfy 通知。

通知策略:
  - 存在异常服务时：每 10 分钟发送一次高优先级通知
  - 所有服务正常时：每 6 小时发送一次低优先级通知
  - 服务恢复时：立即发送恢复通知

用法:
    python3 monitor_ntfy.py          # 前台运行
    nohup python3 monitor_ntfy.py &  # 后台运行

环境变量:
    MONITOR_URL          - 监控接口地址（默认: https://proxy.banzhe.top/api/monitor/status）
    NTFY_URL             - ntfy 服务地址（默认: https://ntfy.sh）
    NTFY_TOPIC           - ntfy 通知主题（必填）
    CHECK_INTERVAL       - 检查间隔秒数（默认: 60）
    ALERT_INTERVAL       - 异常通知间隔秒数（默认: 600，即 10 分钟）
    HEALTHY_INTERVAL     - 正常通知间隔秒数（默认: 21600，即 6 小时）
"""

import os
import sys
import json
import time
import signal
import urllib.request
import urllib.error
import ssl
from datetime import datetime
from pathlib import Path

MONITOR_URL = os.getenv("MONITOR_URL", "https://proxy.banzhe.top/api/monitor/status")
NTFY_URL = os.getenv("NTFY_URL", "https://ntfy.sh")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "9xjK12pv995OXYl1")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
ALERT_INTERVAL = int(os.getenv("ALERT_INTERVAL", "600"))
HEALTHY_INTERVAL = int(os.getenv("HEALTHY_INTERVAL", "21600"))

STATE_FILE = Path("/tmp/monitor_ntfy_state.json")

running = True


def handle_signal(signum, _frame):
    """优雅退出"""
    global running
    print(f"[{datetime.now()}] 收到信号 {signum}，正在退出...")
    running = False


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


def load_state():
    """加载持久化状态"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as state_file:
                return json.load(state_file)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "last_unhealthy": [],
        "last_alert_time": 0,
        "last_healthy_notify_time": 0,
    }


def save_state(state):
    """保存持久化状态"""
    with open(STATE_FILE, "w") as state_file:
        json.dump(state, state_file)


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


def build_alert_body(status_data):
    """构建异常告警的 Markdown 通知内容"""
    unhealthy = status_data.get("unhealthy_services", [])
    total = status_data.get("total", 0)
    healthy_count = status_data.get("healthy", 0)
    unhealthy_count = status_data.get("unhealthy", 0)

    lines = [
        f"**总服务数**: {total} | 健康: {healthy_count} | 异常: {unhealthy_count}",
        "",
    ]

    for service in unhealthy:
        path = service.get("path", "unknown")
        target = service.get("target", "unknown")
        description = service.get("description", "")
        error_message = service.get("error", "未知错误")
        label = f"{description} ({path})" if description else path
        lines.append(f"- **{label}** -> `{target}`")
        lines.append(f"  错误: {error_message}")

    return "\n".join(lines)


def build_healthy_body(status_data):
    """构建正常状态的 Markdown 通知内容"""
    total = status_data.get("total", 0)
    healthy_count = status_data.get("healthy", 0)
    avg_time = status_data.get("avg_response_time_ms")
    services = status_data.get("services", [])

    lines = [
        f"**总服务数**: {total} | 全部健康: {healthy_count}",
        "",
    ]

    for service in services:
        path = service.get("path", "unknown")
        description = service.get("description", "")
        response_time = service.get("response_time_ms")
        label = f"{description} ({path})" if description else path
        time_str = f" ({response_time}ms)" if response_time else ""
        lines.append(f"- **{label}**{time_str}")

    if avg_time:
        lines.append(f"\n**平均响应时间**: {avg_time}ms")

    return "\n".join(lines)


def send_ntfy_notification(title, body, priority="high", tags="warning,server"):
    """发送 ntfy 通知（Markdown 格式）"""
    url = f"{NTFY_URL}/{NTFY_TOPIC}"

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
            print(f"[{datetime.now()}] ntfy 通知发送成功 (HTTP {response.status}) - {title}")
            return True
    except Exception as error:
        print(f"[{datetime.now()}] ntfy 通知发送失败: {error}")
        return False


def check_and_notify(state):
    """执行一次检查并根据策略发送通知"""
    now = time.time()
    status_data = fetch_monitor_status()

    # 监控接口不可达：按异常间隔发送通知
    if status_data is None:
        time_since_last_alert = now - state.get("last_alert_time", 0)
        if time_since_last_alert >= ALERT_INTERVAL:
            send_ntfy_notification(
                "监控接口不可达",
                f"无法访问监控接口: `{MONITOR_URL}`\n\n请检查服务是否正常运行。",
                priority="urgent",
                tags="rotating_light,server",
            )
            state["last_alert_time"] = now
        else:
            remaining = int(ALERT_INTERVAL - time_since_last_alert)
            print(f"[{datetime.now()}] 监控接口不可达，{remaining}s 后再次通知")
        return

    overall_status = status_data.get("overall_status", "unknown")
    unhealthy_services = status_data.get("unhealthy_services", [])
    current_unhealthy_paths = {s.get("path", "") for s in unhealthy_services}
    previous_unhealthy_paths = set(state.get("last_unhealthy", []))

    # 检查是否有服务恢复 → 立即发送恢复通知
    recovered = previous_unhealthy_paths - current_unhealthy_paths
    if recovered:
        lines = ["以下服务已恢复正常：", ""]
        for service_path in recovered:
            lines.append(f"- **{service_path}**")
        send_ntfy_notification(
            "服务已恢复",
            "\n".join(lines),
            priority="default",
            tags="white_check_mark,server",
        )
        state["last_alert_time"] = now

    # 异常状态：每 ALERT_INTERVAL（10 分钟）通知一次，高优先级
    if overall_status != "healthy" and unhealthy_services:
        new_unhealthy = current_unhealthy_paths - previous_unhealthy_paths
        time_since_last_alert = now - state.get("last_alert_time", 0)

        if new_unhealthy or time_since_last_alert >= ALERT_INTERVAL:
            title = "服务异常告警" if new_unhealthy else "服务持续异常"
            alert_tags = "rotating_light,server" if new_unhealthy else "warning,server"
            body = build_alert_body(status_data)
            send_ntfy_notification(title, body, priority="high", tags=alert_tags)
            state["last_alert_time"] = now
        else:
            remaining = int(ALERT_INTERVAL - time_since_last_alert)
            print(
                f"[{datetime.now()}] 存在 {len(unhealthy_services)} 个异常服务，"
                f"{remaining}s 后再次通知"
            )

    # 正常状态：每 HEALTHY_INTERVAL（6 小时）通知一次，低优先级
    elif overall_status == "healthy":
        time_since_last_healthy = now - state.get("last_healthy_notify_time", 0)
        if time_since_last_healthy >= HEALTHY_INTERVAL:
            body = build_healthy_body(status_data)
            send_ntfy_notification(
                "服务状态正常",
                body,
                priority="low",
                tags="white_check_mark,server",
            )
            state["last_healthy_notify_time"] = now
        else:
            total = status_data.get("total", 0)
            print(f"[{datetime.now()}] 所有服务正常 (共 {total} 个)")

    # 更新状态
    state["last_unhealthy"] = list(current_unhealthy_paths)
    save_state(state)


def main():
    if not NTFY_TOPIC:
        print("错误: 请设置 NTFY_TOPIC 环境变量")
        sys.exit(1)

    print(f"[{datetime.now()}] 监控脚本启动")
    print(f"  监控地址: {MONITOR_URL}")
    print(f"  ntfy 主题: {NTFY_TOPIC}")
    print(f"  检查间隔: {CHECK_INTERVAL}s")
    print(f"  异常通知间隔: {ALERT_INTERVAL}s ({ALERT_INTERVAL // 60} 分钟)")
    print(f"  正常通知间隔: {HEALTHY_INTERVAL}s ({HEALTHY_INTERVAL // 3600} 小时)")

    state = load_state()

    while running:
        try:
            check_and_notify(state)
        except Exception as error:
            print(f"[{datetime.now()}] 检查异常: {error}")

        # 逐秒 sleep，以便信号能及时中断退出
        for _ in range(CHECK_INTERVAL):
            if not running:
                break
            time.sleep(1)

    print(f"[{datetime.now()}] 监控脚本已退出")


if __name__ == "__main__":
    main()
