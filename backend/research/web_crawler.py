"""
research/web_crawler.py
─────────────────────────────────────────────────────────────────────────────
Async Research Agent for Intelli-Credit.

Sources crawled (in order of reliability):
  1. Google News RSS    — Company name search (no API key needed)
  2. MCA21 Portal       — Company master + filings (best effort)
  3. eCourts India      — Case search by company name / CIN (best effort)
  4. BSE India          — Corporate announcements (best effort)

Demo Strategy (CRITICAL for hackathon):
  - ALWAYS attempt live crawl first
  - If any source fails → fall back to pre-cached data from research_cache.json
  - Cache results to research/cache/ directory to avoid repeated crawls
  - The demo NEVER crashes due to network failures

Architecture:
  - Fully async (httpx + asyncio)
  - 10s timeout per source
  - Results scored immediately by news_scorer.py
  - Persisted to research_results table by research_routes.py
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not installed. Live crawling disabled — using cache only.")

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    logger.warning("feedparser not installed. News RSS crawling disabled.")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from config import settings
from research.news_scorer import (
    score_text, score_mca_filing, score_ecourt_case,
    aggregate_scores, ScoredArticle
)


# ── Cache directory ────────────────────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Request headers to avoid bot detection
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

HTTP_TIMEOUT = 10   # seconds per source


# ── Result container ───────────────────────────────────────────────────────────

@dataclass
class ResearchAgentResult:
    """Complete output of one research agent run."""
    company_name:   str
    cin:            str
    run_timestamp:  str
    articles:       list[ScoredArticle]
    aggregate:      dict
    sources_tried:  list[str]
    sources_failed: list[str]
    used_cache:     bool
    warnings:       list[str] = field(default_factory=list)


# ── Main Entry Point ──────────────────────────────────────────────────────────

async def run_research_agent(
    company_name: str,
    cin:          str,
    pan:          str = "",
    use_cache:    bool = True,
    demo_fallback_path: Optional[Path] = None,
) -> ResearchAgentResult:
    """
    Run the full research agent pipeline.

    Args:
        company_name:       Company name for search queries
        cin:                Corporate Identification Number
        pan:                PAN (used for GST/tax queries)
        use_cache:          If True, check cache before live crawl
        demo_fallback_path: Path to research_cache.json (fallback)
    """
    logger.info("Research agent starting: %s (CIN=%s)", company_name, cin)

    # ── Check cache first ──────────────────────────────────────────────────────
    if use_cache:
        cached = _load_from_cache(cin or company_name)
        if cached:
            logger.info("Research: using cached result for %s", company_name)
            return cached

    articles       = []
    sources_tried  = []
    sources_failed = []
    warnings       = []

    # ── Live crawl (best effort — each source independent) ────────────────────
    if HTTPX_AVAILABLE:
        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=httpx.Timeout(HTTP_TIMEOUT),
            follow_redirects=True,
        ) as client:

            # 1. Google News RSS
            sources_tried.append("google_news_rss")
            try:
                news = await _crawl_google_news(client, company_name)
                articles.extend(news)
                logger.info("Google News: %d articles found", len(news))
            except Exception as e:
                sources_failed.append("google_news_rss")
                warnings.append(f"Google News crawl failed: {e}")

            # 2. MCA21 Portal
            sources_tried.append("mca21")
            try:
                mca = await _crawl_mca(client, company_name, cin)
                articles.extend(mca)
                logger.info("MCA21: %d filings found", len(mca))
            except Exception as e:
                sources_failed.append("mca21")
                warnings.append(f"MCA crawl failed: {e}")

            # 3. BSE India
            sources_tried.append("bse_india")
            try:
                bse = await _crawl_bse(client, company_name)
                articles.extend(bse)
                logger.info("BSE: %d disclosures found", len(bse))
            except Exception as e:
                sources_failed.append("bse_india")
                warnings.append(f"BSE crawl failed: {e}")

    else:
        sources_failed.append("all_live_sources")
        warnings.append("httpx not installed — live crawl unavailable")

    # ── Demo fallback: load from research_cache.json if crawl empty ───────────
    used_cache = False
    if len(articles) == 0 and demo_fallback_path and demo_fallback_path.exists():
        logger.info("Live crawl empty — loading demo fallback cache")
        articles, warnings_cache = _load_demo_cache(demo_fallback_path)
        warnings.extend(warnings_cache)
        used_cache = True

    # ── Aggregate & cache ─────────────────────────────────────────────────────
    aggregate = aggregate_scores(articles)

    result = ResearchAgentResult(
        company_name=company_name,
        cin=cin,
        run_timestamp=datetime.now(timezone.utc).isoformat(),
        articles=articles,
        aggregate=aggregate,
        sources_tried=sources_tried,
        sources_failed=sources_failed,
        used_cache=used_cache,
        warnings=warnings,
    )

    # Save to cache
    _save_to_cache(cin or company_name, result)

    logger.info(
        "Research complete: %d articles | delta=%d | label=%s | cache=%s",
        len(articles),
        aggregate.get("total_risk_delta", 0),
        aggregate.get("overall_research_risk_label", "?"),
        used_cache,
    )
    return result


# ── Source Crawlers ───────────────────────────────────────────────────────────

async def _crawl_google_news(
    client: "httpx.AsyncClient",
    company_name: str,
) -> list[ScoredArticle]:
    """
    Crawl Google News RSS feed for company mentions.
    No API key needed — public RSS endpoint.
    """
    if not FEEDPARSER_AVAILABLE:
        return []

    query = f'"{company_name}" (NCLT OR litigation OR default OR rating OR pledge)'
    url   = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"

    try:
        response = await client.get(url)
        response.raise_for_status()
        feed     = feedparser.parse(response.text)
    except Exception as e:
        logger.warning("Google News RSS failed: %s", e)
        return []

    articles = []
    for entry in feed.entries[:15]:   # Max 15 articles
        title       = entry.get("title", "")
        summary     = entry.get("summary", "")
        link        = entry.get("link", "")
        published   = entry.get("published", "")

        scored = score_text(
            title=title,
            body=summary,
            url=link,
            source_name="Google News",
            published_date=published[:10] if published else None,
            result_type="news_article",
            is_cached=False,
        )

        # Only include if relevant (risk score != 0 or mentions company)
        if (scored.risk_score_delta != 0 or
                company_name.lower()[:10] in title.lower()):
            articles.append(scored)

    return articles


async def _crawl_mca(
    client: "httpx.AsyncClient",
    company_name: str,
    cin: str,
) -> list[ScoredArticle]:
    """
    Crawl MCA21 portal for company filings.
    MCA provides a public company search API.
    """
    articles = []

    # MCA public search endpoint
    search_url = (
        f"https://www.mca.gov.in/mcafoportal/viewCompanyMasterData.do"
        f"?cin={cin}"
    )

    try:
        response = await client.get(search_url)
        if response.status_code == 200 and BS4_AVAILABLE:
            soup = BeautifulSoup(response.text, "html.parser")
            # Extract filing data from HTML table
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows[1:]:
                    cells = row.find_all("td")
                    if len(cells) >= 3:
                        form_type   = cells[0].get_text(strip=True)
                        description = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        date_str    = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                        if form_type in ("AOC-4", "CHG-1", "CHG-9", "MGT-7", "ADT-1"):
                            scored = score_mca_filing(
                                form_type=form_type,
                                description=description,
                                filing_date=date_str,
                                url=search_url,
                                risk_flag=(form_type in ("CHG-1", "CHG-9")),
                                is_cached=False,
                            )
                            articles.append(scored)

    except Exception as e:
        logger.warning("MCA crawl failed: %s", e)

    return articles


async def _crawl_bse(
    client: "httpx.AsyncClient",
    company_name: str,
) -> list[ScoredArticle]:
    """
    Crawl BSE India for corporate announcements.
    BSE has a public search API for announcements.
    """
    articles = []

    # BSE corporate announcements search
    url = (
        "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
        f"?pageno=1&strCat=-1&strPrevDate=&strScrip=&strSearch=P&strToDate=&strType=C"
        f"&subcategory=-1&company={company_name[:30]}"
    )

    try:
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()
            for item in (data.get("Table", []))[:10]:
                headline  = item.get("HEADLINE", "")
                scrip     = item.get("SCRIP_CD", "")
                news_date = item.get("NEWS_DT", "")

                scored = score_text(
                    title=headline,
                    body=headline,
                    url=f"https://www.bseindia.com/xml-data/corpfiling/AttachHis/{scrip}",
                    source_name="BSE India",
                    published_date=news_date[:10] if news_date else None,
                    result_type="bse_disclosure",
                    is_cached=False,
                )
                if scored.risk_score_delta != 0:
                    articles.append(scored)

    except Exception as e:
        logger.warning("BSE crawl failed: %s", e)

    return articles


# ── Demo Cache Loader ─────────────────────────────────────────────────────────

def _load_demo_cache(cache_path: Path) -> tuple[list[ScoredArticle], list[str]]:
    """
    Load the pre-built Acme Textiles research cache and convert to ScoredArticles.
    This is the guaranteed demo fallback.
    """
    warnings = []
    articles = []

    try:
        with open(cache_path) as f:
            data = json.load(f)
    except Exception as e:
        return [], [f"Failed to load demo cache: {e}"]

    # News articles
    for item in data.get("news_articles", []):
        scored = score_text(
            title=item.get("title", ""),
            body=item.get("summary", item.get("title", "")),
            url=item.get("url", ""),
            source_name=item.get("source", "Cached"),
            published_date=item.get("date"),
            result_type="news_article",
            is_cached=True,
        )
        # Override with pre-computed tier/delta from cache (more accurate)
        if item.get("risk_tier"):
            scored.risk_tier        = item["risk_tier"]
        if item.get("risk_score_delta") is not None:
            scored.risk_score_delta = item["risk_score_delta"]
        articles.append(scored)

    # MCA filings
    for item in data.get("mca_filings", []):
        scored = score_mca_filing(
            form_type=item.get("form", ""),
            description=item.get("description", ""),
            filing_date=item.get("filed_date"),
            url=item.get("url", ""),
            risk_flag=item.get("risk_flag", False),
            notes=item.get("notes", ""),
            is_cached=True,
        )
        articles.append(scored)

    # eCourts findings
    for item in data.get("ecourts_findings", []):
        scored = score_ecourt_case(
            case_type=item.get("case_type", ""),
            case_number=item.get("case_number", ""),
            court=item.get("court", ""),
            status=item.get("status", "Pending"),
            amount_cr=float(item.get("amount_cr", 0) or 0),
            risk_tier=item.get("risk_tier", 3),
            url=item.get("url", ""),
            is_cached=True,
        )
        articles.append(scored)

    warnings.append(
        "Live crawl unavailable — research data loaded from pre-cached demo dataset."
    )
    return articles, warnings


# ── File-based Cache ──────────────────────────────────────────────────────────

def _cache_key(identifier: str) -> str:
    return hashlib.md5(identifier.lower().encode()).hexdigest()[:12]


def _load_from_cache(identifier: str) -> Optional[ResearchAgentResult]:
    """Load a previous crawl result from the file cache."""
    cache_file = CACHE_DIR / f"{_cache_key(identifier)}.json"
    if not cache_file.exists():
        return None

    try:
        with open(cache_file) as f:
            data = json.load(f)

        # Only use cache if less than 24 hours old
        run_ts = datetime.fromisoformat(data.get("run_timestamp", "2000-01-01"))
        age_hours = (datetime.now(timezone.utc) - run_ts.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        if age_hours > 24:
            logger.info("Research cache expired (%.1f hrs old)", age_hours)
            return None

        # Reconstruct ScoredArticles
        articles = []
        for a in data.get("articles", []):
            articles.append(ScoredArticle(
                title=a["title"], url=a["url"],
                source_name=a["source_name"],
                published_date=a.get("published_date"),
                raw_text=a.get("raw_text", ""),
                result_type=a["result_type"],
                risk_tier=a.get("risk_tier"),
                risk_score_delta=a.get("risk_score_delta", 0),
                matched_keywords=a.get("matched_keywords", []),
                is_cached=True,
            ))

        return ResearchAgentResult(
            company_name=data["company_name"],
            cin=data["cin"],
            run_timestamp=data["run_timestamp"],
            articles=articles,
            aggregate=data["aggregate"],
            sources_tried=data.get("sources_tried", []),
            sources_failed=data.get("sources_failed", []),
            used_cache=True,
            warnings=["Loaded from file cache"],
        )
    except Exception as e:
        logger.warning("Cache load failed: %s", e)
        return None


def _save_to_cache(identifier: str, result: ResearchAgentResult) -> None:
    """Save crawl result to file cache."""
    cache_file = CACHE_DIR / f"{_cache_key(identifier)}.json"
    try:
        data = {
            "company_name":   result.company_name,
            "cin":            result.cin,
            "run_timestamp":  result.run_timestamp,
            "aggregate":      result.aggregate,
            "sources_tried":  result.sources_tried,
            "sources_failed": result.sources_failed,
            "articles": [
                {
                    "title":            a.title,
                    "url":              a.url,
                    "source_name":      a.source_name,
                    "published_date":   a.published_date,
                    "raw_text":         a.raw_text[:500],
                    "result_type":      a.result_type,
                    "risk_tier":        a.risk_tier,
                    "risk_score_delta": a.risk_score_delta,
                    "matched_keywords": a.matched_keywords,
                }
                for a in result.articles
            ],
        }
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning("Cache save failed: %s", e)


def result_to_dict(result: ResearchAgentResult) -> dict:
    """Serialise ResearchAgentResult for API responses."""
    from research.news_scorer import scored_to_dict
    return {
        "company_name":   result.company_name,
        "cin":            result.cin,
        "run_timestamp":  result.run_timestamp,
        "used_cache":     result.used_cache,
        "sources_tried":  result.sources_tried,
        "sources_failed": result.sources_failed,
        "aggregate":      result.aggregate,
        "articles":       [scored_to_dict(a) for a in result.articles],
        "warnings":       result.warnings,
    }