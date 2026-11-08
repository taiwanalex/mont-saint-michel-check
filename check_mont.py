import os
import sys
from datetime import datetime
import pytz
from playwright.sync_api import sync_playwright
import requests

# 雙 Bot Token 設定
ALERT_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
MUTE_BOT_TOKEN = os.getenv("TG_MUTE_BOT_TOKEN", ALERT_BOT_TOKEN)
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "8777128716")

def send_telegram(token: str, text: str, silent: bool = False):
    if not token:
        print("[WARN] Telegram Bot Token 未設定，本地輸出訊息：\n", text)
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "disable_notification": silent
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        print(f"[TG] 發送狀態碼: {resp.status_code}")
    except Exception as e:
        print(f"[TG] 發送失敗: {e}")

def run_check():
    tz = pytz.timezone("Asia/Taipei")
    now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    target_url = "https://tickets.monuments-nationaux.fr/en-GB/products?famille=2032864763370400282&product=2308732817290400284"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="en-GB"
        )
        page = context.new_page()

        print(f"[{now_str}] 正在連線聖米歇爾山官方售票日曆...")
        page.goto(target_url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        page_text = page.inner_text("body")
        lines = [l.strip() for l in page_text.splitlines() if l.strip()]

        current_status = "未知 / 未取得"
        is_available = False

        for i, line in enumerate(lines):
            if line == "30" and i + 1 < len(lines):
                current_status = lines[i + 1]
                if "available" in current_status.lower() and "inactive" not in current_status.lower():
                    is_available = True
                break

        browser.close()

        print("=" * 45)
        print(f"查詢時間 (台灣時間): {now_str}")
        print(f"查詢目標: 2026-12-30 (Conference tour in English)")
        print(f"當前官方狀態: 【 {current_status} 】")
        print("=" * 45)

        if is_available:
            alert_msg = (
                "🚨 <b>【聖米歇爾山】12/30 深度英文導覽已放票！</b>\n\n"
                f"🕒 查驗時間：{now_str} (TW)\n"
                "📌 項目：Conference tour in English (2h00)\n"
                "📅 日期：2026-12-30\n"
                f"⚡ 狀態：<b>{current_status} (可預約)</b>\n\n"
                f"🔗 <b>立即前往預約：</b>\n{target_url}"
            )
            print("[ALERT] 12/30 開放！Alert Bot 發送緊急通知！")
            send_telegram(ALERT_BOT_TOKEN, alert_msg, silent=False)
        else:
            status_msg = (
                "ℹ️ <b>【聖米歇爾山票況巡檢】</b>\n\n"
                f"🕒 檢查時間：{now_str} (TW)\n"
                "📅 查詢日期：2026-12-30\n"
                f"📊 當前狀態：<b>{current_status}</b>\n"
                "<i>（維持 30 分鐘自動監控中）</i>"
            )
            print(f"[STATUS] 目前狀態為 {current_status}，Mute Bot 發送靜音記錄。")
            send_telegram(MUTE_BOT_TOKEN, status_msg, silent=True)

if __name__ == "__main__":
    run_check()
