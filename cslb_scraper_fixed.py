#!/usr/bin/env python3
"""
CSLB License Personnel Scraper (Corrected)
Properly follows the search flow and extracts personnel names
"""

import asyncio
import csv
import re
import time
from datetime import datetime
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# Test licenses
LICENSES = [
    "1025605",
    "1007876",
    "960675",
    "985481",
    "188225",
    "196928",
    "1018574",
    "220289",
    "246673",
    "1026958"
]

SEARCH_URL = "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx"

async def scrape_license(page, license_num):
    """Scrape a single license for personnel data"""
    try:
        # Go to search page
        print(f"  → Loading search page...")
        await page.goto(SEARCH_URL, wait_until="load", timeout=30000)
        await page.wait_for_timeout(1000)

        # Fill license number
        print(f"  → Entering license number...")
        await page.fill("#MainContent_LicNo", license_num)

        # Click search
        print(f"  → Clicking search...")
        await page.click("#MainContent_Contractor_License_Number_Search")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # Click Personnel List button
        print(f"  → Clicking Personnel List button...")
        try:
            await page.click("#MainContent_PersonnelLink", timeout=10000)
            await page.wait_for_timeout(2000)
            print(f"    → Personnel List opened")
        except Exception as e:
            print(f"  ⚠ Could not click Personnel List: {str(e)}")

        # Get page content
        content = await page.content()

        # Extract personnel names
        names = extract_names_from_html(content)

        if names:
            print(f"  ✓ Found {len(names)} personnel name(s)")
        else:
            print(f"  ⚠ No names found on page")

        return names

    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
        return []

def extract_names_from_html(html):
    """Extract personnel names from HTML content"""
    names = []

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # Look for tables containing personnel data
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')

            # Look for pattern: "Name" label in first cell, actual name in second cell
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    label = cells[0].get_text().strip()
                    value = cells[1].get_text().strip()

                    # Check if this is a "Name" row
                    if label == 'Name' and value:
                        # Clean up the value (remove extra whitespace)
                        value = re.sub(r'\s+', ' ', value).strip()

                        # Check if value looks like a person's name
                        # Should be 2+ words, start with capital, contain mostly letters/spaces
                        if (len(value) > 3 and
                            ' ' in value and  # Has at least one space
                            re.match(r'^[A-Z]', value) and  # Starts with capital
                            re.match(r'^[A-Za-z\s\-\']+$', value) and  # Only letters, spaces, hyphens, apostrophes
                            len(value.split()) >= 2 and  # At least 2 words
                            value not in names):  # Not duplicate

                            names.append(value)

        # Remove duplicates while preserving order
        unique_names = []
        seen = set()
        for name in names:
            if name not in seen:
                seen.add(name)
                unique_names.append(name)

        return unique_names[:20]  # Return top 20 names

    except Exception as e:
        print(f"    Parse error: {str(e)}")
        return names

async def main():
    print(f"\n{'='*60}")
    print(f"CSLB License Personnel Scraper (Fixed)")
    print(f"{'='*60}")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Processing {len(LICENSES)} licenses\n")

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page()

        for i, license_num in enumerate(LICENSES, 1):
            print(f"[{i}/{len(LICENSES)}] License {license_num}")

            try:
                names = await scrape_license(page, license_num)

                if names:
                    for name in names:
                        parts = name.split(None, 1)
                        first_name = parts[0] if len(parts) > 0 else ""
                        last_name = parts[1] if len(parts) > 1 else ""

                        results.append({
                            "license_number": license_num,
                            "full_name": name,
                            "first_name": first_name,
                            "last_name": last_name
                        })
                else:
                    results.append({
                        "license_number": license_num,
                        "full_name": "NO_DATA_FOUND",
                        "first_name": "",
                        "last_name": ""
                    })

            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
                results.append({
                    "license_number": license_num,
                    "full_name": f"ERROR: {str(e)}",
                    "first_name": "",
                    "last_name": ""
                })

            print()

        await browser.close()

    # Write results to CSV
    output_file = "cslb_personnel_results.csv"
    try:
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["license_number", "full_name", "first_name", "last_name"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print(f"{'='*60}")
        print(f"✓ Results written to: {output_file}")
        print(f"  Total records: {len(results)}")
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    except Exception as e:
        print(f"✗ Error writing CSV: {str(e)}")
        return 1

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
