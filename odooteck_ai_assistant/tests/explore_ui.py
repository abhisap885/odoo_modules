"""Read-only browser exploration of the demo UI for screenshot planning."""
import os

from playwright.sync_api import sync_playwright

base = os.environ.get("ODOO_BASE_URL", "http://127.0.0.1:8019")
login = os.environ.get("ODOO_LOGIN", "admin")
password = os.environ.get("ODOO_PASSWORD", "admin")
actions = [
    "action_ot_ai_bot", "action_ot_ai_knowledge", "action_ot_ai_session",
    "action_ot_ai_message", "action_ot_ai_provider",
]

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    page.goto(base + "/web/login?db=demo", wait_until="domcontentloaded", timeout=30000)
    with page.expect_navigation(timeout=30000):
        page.evaluate("""([username, secret]) => {
            const form = document.querySelector('form.oe_login_form');
            form.querySelector('input[name="login"]').value = username;
            form.querySelector('input[name="password"]').value = secret;
            form.submit();
        }""", [login, password])
    page.wait_for_timeout(900)
    print("login URL:", page.url)
    if "/web/login" in page.url:
        print("login errors:", page.locator(".alert-danger").all_text_contents())
        print("body:", page.locator("body").inner_text()[-900:])
        raise SystemExit("Demo login failed; browser exploration needs valid credentials.")
    for action in actions:
        page.goto(base + "/odoo/action-odooteck_ai_assistant." + action, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1400)
        title = page.title()
        rows = page.locator(".o_list_table tbody tr").count()
        print(action, "title:", title, "rows:", rows, "url:", page.url)
        print(" first row:", page.locator(".o_list_table tbody tr").first.inner_text()[:180] if rows else "empty")
    page.goto(base + "/shop?db=demo", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1000)
    print("shop widget:", page.locator("#ot-ai-chat").count(),
          "style error:", "style compilation failed" in page.locator("body").inner_text().lower())
    browser.close()
