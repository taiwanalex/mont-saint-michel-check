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
    target_date = "2026-12-30"

    target_url = "https://tickets.monuments-nationaux.fr/en-GB/products?famille=2032864763370400282&product=2308732817290400284"
    
    current_status = "未知 / 未取得"
    is_available = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="en-GB",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        print(f"[{now_str}] 正在連線聖米歇爾山官方售票日曆...")
        page.goto(target_url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        # 1. 關閉 Cookie 遮罩
        for btn_sel in ["#tarteaucitronPersonalize2", "button:has-text('Accept')", "button:has-text('Accepter')"]:
            try:
                btn = page.locator(btn_sel)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click()
                    page.wait_for_timeout(1000)
                    break
            except Exception:
                pass

        # 2. 切換月份直到 December 2026 出現
        for _ in range(4):
            body_content = page.content()
            if "December 2026" in body_content or "décembre 2026" in body_content.lower():
                print("[INFO] 已成功切換至 2026 年 12 月日曆。")
                break
            
            # 尋找下個月箭頭按鈕
            next_arrow = page.locator(".fc-next-button, button[aria-label*='next'], .calendar-next, button.next, [class*='next']")
            if next_arrow.count() > 0 and next_arrow.first.is_visible():
                next_arrow.first.click()
                page.wait_for_timeout(2000)
            else:
                break

        page.wait_for_timeout(2000)

        # 3. 精確定位 2026-12-30
        date_cell = page.locator("[data-date='2026-12-30'], td[data-date*='12-30']")
        if date_cell.count() > 0:
            cell_class = date_cell.first.get_attribute("class") or ""
            cell_html = date_cell.first.inner_html().lower()
            cell_text = date_cell.first.inner_text().strip()
            print(f"[DEBUG] 抓取到 12-30 單元格: class='{cell_class}', text='{cell_text}'")

            if "available" in cell_class.lower() or "disponible" in cell_class.lower() or "available" in cell_html:
                current_status = "Available"
                is_available = True
            elif "disabled" in cell_class.lower() or "inactive" in cell_class.lower() or "fc-day-disabled" in cell_class:
                current_status = "Inactive"
            else:
                current_status = "Inactive"
        else:
            # 備用文字解析：直接比對 12 月的內文
            page_text = page.inner_text("body")
            if "30" in page_text:
                lines = [l.strip() for l in page_text.splitlines() if l.strip()]
                for i, l in enumerate(lines):
                    if l == "30" and i + 1 < len(lines):
                        nxt = lines[i + 1].lower()
                        if "available" in nxt:
                            current_status = "Available"
                            is_available = True
                            break
                        elif "inactive" in nxt or "indisponible" in nxt:
                            current_status = "Inactive"
                            break

        # 只要不是 Available，一律視為未放票的 Inactive
        if current_status == "未知 / 未取得":
            current_status = "Inactive"

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
