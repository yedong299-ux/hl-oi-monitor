"""
Hyperliquid 持仓量(OI) 5分钟变化监控
数据源：Hyperliquid 官方公开接口 https://api.hyperliquid.xyz/info (免费，无需 API Key)
每次运行：拉取全市场最新 OI，和上一次运行(约5分钟前)的快照比较，
超过阈值就通过 Bark 推送提醒，然后把本次快照存回 state.json。

建议用 GitHub Actions 定时(每5分钟)跑这个脚本，见同目录 monitor.yml。
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
STATE_FILE = Path(__file__).parent / "state.json"

# 变化阈值(百分比)，超过就提醒
THRESHOLD_PCT = float(os.environ.get("OI_CHANGE_THRESHOLD", "10"))

# 如果快照太老（比如脚本没按时跑），超过这个秒数就不拿来做比较，避免把"1小时变化"误报成"5分钟变化"
MAX_SNAPSHOT_AGE_SECONDS = int(os.environ.get("MAX_SNAPSHOT_AGE_SECONDS", "900"))  # 15分钟

# 只监控这些币种；留空 = 监控全市场所有 Hyperliquid 永续合约
# 例：WATCHLIST = ["B2", "MMT", "STRK", "AR", "MARSCOIN", "ARK", "VTHO", "USELESS"]
WATCHLIST_ENV = os.environ.get("OI_WATCHLIST", "").strip()
WATCHLIST = [s.strip().upper() for s in WATCHLIST_ENV.split(",") if s.strip()] if WATCHLIST_ENV else None

BARK_KEY = os.environ.get("BARK_KEY", "").strip()
BARK_SERVER = os.environ.get("BARK_SERVER", "https://api.day.app").rstrip("/")


def fetch_asset_contexts():
    """返回 {coin: {"oi_usd": float, "price": float}}"""
    resp = requests.post(
        HL_INFO_URL,
        json={"type": "metaAndAssetCtxs"},
        timeout=20,
    )
    resp.raise_for_status()
    meta, asset_ctxs = resp.json()
    universe = meta["universe"]

    result = {}
    for coin_meta, ctx in zip(universe, asset_ctxs):
        if coin_meta.get("isDelisted"):
            continue
        name = coin_meta["name"]
        try:
            mark_px = float(ctx["markPx"])
            oi_base = float(ctx["openInterest"])
        except (KeyError, TypeError, ValueError):
            continue
        result[name] = {"oi_usd": oi_base * mark_px, "price": mark_px}
    return result


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def send_bark(title, body):
    if not BARK_KEY:
        print(f"[跳过推送-未配置BARK_KEY] {title}: {body}")
        return
    url = f"{BARK_SERVER}/{BARK_KEY}/{requests.utils.quote(title)}/{requests.utils.quote(body)}"
    try:
        r = requests.get(url, params={"group": "OI监控", "sound": "alarm"}, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[Bark推送失败] {e}", file=sys.stderr)


def fmt_usd(v):
    if v >= 1e8:
        return f"${v / 1e8:.2f}亿"
    if v >= 1e4:
        return f"${v / 1e4:.1f}万"
    return f"${v:.0f}"


def main():
    now = time.time()
    current = fetch_asset_contexts()
    prev_state = load_state()

    if WATCHLIST:
        coins_to_check = [c for c in WATCHLIST if c in current]
    else:
        coins_to_check = list(current.keys())

    alerts = []
    for coin in coins_to_check:
        cur = current[coin]
        prev = prev_state.get(coin)
        if not prev:
            continue
        age = now - prev.get("ts", 0)
        if age > MAX_SNAPSHOT_AGE_SECONDS or age <= 0:
            continue
        prev_oi = prev.get("oi_usd", 0)
        if prev_oi <= 0:
            continue
        pct_change = (cur["oi_usd"] - prev_oi) / prev_oi * 100
        if abs(pct_change) >= THRESHOLD_PCT:
            alerts.append((coin, pct_change, prev_oi, cur["oi_usd"], age))

    for coin, pct_change, prev_oi, cur_oi, age in alerts:
        direction = "暴增" if pct_change > 0 else "暴减"
        title = f"{coin} 持仓量{direction} {pct_change:+.1f}%"
        body = f"{fmt_usd(prev_oi)} → {fmt_usd(cur_oi)}（约{age/60:.0f}分钟内）"
        print(f"[ALERT] {title} | {body}")
        send_bark(title, body)

    if not alerts:
        print(f"本次检查 {len(coins_to_check)} 个币种，无超过 {THRESHOLD_PCT}% 的持仓量变化。")

    # 更新快照
    new_state = {
        coin: {"ts": now, "oi_usd": current[coin]["oi_usd"]}
        for coin in current
    }
    save_state(new_state)


if __name__ == "__main__":
    main()
