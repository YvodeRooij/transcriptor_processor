import os
import json
import asyncio
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_krisp_cookies():
    async with async_playwright() as p:
        try:
            # Launch browser in non-headless mode to use current Chrome session
            browser = await p.chromium.launch(
                headless=False,
                channel='chrome'
            )
            context = await browser.new_context()

            page = await context.new_page()

            try:
                logger.info("Please log in to Krisp.ai in the browser window that opens...")
                await page.goto('https://app.krisp.ai/login', wait_until='networkidle')
                
                # Wait for user to log in and reach meeting notes page
                await page.wait_for_url('**/meeting-notes', timeout=300000)  # 5 minute timeout
                logger.info("Successfully logged in!")

                # Wait for page to be fully loaded
                await asyncio.sleep(5)
                
                # Get all cookies
                all_cookies = await context.cookies()
                logger.info(f"Found {len(all_cookies)} cookies")
                
                # Filter for Krisp.ai cookies
                krisp_cookies = [c for c in all_cookies if '.krisp.ai' in c['domain']]
                logger.info(f"Found {len(krisp_cookies)} Krisp.ai cookies")

                # Format cookies for .env file
                cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in krisp_cookies])

                print("\n=== Add this to your .env file ===")
                print(f"KRISP_COOKIES='{cookie_str}'")
                print("================================\n")

                # Save full cookie details to file
                with open('krisp_cookies.json', 'w') as f:
                    json.dump(all_cookies, f, indent=2)
                logger.info("Saved cookies to krisp_cookies.json")

                # Try to access a meeting transcript to verify cookies
                logger.info("Cookies have been saved. They will be used with the headless browser approach.")

            except Exception as e:
                logger.error(f"Error during process: {e}")
            finally:
                await browser.close()

        except Exception as e:
            logger.error(f"Error launching browser: {e}")

if __name__ == "__main__":
    asyncio.run(get_krisp_cookies())
