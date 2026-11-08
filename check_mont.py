import os
import sys
from playwright.sync_api import sync_playwright
import requests

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "8777128716")

def send_telegram(text: str):
    if not TG_BOT_TOKEN:
        print("[WARN] TG_BOT_TOKEN 未設定，直接印出訊息：\n", text)
        return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        print(f"[TG] 發送狀態: {resp.status_code}")
    except Exception as e:
        print(f"[TG] 發送失敗: {e}")

def run_check():
    target_url = "https://tickets.monuments-nationaux.fr/en-GB/products?famille=2032864763370400282&product=2308732817290400284"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="en-GB"
        )
        page = context.new_page()

        print("[INFO] 正在載入聖米歇爾山導覽日曆...")
        page.goto(target_url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        page_text = page.inner_text("body")
        lines = [l.strip() for l in page_text.splitlines() if l.strip()]

        is_available = False
        for i, line in enumerate(lines):
            if line == "30" and i + 1 < len(lines):
                next_line = lines[i + 1]
                print(f"[DEBUG] 30 日當前狀態: {next_line}")
                if "available" in next_line.lower() and "inactive" not in next_line.lower():
                    is_available = True
                break

        browser.close()

        if is_available:
            msg = (
                "🚨 <b>【聖米歇爾山】12/30 深度英文導覽已放票！</b>\n\n"
                "項目：Conference tour in English (2h00)\n"
                "日期：2026-12-30\n"
                "狀態：<b>Available (可預約)</b>\n\n"
                f"🔗 <b>立即前往預約：</b>\n{target_url}"
            )
            print("[ALERT] 12/30 開放！發送 Telegram 通知...")
            send_telegram(msg)
        else:
            print("[OK] 12/30 目前仍為 Inactive。")

if __name__ == "__main__":
    run_check()
