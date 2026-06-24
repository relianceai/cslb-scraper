#!/usr/bin/env python3
import asyncio
import pandas as pd
import re
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx"

def extract_names(html):
    names = []
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label, value = cells[0].get_text().strip(), cells[1].get_text().strip()
                    if label == 'Name' and value and ' ' in value and re.match(r'^[A-Z]', value):
                        value = re.sub(r'\s+', ' ', value).strip()
                        if re.match(r'^[A-Za-z\s\-\']+$', value) and value not in names:
                            names.append(value)
        return list(dict.fromkeys(names))
    except:
        return names

async def scrape_license(page, license_num):
    try:
        await page.goto(SEARCH_URL, wait_until="load", timeout=30000)
        await page.wait_for_timeout(300)
        await page.fill("#MainContent_LicNo", str(license_num))
        await page.click("#MainContent_Contractor_License_Number_Search")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(800)
        try:
            await page.click("#MainContent_PersonnelLink", timeout=10000)
            await page.wait_for_timeout(800)
        except:
            pass
        return extract_names(await page.content())
    except Exception as e:
        return []

async def process_file(file_path):
    print(f"\nProcessing: {file_path}")
    print("=" * 60)

    df = pd.read_excel(file_path)
    if 'first_name' not in df.columns:
        df['first_name'] = ''
    if 'last_name' not in df.columns:
        df['last_name'] = ''

    total = len(df)
    start = datetime.now()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page()

        for idx, row in df.iterrows():
            lic = str(row['LicenseNumber'])

            if pd.notna(row['first_name']) and row['first_name'] != '':
                continue

            names = await scrape_license(page, lic)
            if names:
                parts = names[0].split(None, 1)
                df.at[idx, 'first_name'] = parts[0] if len(parts) > 0 else ''
                df.at[idx, 'last_name'] = parts[1] if len(parts) > 1 else ''
            else:
                df.at[idx, 'first_name'] = 'NO_DATA'

            if (idx + 1) % 25 == 0 or idx == 0:
                elapsed = (datetime.now() - start).total_seconds()
                rate = (idx + 1) / elapsed if elapsed > 0 else 0
                remaining = (total - idx - 1) / rate if rate > 0 else 0
                print(f"[{idx+1:3d}/{total:3d}] {lic:>8} - {rate:.1f}/sec (~{remaining/60:.0f}m remaining)")

        await browser.close()

    df.to_excel(file_path, index=False)
    elapsed = (datetime.now() - start).total_seconds()
    print(f"\n✓ Completed in {elapsed/60:.1f} minutes ({elapsed/3600:.2f} hours)")
    print(f"Total processed: {total}")

if __name__ == "__main__":
    asyncio.run(process_file('/root/test_file.xlsx'))
