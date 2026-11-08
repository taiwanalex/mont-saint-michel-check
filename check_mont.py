import os
import sys
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

    target_url = "https://tickets.monuments-nationaux.fr/en-GB/products?famille=2032864763370400282&product=2308732817290400284"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="en-GB"
        )
        page = context.new_page()

        print(f"[{now_str}] 正在連線聖米歇爾山官方售票日曆...")
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

        # 等待日曆組件或載入動畫完成
        try:
            page.wait_for_selector(".calendar, [class*='calendar'], table", timeout=15000)
        except Exception:
            pass
        page.wait_for_timeout(4000)

        # 確保顯示 12 月份（若當前是 11 月，點擊切換下一月）
        content = page.content()
        if "December" not in content and "12" not in page.title():
            next_btn = page.locator("button[aria-label*='Next'], [class*='next'], .calendar-next, button:has-text('>')")
            if next_btn.count() > 0:
                next_btn.first.click()
                page.wait_for_timeout(2000)

        # 抓取日曆所有文字內容
        page_text = page.inner_text("body")
        lines = [l.strip() for l in page_text.splitlines() if l.strip()]

        current_status = "未知 / 未取得"
        is_available = False

        # 方法 1：以文字排列順序比對（30 號下一行）
        for i, line in enumerate(lines):
            if line == "30" and i + 1 < len(lines):
                candidate = lines[i + 1]
                if any(k in candidate.lower() for k in ["inactive", "available", "sold out", "full"]):
                    current_status = candidate
                    break

        # 方法 2：若方法 1 沒抓到，以 DOM 節點屬性檢查
        if current_status == "未知 / 未取得":
            day_btn = page.locator("xpath=//*[text()='30' or contains(text(), ' 30 ')]/ancestor::*[self::td or self::button or self::div][1]")
            if day_btn.count() > 0:
                node_html = day_btn.first.inner_html().lower()
                node_class = day_btn.first.get_attribute("class") or ""
                node_text = day_btn.first.inner_text().strip()
                
                if "inactive" in node_html or "disabled" in node_class.lower() or "inactive" in node_class.lower():
                    current_status = "Inactive"
                elif "available" in node_html or "available" in node_class.lower():
                    current_status = "Available"
                elif node_text:
                    current_status = node_text.replace("\n", " ")

        if "available" in current_status.lower() and "inactive" not in current_status.lower():
            is_available = True

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
            print("[ALERT] 12/30 開放！Alert Bot 發送通知！")
            send_telegram(ALERT_BOT_TOKEN, alert_msg, silent=False)
        else:
            status_msg = (
                "ℹ️ <b>【聖米歇爾山票況巡檢】</b>\n\n"
                f"🕒 檢查時間：{now_str} (TW)\n"
                "📅 查詢日期：2026-12-30\n"
                f"📊 當前狀態：<b>{current_status}</b>\n"
                "<i>（維持 30 分鐘自動監控中）</i>"
            )
            print(f"[STATUS] 目前狀態為 {current_status}，Mute Bot 發送記錄。")
            send_telegram(MUTE_BOT_TOKEN, status_msg, silent=True)

if __name__ == "__main__":
    run_check()
