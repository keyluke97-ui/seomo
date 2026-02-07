
import streamlit as st
from notion_bot import NotionBot
from scraper import scrape_jobs
from datetime import datetime, timedelta

# Mock secrets if not present (but they should be loaded by streamlit if run via streamlit, 
# but here we are running as script. We need to load secrets manually or rely on NotionBot reading them?)
# NotionBot reads st.secrets.
# When running as standalone script, st.secrets might not be populated unless we use specific loader or mock it.
# However, we updated secrets.toml.
# Let's try to load secrets manually for this test script.

import toml
import os

def load_secrets():
    secrets_path = ".streamlit/secrets.toml"
    if os.path.exists(secrets_path):
        return toml.load(secrets_path)
    return {}

secrets = load_secrets()

# Monkey patch st.secrets for the standalone run
# (NotionBot uses st.secrets.get)
class MockSecrets(dict):
    def __getattr__(self, key):
        return self.get(key)

st.secrets = MockSecrets(secrets)

def main():
    print("="*50)
    print("End-to-End Test: Scrape + Notion Save")
    print("="*50)

    # 1. Initialize NotionBot
    try:
        print("[1] Initializing NotionBot...")
        bot = NotionBot()
        print("   - Success")
    except Exception as e:
        print(f"   - Failed: {e}")
        return

    # 2. Scrape (Mock or Real)
    print("\n[2] Scraping 1 job (Real search)...")
    # Quick search for "Python"
    start = datetime.now()
    end = start + timedelta(days=30)
    
    # We will use '사람인' only for speed
    jobs = scrape_jobs(
        sources=["사람인"],
        keywords=["Python"],
        deadline_start=start,
        deadline_end=end,
        progress_callback=lambda x: print(f"   - Progress: {x*100:.0f}%", end="\r")
    )
    
    if not jobs:
        print("\n   - No jobs found. Creating a dummy job for test.")
        jobs = [{
            "title": "[TEST] End-to-End Test Job",
            "company": "Test Company",
            "url": "https://example.com/test_job",
            "deadline": "2026-12-31",
            "deadline_date": datetime(2026, 12, 31),
            "body": "This is a test job description."
        }]
    else:
        print(f"\n   - Found {len(jobs)} jobs. Using the first one.")
        jobs = jobs[:1] # Process only 1

    # 3. Save to Notion
    print(f"\n[3] Saving 1 job to Notion...")
    print(f"   - Job: {jobs[0]['title']}")
    
    result = bot.batch_create_jobs(jobs)
    
    print(f"\n[4] Result: {result}")
    
    if result["saved"] > 0:
        print("\n[SUCCESS] Job saved to Notion successfully!")
    elif result["skipped"] > 0:
        print("\n[SUCCESS] Job was skipped (Duplicate), but connection worked!")
    else:
        print("\n[FAIL] Failed to save job.")

if __name__ == "__main__":
    main()
