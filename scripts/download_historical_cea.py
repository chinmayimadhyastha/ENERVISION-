from pathlib import Path
from playwright.sync_api import sync_playwright
import time

BASE_DIR = Path(__file__).resolve().parent.parent

SAVE_DIR = BASE_DIR / "data" / "generation" / "historical_raw"
SAVE_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://cea.nic.in/daily-renewable-generation-report/?lang=en"

FROM_DATE = "01/01/2022"
TO_DATE = "07/06/2022"


with sync_playwright() as p:

    browser = p.chromium.launch(headless=False)

    page = browser.new_page(accept_downloads=True)

    print("\n" + "=" * 60)
    print("DOWNLOADING CEA 2022 GAP")
    print("01/01/2022 → 07/06/2022")
    print("=" * 60)

    page.goto(URL, wait_until="domcontentloaded")

    time.sleep(5)

    # -----------------------------------------
    # DATE FILTER
    # -----------------------------------------

    min_date = page.locator('input[name="min"]')
    max_date = page.locator('input[name="max"]')

    min_date.fill(FROM_DATE)
    max_date.fill(TO_DATE)

    min_date.dispatch_event("input")
    max_date.dispatch_event("input")

    min_date.dispatch_event("change")
    max_date.dispatch_event("change")

    max_date.press("Enter")

    time.sleep(8)

    # -----------------------------------------
    # SELECT ALL RECORDS
    # -----------------------------------------

    try:

        select = page.locator("select").first

        select.select_option(value="-1")

        time.sleep(5)

    except Exception as e:

        print("Could not select All:", e)

    # -----------------------------------------
    # FIND REPORTS
    # -----------------------------------------

    rows = page.locator("table tbody tr")

    print(f"\nReports found: {rows.count()}")

    downloaded = 0
    skipped = 0
    failed = 0

    # -----------------------------------------
    # DOWNLOAD ONLY 2022-01-01 → 2022-07-06
    # -----------------------------------------

    for i in range(rows.count()):

        row = rows.nth(i)

        cells = row.locator("td")

        if cells.count() < 3:
            continue

        report_name = cells.nth(0).inner_text().strip()
        report_date = cells.nth(1).inner_text().strip()

        print(
            f"{i + 1}: {report_name} | {report_date}"
        )

        # -------------------------------------
        # SAFETY CHECK
        # -------------------------------------

        try:

            year, month, day = map(
                int,
                report_date.split("-")
            )

            report_key = year * 10000 + month * 100 + day

        except:

            print("   Could not read date")
            continue

        start_key = 20220101
        end_key = 20220706

        if not (start_key <= report_key <= end_key):

            print("   Skipping - outside required range")

            continue

        # -------------------------------------
        # OUTPUT FILE
        # -------------------------------------

        output_file = SAVE_DIR / f"{report_name}.pdf"

        if output_file.exists():

            print("   Already exists")

            skipped += 1

            continue

        # -------------------------------------
        # PDF LINK
        # -------------------------------------

        links = cells.nth(2).locator("a")

        if links.count() == 0:

            print("   No PDF link")

            failed += 1

            continue

        # -------------------------------------
        # DOWNLOAD
        # -------------------------------------

        try:

            with page.expect_download(timeout=30000) as download_info:

                links.first.click()

            download = download_info.value

            download.save_as(output_file)

            print("   Downloaded:", output_file.name)

            downloaded += 1

        except Exception as e:

            print("   FAILED:", e)

            failed += 1

    # -----------------------------------------
    # SUMMARY
    # -----------------------------------------

    print("\n" + "=" * 60)
    print("2022 GAP DOWNLOAD SUMMARY")
    print("=" * 60)

    print("Downloaded:", downloaded)
    print("Already existed:", skipped)
    print("Failed:", failed)

    browser.close()

print("\nFinished!")