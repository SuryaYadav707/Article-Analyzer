# analyzer.py

import os
import json
import re
import asyncio
import logging
import platform
import random
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define categories and keywords for classification
CATEGORY_LIST = [
    "About Us", "Products & Services", "Leadership/Team",
    "Blog/News/Press Release", "Contact/Support",
    "Privacy/Legal", "Careers/Jobs", "Other"
]

CATEGORY_KEYWORDS = {
    "About Us": ["about us", "our story", "who we are"],
    "Products & Services": ["product", "service", "solution"],
    "Leadership/Team": ["our team", "leadership", "ceo", "founder"],
    "Blog/News/Press Release": ["blog", "news", "press"],
    "Contact/Support": ["contact", "support", "help", "reach"],
    "Privacy/Legal": ["privacy", "terms", "policy"],
    "Careers/Jobs": ["career", "job", "hiring"],
    "Other": []
}

# Rate limit handler to manage API requests
class RateLimitHandler:
    def __init__(self, max_requests_per_minute=10, max_backoff_seconds=60):
        self.max_requests_per_minute = max_requests_per_minute
        self.requests_timestamps = []
        self.quota_exceeded = False
        self.quota_reset_time = None
        self.max_backoff = max_backoff_seconds
        self.error_count = 0

    async def wait_if_needed(self):
        now = datetime.now()

        if self.quota_exceeded and self.quota_reset_time:
            if now < self.quota_reset_time:
                wait_time = (self.quota_reset_time - now).total_seconds()
                logger.warning(f"Quota exceeded. Waiting {wait_time:.0f}s...")
                await asyncio.sleep(wait_time)
            else:
                self.quota_exceeded = False
                self.quota_reset_time = None

        cutoff = now - timedelta(seconds=60)
        self.requests_timestamps = [t for t in self.requests_timestamps if t > cutoff]

        if len(self.requests_timestamps) >= self.max_requests_per_minute:
            oldest = min(self.requests_timestamps)
            wait_time = 60 - (now - oldest).total_seconds()
            if wait_time > 0:
                logger.warning(f"Rate limit hit. Waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)

    def record_request(self):
        self.requests_timestamps.append(datetime.now())
        self.reset_backoff()

    def handle_quota_error(self, retry_delay_seconds=None):
        self.quota_exceeded = True
        self.quota_reset_time = datetime.now() + timedelta(
            seconds=retry_delay_seconds if retry_delay_seconds else 3600
        )
        logger.error(f"Quota error: cooling off until {self.quota_reset_time}")

    async def backoff(self):
        delay = min(2 ** self.error_count + random.uniform(0, 1), self.max_backoff)
        logger.warning(f"Transient failure. Backing off for {delay:.1f}s...")
        await asyncio.sleep(delay)
        self.error_count += 1

    def reset_backoff(self):
        self.error_count = 0

# Define the main analyzer class
class Analyzer:
    def __init__(self, rate_limit: int = 5):
        self.rate_limiter = RateLimitHandler(rate_limit)
        load_dotenv()
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("Missing GEMINI_API_KEY in .env")
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=key)
        self.browser = None
        self.context = None

    async def start_browser(self):
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(headless=True)
        self.context = await self.browser.new_context()

    async def close_browser(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
     
    async def validate_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in ["http", "https"]

     # Extract a snippet from the HTML based on category keywords
    def extract_snippet(self, html: str, category: str) -> str:
        soup = BeautifulSoup(html, 'html.parser')
        keywords = CATEGORY_KEYWORDS.get(category, [])

        # Primary method: use semantic headings
        for heading in soup.find_all(['h1', 'h2', 'h3']):
            heading_text = heading.get_text(" ", strip=True).lower()
            if any(kw in heading_text for kw in keywords):
                snippet = " ".join(p.get_text(" ", strip=True) for p in heading.find_all_next(['p', 'div'], limit=3))
                return snippet[:500]

        #  Fallback 1: article tag
        article = soup.find('article')
        if article:
            text = article.get_text(" ", strip=True)
            if any(kw in text.lower() for kw in keywords):
                return text[:500]

        # Fallback 2: main tag
        main = soup.find('main')
        if main:
            text = main.get_text(" ", strip=True)
            if any(kw in text.lower() for kw in keywords):
                return text[:500]

        # Fallback 3: common div classes
        for cls in ['post-content', 'entry-content', 'article-body', 'content']:
            div = soup.find('div', class_=cls)
            if div:
                text = div.get_text(" ", strip=True)
                if any(kw in text.lower() for kw in keywords):
                    return text[:500]

        return ""

    # Associate links based on category keywords
    async def associate_links(self, page: Page, base_url: str, category: str) -> List[str]:
        try:
            anchors = await page.query_selector_all('a[href]')
            matches = []
            domain = urlparse(base_url).netloc
            keywords = CATEGORY_KEYWORDS.get(category, [])

            for a in anchors:
                href = await a.get_attribute('href')
                text = (await a.inner_text()).lower() if a else ""
                if not href:
                    continue
                abs_url = urljoin(base_url, href)
                parsed = urlparse(abs_url)
                if parsed.netloc and parsed.netloc != domain:
                    continue
                full_text = href.lower() + " " + text
                if any(kw in full_text for kw in keywords):
                    matches.append(abs_url)

            return list(dict.fromkeys(matches))[:5]
        except Exception as e:
            logger.warning(f"Anchor match error: {e}")
            return []
        
    # Get categories from the text using LLM
    async def get_categories(self, text: str) -> List[Dict[str, str]]:
        for attempt in range(3):
            await self.rate_limiter.wait_if_needed()
            
            prompt = f"""
            Given the following content, extract matching categories from this list:
            {', '.join(CATEGORY_LIST)}
            Return JSON: [{{"category_name": "...", "text": ""}}]
            Content: {text[:3000]}
            """
            
            try:
                logger.info(f"[LLM CALL][Categories] Attempt {attempt+1}")
                response = await asyncio.to_thread(self.llm.invoke, [HumanMessage(content=prompt)])
                self.rate_limiter.record_request()
                logger.debug(f"[LLM Response] {response.content.strip()}")
                match = re.search(r"\[.*\]", response.content.strip(), re.DOTALL)
                return json.loads(match.group()) if match else []
            except Exception as e:
                logger.warning(f"LLM error in get_categories: {e}")
                await self.rate_limiter.backoff()
        return []

    # Get the site type based on content analysis
    async def get_site_type(self, text: str) -> str:
        for attempt in range(3):
            await self.rate_limiter.wait_if_needed()
            prompt = f"""
            Classify this site into one: [blog, news, company, ecommerce, portfolio, forum, educational, medical, other]
            Return JSON: {{"site_type": "..."}}
            Content: {text[:3000]}
            """
            try:
                logger.info(f"[LLM CALL][SiteType] Attempt {attempt+1}")
                response = await asyncio.to_thread(self.llm.invoke, [HumanMessage(content=prompt)])
                self.rate_limiter.record_request()
                logger.debug(f"[LLM Response] {response.content.strip()}")
                match = re.search(r"\{.*\}", response.content.strip(), re.DOTALL)
                return json.loads(match.group()).get("site_type", "other") if match else "other"
            except Exception as e:
                logger.warning(f"LLM error in get_site_type: {e}")
                await self.rate_limiter.backoff()
        return "other"

    async def analyze_url(self, url: str) -> Dict[str, Any]:
        try:
            if not await self.validate_url(url):
                return {"URL": url, "site_type": "other", "extracted_web_content": "", "content": [], "errors": "Invalid URL"}

            page = await self.context.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(2000)
            final_url = page.url
            html = await page.content()

            soup = BeautifulSoup(html, 'html.parser')
            for tag in ["script", "style", "nav", "footer", "aside"]:
                for el in soup.find_all(tag): el.decompose()
            text = soup.get_text(" ", strip=True)
            text = re.sub(r"\s+", " ", text)

            categories = await self.get_categories(text)
            site_type = await self.get_site_type(text)

            structured_content = []
            for cat in categories:
                name = cat["category_name"]
                snippet = self.extract_snippet(html, name)
                links = await self.associate_links(page, final_url, name)
                if snippet or links:
                    structured_content.append({name: {"text": snippet, "links": links}})

            await page.close()

            return {
                "URL": final_url,
                "site_type": site_type,
                "extracted_web_content": text,
                "content": structured_content,
                "errors": None
            }

        except Exception as e:
            return {"URL": url, "site_type": "other", "extracted_web_content": "", "content": [], "errors": str(e)}


def load_urls(filepath: Optional[str]) -> List[str]:
    if filepath and os.path.exists(filepath):
        with open(filepath) as f:
            return [l.strip() for l in f if l.strip()]
    return [
        "https://www.techcrunch.com",
        "https://www.healthline.com",
        "https://www.tesla.com",
        "https://www.nike.com",
        "https://www.zendesk.com",
        "https://www.ibm.com",
        "https://www.adobe.com",
        "https://www.intel.com",
        "https://www.forbes.com",
        "https://www.udemy.com"
        
    ]

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Input file with URLs")
    parser.add_argument("-o", "--output", default="results.json")
    parser.add_argument("--rate", type=int, default=5)
    args = parser.parse_args()

    analyzer = Analyzer(rate_limit=args.rate)
    await analyzer.start_browser()
    urls = load_urls(args.file)

    logger.info(f"Starting analysis of {len(urls)} URLs...")
    results = []

    for i, url in enumerate(urls):
        logger.info(f"Processing URL {i+1}/{len(urls)}: {url}")
        result = await analyzer.analyze_url(url)
        results.append(result)
        await asyncio.sleep(2)

    await analyzer.close_browser()

    # Save results to file
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary and results
    success_count = sum(1 for r in results if not r["errors"])
    failure_count = len(results) - success_count

    print("\n" + "="*80)
    print("ANALYSIS RESULTS")
    print("="*80)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    logger.info(f"\nAnalysis complete. {success_count} succeeded, {failure_count} failed.")

if __name__ == "__main__":
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
