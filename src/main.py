import argparse
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any

from scraper.stepstone_parser import StepstoneParser
from scraper.jobsite_parser import JobSiteParser
from scraper.utils import load_json, ensure_dir, unique_by_key, chunked
from outputs.exporters import export_json, export_csv, export_excel

PARSERS = {
    "stepstone": StepstoneParser(),
    "jobsite": JobSiteParser(),  # generic parser for non-stepstone-network sites
}

def pick_parser_for_site(site: str):
    site_l = site.lower()
    if "stepstone" in site_l or site_l.endswith(".be") or site_l.endswith(".nl") or site_l.endswith(".at") or site_l.endswith(".de"):
        return PARSERS["stepstone"]
    # Sites like totaljobs, cwjobs, careerstructure, caterer, nijobs, irishjobs, etc.
    return PARSERS["jobsite"]

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stepstone & related job boards scraper")
    parser.add_argument("--query", type=str, default=None, help="Search keyword(s), e.g. 'python developer'")
    parser.add_argument("--location", type=str, default=None, help="Location filter if supported by target site")
    parser.add_argument("--sites", type=str, default=None, help="Comma-separated list of domains to crawl")
    parser.add_argument("--max-pages", type=int, default=None, help="Max pages per site to iterate")
    parser.add_argument("--outdir", type=str, default="output", help="Directory to write export files")
    parser.add_argument("--formats", type=str, default="json,csv", help="Comma-separated: json,csv,xlsx")
    parser.add_argument("--config", type=str, default=os.path.join(os.path.dirname(__file__), "config", "settings.json"),
                        help="Path to settings.json")
    parser.add_argument("--input", type=str, default=None,
                        help="Optional JSON file with overrides: { 'query':..., 'sites':[], 'location':..., 'max_pages':... }")
    return parser.parse_args()

def load_settings(config_path: str) -> Dict[str, Any]:
    conf = load_json(config_path)
    if not isinstance(conf, dict):
        raise ValueError("Invalid settings.json content")
    return conf

def derive_run_params(args: argparse.Namespace, settings: Dict[str, Any]) -> Dict[str, Any]:
    run_params: Dict[str, Any] = {}

    # CLI overrides > input file > settings.json defaults
    if args.input:
        input_data = load_json(args.input) or {}
    else:
        input_data = {}

    run_params["query"] = args.query or input_data.get("query") or settings.get("default_query") or ""
    run_params["location"] = args.location or input_data.get("location") or settings.get("default_location") or ""
    run_params["max_pages"] = args.max_pages or input_data.get("max_pages") or settings.get("max_pages", 1)
    if args.sites:
        run_params["sites"] = [s.strip() for s in args.sites.split(",") if s.strip()]
    else:
        run_params["sites"] = input_data.get("sites") or settings.get("sites", [])

    run_params["formats"] = [fmt.strip().lower() for fmt in args.formats.split(",") if fmt.strip()]
    run_params["outdir"] = args.outdir
    run_params["request"] = settings.get("request", {})
    run_params["throttle_seconds"] = settings.get("throttle_seconds", 1.0)
    run_params["concurrency"] = settings.get("concurrency", 3)

    return run_params

def export_all(records: List[Dict[str, Any]], outdir: str, formats: List[str]) -> None:
    ensure_dir(outdir)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(outdir, f"jobs_{timestamp}")

    if "json" in formats:
        export_json(records, f"{base}.json")
    if "csv" in formats:
        export_csv(records, f"{base}.csv")
    if "xlsx" in formats or "xls" in formats:
        export_excel(records, f"{base}.xlsx")

def main() -> None:
    args = parse_args()
    try:
        settings = load_settings(args.config)
    except Exception as e:
        print(f"[config] Failed to load settings: {e}", file=sys.stderr)
        sys.exit(1)

    params = derive_run_params(args, settings)

    if not params["sites"]:
        print("[warn] No sites provided. Using settings.sites or pass --sites domain1,domain2", file=sys.stderr)
        sys.exit(2)

    all_results: List[Dict[str, Any]] = []

    # Iterate sites in small chunks to avoid hammering
    for group in chunked(params["sites"], max(1, int(params["concurrency"]))):
        for site in group:
            parser = pick_parser_for_site(site)
            try:
                site_results = parser.search_and_collect(
                    domain=site,
                    query=params["query"],
                    location=params["location"],
                    max_pages=int(params["max_pages"]),
                    request_conf=params["request"],
                    throttle=params["throttle_seconds"],
                )
                all_results.extend(site_results)
                print(f"[info] {site}: collected {len(site_results)} jobs")
            except Exception as e:
                print(f"[error] {site}: {e}", file=sys.stderr)

    # de-duplicate by jobUrl
    deduped = unique_by_key(all_results, "jobUrl")
    print(f"[info] total jobs: {len(all_results)} | unique: {len(deduped)}")

    export_all(deduped, params["outdir"], params["formats"])
    print("[done] Export complete.")

if __name__ == "__main__":
    main()