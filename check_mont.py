import os
import sys
import json
from datetime import datetime
import pytz
from playwright.sync_api import sync_playwright
import requests

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
    target_date = "2026-12-30"

    target_url = "https://tickets.monuments-nationaux.fr/en-GB/products?famille=2032864763370400282&product=2308732817290400284"
    
    current_status = "未知 / 未取得"
    is_available = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="en-GB",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        # 監聽網路傳輸，攔截日曆資料 API
        api_data = {}
        def handle_response(response):
            if any(k in response.url for k in ["availability", "calendrier", "calendar", "products", "seance"]):
                try:
                    if "json" in response.headers.get("content-type", ""):
                        data = response.json()
                        api_data[response.url] = data
                except Exception:
                    pass

        page.on("response", handle_response)

        print(f"[{now_str}] 正在連線聖米歇爾山官方售票日曆...")
        page.goto(target_url, wait_until="networkidle", timeout=60000)

        # 處理並關閉 Cookie 隱私彈窗（若存在）
        try:
            cookie_btn = page.locator("button#tarteaucitronPersonalize2, button:has-text('Accept all'), button:has-text('Tout accepter'), button:has-text('Allow all')")
            if cookie_btn.count() > 0 and cookie_btn.first.is_visible():
                cookie_btn.first.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        # 等待日曆渲染完成
        page.wait_for_timeout(5000)

        # 檢查月份，若在 11 月則切換至 12 月
        try:
            body_text = page.inner_text("body")
            if "December" not in body_text:
                next_btns = page.locator("button[aria-label*='Next'], [class*='next'], .calendar-next, button:has-text('>')")
                if next_btns.count() > 0:
                    next_btns.first.click()
                    page.wait_for_timeout(3000)
        except Exception:
            pass

        # 解析畫面上的日期文字
        full_text = page.inner_text("body")
        lines = [l.strip() for l in full_text.splitlines() if l.strip()]

        for i, line in enumerate(lines):
            if line == "30" and i + 1 < len(lines):
                candidate = lines[i + 1]
                # 排除一般月份文字，確認是狀態詞
                if any(k in candidate.lower() for k in ["inactive", "available", "sold out", "full", "complet"]):
                    current_status = candidate
                    break

        # 備用 DOM 定位
        if current_status == "未知 / 未取得":
            elements = page.locator("xpath=//*[text()='30' or contains(text(), ' 30 ')]").all()
            for el in elements:
                try:
                    parent_text = el.locator("xpath=..").inner_text().strip()
                    if "inactive" in parent_text.lower():
                        current_status = "Inactive"
                        break
                    elif "available" in parent_text.lower():
                        current_status = "Available"
                        break
                except Exception:
                    continue

        if "available" in current_status.lower() and "inactive" not in current_status.lower():
            is_available = True

        browser.close()

    print("=" * 45)
    print(f"查詢時間 (台灣時間): {now_str}")
    print(f"查詢目標: {target_date} (Conference tour in English)")
    print(f"當前官方狀態: 【 {current_status} 】")
    print("=" * 45)

    if is_available:
        alert_msg = (
            "🚨 <b>【聖米歇爾山】12/30 深度英文導覽已放票！</b>\n\n"
            f"🕒 查驗時間：{now_str} (TW)\n"
            "📌 項目：Conference tour in English (2h00)\n"
            f"📅 日期：{target_date}\n"
            f"⚡ 狀態：<b>{current_status} (可預約)</b>\n\n"
            f"🔗 <b>立即前往預約：</b>\n{target_url}"
        )
        print("[ALERT] 12/30 開放！Alert Bot 發送通知！")
        send_telegram(ALERT_BOT_TOKEN, alert_msg, silent=False)
    else:
        status_msg = (
            "ℹ️ <b>【聖米歇爾山票況巡檢】</b>\n\n"
            f"🕒 檢查時間：{now_str} (TW)\n"
            f"📅 查詢日期：{target_date}\n"
            f"📊 當前狀態：<b>{current_status}</b>\n"
            "<i>（維持 30 分鐘自動監控中）</i>"
        )
        print(f"[STATUS] 目前狀態為 {current_status}，Mute Bot 發送記錄。")
        send_telegram(MUTE_BOT_TOKEN, status_msg, silent=True)

if __name__ == "__main__":
    run_check()
