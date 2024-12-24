import os
import logging
from playwright.async_api import async_playwright
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class KrispClient:
    """Client for interacting with Krisp.ai API using headless browser."""
    
    def __init__(self):
        """Initialize Krisp client."""
        self.browser_context = None
        self.playwright = None
        self.cookies = None
        logger.info("Krisp client initialized")

    def _parse_cookies(self, cookie_str: str) -> list:
        """Parse cookie string into list of cookie objects."""
        cookies = []
        for cookie in cookie_str.split(';'):
            if '=' in cookie:
                name, value = cookie.strip().split('=', 1)
                cookies.append({
                    'name': name,
                    'value': value,
                    'domain': '.krisp.ai',
                    'path': '/'
                })
        return cookies

    async def _init_browser(self):
        """Initialize headless browser with cookies."""
        if self.browser_context is None:
            try:
                self.playwright = await async_playwright().start()
                
                # Launch browser with cookies
                self.browser_context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir='',  # Empty string for temporary context
                    headless=True
                )
                logger.info("Browser context initialized")

                # Get cookies from environment
                cookie_str = os.getenv('KRISP_COOKIES')
                if not cookie_str:
                    raise Exception("KRISP_COOKIES environment variable not found")
                
                # Parse and set cookies
                self.cookies = self._parse_cookies(cookie_str)
                
                # Add cookies to context
                page = await self.browser_context.new_page()
                try:
                    # Set cookies for all relevant domains
                    for domain in ['app.krisp.ai', 'account.krisp.ai', 'krisp.ai']:
                        await self.browser_context.add_cookies([
                            {**cookie, 'domain': domain}
                            for cookie in self.cookies
                        ])
                    
                    # Verify authentication
                    logger.info("Verifying Krisp.ai authentication...")
                    await page.goto('https://app.krisp.ai', wait_until='networkidle')
                    
                    if 'login' in page.url or 'sign-up' in page.url:
                        raise Exception("Invalid or expired cookies. Please update KRISP_COOKIES in .env")
                    
                    logger.info("Successfully verified Krisp.ai authentication")
                finally:
                    await page.close()

            except Exception as e:
                if self.browser_context:
                    await self.browser_context.close()
                    self.browser_context = None
                if self.playwright:
                    await self.playwright.stop()
                    self.playwright = None
                raise Exception(f"Failed to initialize browser: {str(e)}")

    async def get_meeting_notes(self, url: str) -> Optional[Dict[str, Any]]:
        """Get meeting notes from Krisp.ai using headless browser with Chrome profile auth."""
        page = None
        try:
            await self._init_browser()
            page = await self.browser_context.new_page()
            
            logger.info(f"Navigating to meeting notes: {url}")
            response = await page.goto(url, wait_until='networkidle')
            
            if response.status == 401 or response.status == 403:
                raise Exception("Authentication failed or access forbidden")
            
            if 'login' in page.url or 'sign-up' in page.url:
                raise Exception(f"Lost authentication. Please ensure Chrome {self.profile} is logged in.")
            
            # Wait for content to load with increased timeout
            try:
                await page.wait_for_selector('.transcript-content', timeout=60000)
            except Exception as e:
                logger.error("Transcript content not found. Page content:")
                logger.error(await page.content())
                raise Exception("Failed to find transcript content on page") from e
            
            # Extract data using JavaScript evaluation
            data = await page.evaluate('''() => {
                const extractText = (selector) => {
                    const el = document.querySelector(selector);
                    return el ? el.innerText : '';
                };
                
                const extractActionItems = () => {
                    const items = [];
                    const messages = document.querySelectorAll('.message-content');
                    messages.forEach(message => {
                        const text = message.innerText.toLowerCase();
                        if (text.includes('action item') || 
                            text.includes('next step') || 
                            text.includes('follow up') || 
                            text.includes('todo')) {
                            items.push(message.innerText);
                        }
                    });
                    return items;
                };
                
                return {
                    summary: extractText('.summary-section'),
                    transcript: extractText('.transcript-content'),
                    actionItems: extractActionItems()
                };
            }''')
            
            await page.close()
            
            logger.info("Successfully extracted meeting notes")
            return {
                'summary': data['summary'].strip(),
                'action_items': [item.strip() for item in data['actionItems'] if item.strip()],
                'transcript': data['transcript'].strip()
            }
            
        except Exception as e:
            logger.error(f"Error fetching meeting notes: {e}")
            return None
        finally:
            if self.browser_context:
                await self.browser_context.close()
            if self.playwright:
                await self.playwright.stop()
