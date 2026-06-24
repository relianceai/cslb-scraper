#!/usr/bin/env python3
"""
CSLB License Personnel Scraper - XLSX Integration
Reads licenses from XLSX files, scrapes personnel data, writes results back
"""

import asyncio
import pandas as pd
import re
import time
import glob
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

SEARCH_URL = "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx"

def extract_names_from_html(html):
    """Extract personnel names from HTML content"""
    names = []

    try:
        soup = BeautifulSoup(html, 'html.parser')
        tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text().strip()
                    value = cells[1].get_text().strip()

                    if label == 'Name' and value:
                        value = re.sub(r'\s+', ' ', value).strip()
                        if (len(value) > 3 and
                            ' ' in value and
                            re.match(r'^[A-Z]', value) and
                            re.match(r'^[A-Za-z\s\-\']+$', value) and
                            len(value.split()) >= 2 and
                            value not in names):
                            names.append(value)

        unique_names = []
        seen = set()
        for name in names:
            if name not in seen:
                seen.add(name)
                unique_names.append(name)

        return unique_names

    except Exception as e:
        return names

async def scrape_license(page, license_num):
    """Scrape a single license for personnel data"""
    try:
        await page.goto(SEARCH_URL, wait_until="load", timeout=30000)
        await page.wait_for_timeout(500)

        await page.fill("#MainContent_LicNo", str(license_num))
        await page.click("#MainContent_Contractor_License_Number_Search")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(1000)

        try:
            await page.click("#MainContent_PersonnelLink", timeout=10000)
            await page.wait_for_timeout(1000)
        except:
            pass

        content = await page.content()
        names = extract_names_from_html(content)

        return names if names else []

    except Exception as e:
        return []

async def process_xlsx_file(file_path, output_path=None):
    """Process a single XLSX file: read licenses, scrape, add columns, save"""

    if output_path is None:
        output_path = file_path

    file_name = Path(file_path).name
    print(f"\n{'='*60}")
    print(f"Processing: {file_name}")
    print(f"{'='*60}")

    # Read XLSX
    print(f"Reading XLSX...")
    df = pd.read_excel(file_path)
    total_rows = len(df)
    print(f"Loaded {total_rows} licenses")

    # Add new columns if they don't exist
    if 'first_name' not in df.columns:
        df['first_name'] = ''
    if 'last_name' not in df.columns:
        df['last_name'] = ''

    # Track progress
    processed = 0
    failed = 0
    start_time = datetime.now()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page()

        for idx, row in df.iterrows():
            license_num = row['LicenseNumber']

            # Skip if already processed
            if pd.notna(row['first_name']) and row['first_name'] != '':
                processed += 1
                continue

            try:
                names = await scrape_license(page, license_num)

                if names:
                    # Use first name found
                    full_name = names[0]
                    parts = full_name.split(None, 1)
                    df.at[idx, 'first_name'] = parts[0] if len(parts) > 0 else ''
                    df.at[idx, 'last_name'] = parts[1] if len(parts) > 1 else ''
                    status = f"✓ {len(names)} name(s)"
                else:
                    df.at[idx, 'first_name'] = 'NO_DATA'
                    df.at[idx, 'last_name'] = ''
                    status = "⚠ No data found"

                processed += 1

                # Print progress every 50 licenses or on first/last
                if (idx + 1) % 50 == 0 or idx == 0 or idx == total_rows - 1:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = (idx + 1) / elapsed if elapsed > 0 else 0
                    remaining = (total_rows - idx - 1) / rate if rate > 0 else 0

                    print(f"[{idx+1:5d}/{total_rows:5d}] {license_num:8s} {status:25s} "
                          f"({rate:.1f}/sec, ~{remaining/3600:.1f}h remaining)")

            except Exception as e:
                df.at[idx, 'first_name'] = f'ERROR'
                df.at[idx, 'last_name'] = ''
                failed += 1
                processed += 1

        await browser.close()

    # Save results
    print(f"\nSaving results to {Path(output_path).name}...")
    df.to_excel(output_path, index=False)

    elapsed = (datetime.now() - start_time).total_seconds()
    print(f"✓ Completed in {elapsed/3600:.1f} hours")
    print(f"  Processed: {processed}")
    print(f"  Failed: {failed}")

    return df

async def main():
    print(f"\n{'='*60}")
    print(f"CSLB License Personnel Scraper - XLSX Batch Processing")
    print(f"{'='*60}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Find all XLSX files (excluding any that might be outputs)
    files = sorted(glob.glob('/tmp/cslb-scraper/*.xlsx'))
    files = [f for f in files if 'CSLBSearchData' in f]  # Only process original files

    print(f"Found {len(files)} XLSX files to process")
    print(f"Total licenses: {sum(len(pd.read_excel(f)) for f in files):,}\n")

    # Process each file
    for file_path in files:
        try:
            await process_xlsx_file(file_path)
        except Exception as e:
            print(f"✗ Error processing {Path(file_path).name}: {e}")

    print(f"\n{'='*60}")
    print(f"All files completed!")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
