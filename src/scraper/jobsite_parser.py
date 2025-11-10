import time
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

from .utils import fetch_html, clean_text, make_absolute_url, parse_date

class JobSiteParser:
    """
    Generic parser for UK/IE job boards like totaljobs.com, cwjobs.co.uk, careerstructure.com,
    caterer.com, nijobs.com, irishjobs.ie, etc.
    Tries multiple selectors to be resilient across templates.
    """

    SEARCH_PATHS = [
        "/search?{qs}",
        "/jobs?{qs}",
        "/jobs/search/?{qs}",
    ]

    CARD_ANCHOR_SELECTORS = [
        "a[href*='/job/']",
        "a[href*='/jobs/']",
        "a.result-job__title",
        "a.job-card__title",
    ]

    TITLE_SELECTORS = [
        ".job-title, .job-card__title, h2, h3",
    ]
    COMPANY_SELECTORS = [
        ".job-card__company, .company, [data-company]",
    ]
    LOCATION_SELECTORS = [
        ".location, .job-card__location, [data-location]",
    ]
    SALARY_SELECTORS = [
        ".salary, .job-card__salary, [data-salary]",
    ]
    DATE_SELECTORS = [
        "time[datetime], time, .date, .posted",
    ]

    def _build_search_urls(self, domain: str, query: str, location: str, max_pages: int) -> List[str]:
        urls: List[str] = []
        for path in self.SEARCH_PATHS:
            for page in range(1, max_pages + 1):
                qp = {"q": query or "", "where": location or "", "page": page}
                qs = urlencode({k: v for k, v in qp.items() if v})
                urls.append(f"https://{domain}{path.format(qs=qs)}")
        # unique
        seen = set()
        unique = []
        for u in urls:
            if u not in seen:
                unique.append(u)
                seen.add(u)
        return unique

    def _extract_cards(self, soup):
        anchors = []
        for sel in self.CARD_ANCHOR_SELECTORS:
            anchors.extend(soup.select(sel))
        # unique by href
        uniq, seen = [], set()
        for a in anchors:
            href = a.get("href") or ""
            if not href or href in seen:
                continue
            seen.add(href)
            uniq.append(a)
        return uniq

    def _parse_card(self, a, base_url: str) -> Dict[str, Any]:
        job_url = make_absolute_url(base_url, a.get("href") or "")
        root = a.find_parent(["article", "li", "div"]) or a

        def first_text(selectors):
            for sel in selectors:
                node = root.select_one(sel)
                if node and node.get_text(strip=True):
                    return clean_text(node.get_text())
            # fallback to anchor text
            return clean_text(a.get_text())

        title = first_text(self.TITLE_SELECTORS)
        company = first_text(self.COMPANY_SELECTORS)
        location = first_text(self.LOCATION_SELECTORS)
        salary = first_text(self.SALARY_SELECTORS)
        dt = ""
        for sel in self.DATE_SELECTORS:
            el = root.select_one(sel)
            if el:
                dt = parse_date(el.get("datetime") or el.get_text(strip=True))
                break

        return {
            "jobTitle": title,
            "companyName": company,
            "location": location,
            "jobUrl": job_url,
            "jobDescription": "",
            "salary": salary,
            "employmentType": "",
            "datePosted": dt,
            "category": "",
            "experienceLevel": "",
            "source": base_url,
        }

    def _enrich_detail(self, record: Dict[str, Any]) -> Dict[str, Any]:
        html, soup, _ = fetch_html(record["jobUrl"])
        if not soup:
            return record
        desc_sel = [
            ".job-description, .description, article, [data-description]",
        ]
        for sel in desc_sel:
            el = soup.select_one(sel)
            if el:
                record["jobDescription"] = clean_text(el.get_text(separator="\n"))
                break

        # Employment type + experience heuristics
        blob = (html or "").lower()
        for hint in ("full-time", "part-time", "contract", "temporary", "permanent"):
            if hint in blob:
                record["employmentType"] = hint.title()
                break
        for hint in ("junior", "mid", "senior", "lead"):
            if hint in blob:
                record["experienceLevel"] = hint.title()
                break
        return record

    def search_and_collect(
        self,
        domain: str,
        query: str = "",
        location: str = "",
        max_pages: int = 1,
        request_conf: Optional[dict] = None,
        throttle: float = 1.0,
    ) -> List[Dict[str, Any]]:
        base = f"https://{domain}"
        results: List[Dict[str, Any]] = []
        urls = self._build_search_urls(domain, query, location, max_pages)

        for url in urls:
            _, soup, status = fetch_html(url, request_conf=request_conf)
            if soup is None or status >= 400:
                time.sleep(throttle)
                continue
            for a in self._extract_cards(soup):
                rec = self._parse_card(a, base)
                try:
                    rec = self._enrich_detail(rec)
                except Exception:
                    pass
                results.append(rec)
                time.sleep(throttle)

        return results