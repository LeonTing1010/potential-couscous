import argparse
import os
import json
import re # For sanitizing filenames
from pathlib import Path 
from datetime import datetime, timezone 

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding
from rich.rule import Rule
from rich.layout import Group 
from rich.style import Style
from rich.syntax import Syntax 

# --- Constants ---
APP_ANALYSIS_OUTPUT_ROOT_DIR = Path("./all_app_analyses") 
FORUM_NLP_ANALYSIS_OUTPUT_ROOT_DIR = Path("./all_forum_nlp_analyses")
PRODUCT_MENTIONS_OUTPUT_ROOT_DIR = Path("./all_product_mentions")
KEYWORD_TRENDS_OUTPUT_ROOT_DIR = Path("./all_keyword_trends")

# --- Helper Functions for File System Interaction (Generic) ---

def load_single_json_file(filepath: Path) -> dict | None:
    """Loads and parses a single JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f: data = json.load(f)
        return data
    except json.JSONDecodeError: print(f"[ERROR] JSON decode error in '{filepath}'."); return None
    except IOError: print(f"[ERROR] IO error reading '{filepath}'."); return None
    except Exception as e: print(f"[ERROR] Unexpected error loading '{filepath}': {e}"); return None

def _sanitize_filename_component(name: str, max_len: int = 50) -> str:
    """Sanitizes a string to be used as a filename/directory component."""
    s = name.lower(); s = re.sub(r'\s+', '_', s); s = re.sub(r'[^\w-]', '', s); return s[:max_len]

# --- App Review Analysis Helpers (from previous version) ---
def get_analyzed_app_ids_from_fs(root_dir_path: Path) -> list[str]:
    app_ids = []
    if not root_dir_path.is_dir(): return []
    for item in root_dir_path.iterdir():
        if item.is_dir(): app_ids.append(item.name.replace('_', '.'))
    return sorted(list(set(app_ids)))

def get_analysis_files_for_app_from_fs(app_id_original: str, root_dir_path: Path, limit: int = 1, sort_descending: bool = True) -> list[dict]:
    app_id_sanitized = app_id_original.replace('.', '_'); app_analysis_dir = root_dir_path / app_id_sanitized
    if not app_analysis_dir.is_dir(): return []
    json_files = sorted(list(app_analysis_dir.glob(f"{app_id_sanitized}_*.json")), key=lambda p: p.name, reverse=sort_descending)
    return [data for filepath in json_files[:limit] if (data := load_single_json_file(filepath))]

# --- Forum NLP Analysis Helpers (from previous version) ---
def get_analyzed_forum_platforms(nlp_root_dir: Path) -> list[str]:
    platforms = []
    if not nlp_root_dir.is_dir(): return []
    for item in nlp_root_dir.iterdir():
        if item.is_dir(): platforms.append(item.name)
    return sorted(platforms)

def get_analyzed_forum_ids_for_platform(platform_dir: Path) -> list[str]:
    forum_ids = []
    if not platform_dir.is_dir(): return []
    for item in platform_dir.iterdir():
        if item.is_dir(): forum_ids.append(item.name)
    return sorted(forum_ids)

def get_nlp_analysis_files_for_forum(forum_nlp_data_dir: Path, limit: int = 5) -> list[dict]:
    if not forum_nlp_data_dir.is_dir(): return []
    loaded_analyses = [data for filepath in forum_nlp_data_dir.glob("*_nlp.json") if (data := load_single_json_file(filepath)) and data.get("nlp_analysis_timestamp_utc")]
    loaded_analyses.sort(key=lambda x: x["nlp_analysis_timestamp_utc"], reverse=True)
    return loaded_analyses[:limit]

# --- Product Mentions & Keyword Trends Helpers ---
def get_product_mention_platforms_from_fs(mentions_root_dir: Path) -> list[str]:
    platforms = []
    if not mentions_root_dir.is_dir():
        print(f"[FS_SCAN_WARN] Product mentions root directory '{mentions_root_dir}' not found.")
        return []
    for item in mentions_root_dir.iterdir():
        if item.is_dir(): platforms.append(item.name)
    return sorted(platforms)

def get_product_mentions_by_platform(platform_dir: Path, limit: int = 5) -> list[dict]:
    if not platform_dir.is_dir(): return []
    product_files = list(platform_dir.glob("*.json"))
    loaded_mentions = [data for filepath in product_files if (data := load_single_json_file(filepath)) and data.get("retrieved_utc")]
    loaded_mentions.sort(key=lambda x: x["retrieved_utc"], reverse=True) # Sort by retrieval time
    return loaded_mentions[:limit]

def get_trend_data_for_keyword(keyword_trends_root_dir: Path, keyword: str) -> dict | None:
    sanitized_keyword_dir_name = _sanitize_filename_component(keyword)
    keyword_dir = keyword_trends_root_dir / sanitized_keyword_dir_name
    if not keyword_dir.is_dir():
        print(f"[TRENDS_LOAD_INFO] No trend data directory found for keyword '{keyword}' (expected at '{keyword_dir}').")
        return None
    
    trend_data = {"keyword": keyword}
    trend_data["interest_over_time"] = load_single_json_file(keyword_dir / "interest_over_time.json")
    trend_data["related_topics"] = load_single_json_file(keyword_dir / "related_topics.json")
    trend_data["related_queries"] = load_single_json_file(keyword_dir / "related_queries.json")
    
    if not trend_data["interest_over_time"] and not trend_data["related_topics"] and not trend_data["related_queries"]:
        print(f"[TRENDS_LOAD_WARN] No actual trend data files found for keyword '{keyword}' in '{keyword_dir}'.")
        return None # No useful data found
    return trend_data

# --- Display Functions ---
def display_app_review_analysis_document(analysis_doc: dict, console: Console):
    # (Content from previous version - assumed correct and complete)
    if not analysis_doc: console.print("No app review analysis document.",style="yellow"); return
    app_name=analysis_doc.get("app_name","N/A");app_id=analysis_doc.get("app_id","N/A");ts=analysis_doc.get("analysis_timestamp_utc","N/A")
    llm=analysis_doc.get("llm_model_used",analysis_doc.get("llm_model","N/A"));scraper=analysis_doc.get("scraper_parameters",{});src=analysis_doc.get("source_type","N/A")
    scraper_info=f"Target:{scraper.get('reviews_fetched_target_count','N/A')},Actual:{scraper.get('reviews_fetched_actual_count','N/A')},Rating:{scraper.get('target_star_rating','N/A')}-star"
    title=f"App Review: [bold cyan]{app_name}[/] ({app_id})";sub=f"Analyzed: {ts}";r_list=[Text.from_markup(f"[u]Summary:[/]\n{analysis_doc.get('analysis_summary','N/A')}\n",justify="full")]
    pain=analysis_doc.get("identified_pain_points",[]);
    if pain:
        tbl=Table(title="Pain Points",header_style="gold3",expand=True);tbl.add_column("Summary",style="cyan",min_width=20);tbl.add_column("Snippets",min_width=30)
        for p in pain: tbl.add_row(p.get("pain_point_summary","N/A"),Text("\n---\n").join([Text(f'"{s}"') for s in p.get("example_snippets",[])]) or "N/A")
        r_list.extend([tbl,Text("")])
    else: r_list.append(Text("No pain points identified.",style="italic"))
    r_list.append(Text.from_markup(f"[b]LLM:[/b] {llm}\n[b]Scraper:[/b] {scraper_info}\n[b]Source:[/b] {src}"))
    console.print(Panel(Padding(Group(*r_list),(1,2)),title=title,subtitle=sub,border_style="green",expand=False)); console.print()

def display_forum_nlp_document(nlp_doc: dict, console: Console):
    # (Content from previous version - assumed correct and complete)
    if not nlp_doc: console.print("No forum NLP document.",style="yellow"); return
    pid=nlp_doc.get("source_post_id","N/A");sub=nlp_doc.get("analyzed_subreddit","N/A");ts=nlp_doc.get("nlp_analysis_timestamp_utc","N/A")
    llm=nlp_doc.get("llm_model_used","N/A") 
    title=f"Forum NLP: [bold cyan]{sub}/t3_/{pid}[/]";sub_title=f"Analyzed: {ts}";r_list=[]
    r_list.append(Text.from_markup(f"[u]Need/Problem:[/]\n{nlp_doc.get('primary_user_need_or_problem','N/A')}\n"))
    r_list.append(Text.from_markup(f"[b]Topics:[/b] {', '.join(nlp_doc.get('key_topics_keywords',['N/A']))}\n"))
    r_list.append(Text.from_markup(f"[b]Sentiment:[/b] {nlp_doc.get('sentiment_regarding_problem_or_need','N/A')}\n"))
    pain=nlp_doc.get("pain_point_indicators_verbatim",[]);r_list.append(Text.from_markup(f"[u]Pain Indicators:[/]\n"+("\n".join([f"- \"{p}\"" for p in pain]) if pain else "[i]None identified.[/i]\n")))
    sols=nlp_doc.get("suggested_solutions_from_comments",[])
    if sols:
        tbl=Table(title="Solutions",header_style="gold3",expand=True);tbl.add_column("Summary",style="cyan",min_width=20);tbl.add_column("Quote",min_width=30)
        for s in sols: tbl.add_row(s.get("solution_summary","N/A"),s.get("verbatim_quote","N/A"))
        r_list.extend([tbl,Text("")])
    else: r_list.append(Text.from_markup("[u]Solutions:[/]\n[i]None identified.[/i]\n"))
    r_list.append(Text.from_markup(f"[u]Discussion Summary:[/]\n{nlp_doc.get('overall_discussion_summary','N/A')}\n"))
    if llm!="N/A":r_list.append(Text.from_markup(f"[b]LLM:[/b] {llm}"))
    console.print(Panel(Padding(Group(*r_list),(1,2)),title=title,subtitle=sub_title,border_style="blue",expand=False)); console.print()

def display_trends_report_document(console: Console, product_mention: dict | None, trend_data: dict | None):
    if not trend_data or not trend_data.get("keyword"):
        console.print("No trend data provided or keyword missing.", style="yellow"); return

    keyword = trend_data["keyword"]
    title_text = f"Google Trends Analysis for Keyword: [bold magenta]{keyword}[/]"
    renderables = []

    if product_mention:
        pm_name = product_mention.get("product_name", "N/A")
        pm_tagline = product_mention.get("tagline", "N/A")
        pm_ph_url = product_mention.get("ph_url", "N/A")
        pm_retrieved = product_mention.get("retrieved_utc", "N/A")
        pm_panel = Panel(Text.from_markup(f"[b]Product Name:[/b] {pm_name}\n[b]Tagline:[/b] {pm_tagline}\n[b]PH URL:[/b] {pm_ph_url}\n[b]Discovered:[/b] {pm_retrieved}"),
                         title="Matching Product Mention", border_style="dim cyan", expand=False)
        renderables.append(pm_panel)

    iot = trend_data.get("interest_over_time")
    if iot and iot.get("date_points"):
        dates = list(iot["date_points"].keys())
        values = [v.get(keyword, 0) for v in iot["date_points"].values()] # Ensure keyword exists
        summary = f"Data points: {len(dates)}. Min: {min(values) if values else 'N/A'}, Max: {max(values) if values else 'N/A'}. Partial data: {iot.get('isPartial', False)}"
        renderables.append(Text.from_markup(f"\n[bold underline]Interest Over Time ({keyword}):[/]\n{summary}"))
        # Could add a small bar chart here or more detailed table if needed.
    else:
        renderables.append(Text.from_markup(f"\n[bold underline]Interest Over Time ({keyword}):[/]\n[italic]No data available.[/italic]"))

    for key in ["related_topics", "related_queries"]:
        data_item = trend_data.get(key)
        renderables.append(Text(f"\n[bold underline]{key.replace('_', ' ').title()}:[/]"))
        if data_item and (data_item.get("top") or data_item.get("rising")):
            for sub_key in ["top", "rising"]:
                items = data_item.get(sub_key, [])
                if items:
                    table = Table(title=f"{sub_key.capitalize()} {key.replace('_', ' ').title()}", title_style="bold magenta" if sub_key == "rising" else "bold", show_header=True, header_style="bold yellow", expand=True)
                    if key == "related_topics":
                        table.add_column("Topic/Title", style="cyan"); table.add_column("Type", style="dim"); table.add_column("Value", style="green" if sub_key == "rising" else "white")
                        for item in items: table.add_row(item.get("topic_title"), item.get("topic_type"), str(item.get("value")))
                    else: # related_queries
                        table.add_column("Query", style="cyan"); table.add_column("Value", style="green" if sub_key == "rising" else "white")
                        for item in items: table.add_row(item.get("query"), str(item.get("value")))
                    renderables.append(table)
                else:
                    renderables.append(Text(f"No {sub_key} {key.replace('_', ' ')} found.", style="italic"))
        else:
            renderables.append(Text(f"No {key.replace('_', ' ')} data available.", style="italic"))
    
    console.print(Panel(Padding(Group(*renderables), (1,2)), title=title_text, border_style="magenta", expand=False))
    console.print()

# --- Main ---
def main():
    parser = argparse.ArgumentParser(description="DemandRadar Reporting Script.", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--source_type", type=str, choices=['apps', 'forums', 'trends', 'all'], default='all',
                        help="Data source: 'apps', 'forums', 'trends', 'all'. (default: 'all')")
    parser.add_argument("--id", type=str, # Renamed from app_id for broader use
                        help=("Specific ID. For 'apps': app_id (com.example.app).\n"
                              "For 'forums': sanitized forum_id (r_SideProject).\n"
                              "For 'trends': keyword/product name to report trends for."))
    parser.add_argument("--limit", type=int, default=3, help="Max entries per item (default: 3).")
    args = parser.parse_args()

    console = Console()
    title_suffix = f"({args.source_type.capitalize()})" if args.id else "(Overview)"
    console.print(Rule(f"[bold #FFD700]📊 DemandRadar Report {title_suffix} 📊[/bold #FFD700]", style="#FFBF00"))

    if args.source_type in ['apps', 'all']:
        console.print(Rule("[bold green]App Review Analyses[/]", style="green"))
        app_root_dir = APP_ANALYSIS_OUTPUT_ROOT_DIR
        ids_to_process = [args.id] if args.id and args.source_type == 'apps' else get_analyzed_app_ids_from_fs(app_root_dir)
        if not ids_to_process and args.id : console.print(f"ℹ️ No analysis for app ID: [bold]{args.id}[/].", style="yellow")
        elif not ids_to_process : console.print(f"ℹ️ No app analyses in '{app_root_dir}'.", style="yellow")
        for app_id_str in ids_to_process:
            if not (args.id and args.source_type == 'apps'): console.print(Rule(f"[bold #00BFFF]App: {app_id_str}[/]", style="#007FFF"))
            analyses = get_analysis_files_for_app_from_fs(app_id_str, app_root_dir, limit=args.limit)
            if analyses:
                for doc in analyses: display_app_review_analysis_document(doc, console)
            else: console.print(f"ℹ️ No analysis files for app ID: [bold]{app_id_str}[/].", style="italic yellow")
        console.print()

    if args.source_type in ['forums', 'all']:
        console.print(Rule("[bold blue]Forum NLP Analyses[/]", style="blue"))
        nlp_root = FORUM_NLP_ANALYSIS_OUTPUT_ROOT_DIR
        if args.id and args.source_type == 'forums': # Assumes ID is platform/sanitized_forum_id e.g. reddit/r_SideProject
            parts = args.id.split('/', 1); platform, forum_id = (parts[0], parts[1]) if len(parts)==2 else ("reddit", args.id) # Default platform
            console.print(f"\n[INFO] Forum NLP for {platform}/{forum_id} (limit: {args.limit})...", style="cyan")
            forum_dir = nlp_root / platform / forum_id
            if not forum_dir.is_dir(): console.print(f"ℹ️ No NLP data for {platform}/{forum_id}.", style="yellow")
            else:
                nlps = get_nlp_analysis_files_for_forum(forum_dir, limit=args.limit)
                if nlps:
                    for doc in nlps: display_forum_nlp_document(doc, console)
                else: console.print(f"ℹ️ No NLP files for {platform}/{forum_id}.", style="italic yellow")
        else:
            platforms = get_analyzed_forum_platforms(nlp_root)
            if not platforms: console.print(f"ℹ️ No forum platforms in '{nlp_root}'.", style="yellow")
            for plat in platforms:
                console.print(Rule(f"[bold #BA55D3]Platform: {plat}[/]", style="#8A2BE2"))
                forum_ids = get_analyzed_forum_ids_for_platform(nlp_root / plat)
                if not forum_ids: console.print(f"ℹ️ No forums for platform '{plat}'.", style="italic yellow")
                for fid in forum_ids:
                    console.print(Rule(f"[bold #6495ED]Forum: {fid}[/]", style="#4169E1"))
                    nlps = get_nlp_analysis_files_for_forum(nlp_root / plat / fid, limit=args.limit)
                    if nlps:
                        for doc in nlps: display_forum_nlp_document(doc, console)
                    else: console.print(f"ℹ️ No NLP files for forum ID: [bold]{fid}[/].", style="italic yellow")
        console.print()

    if args.source_type in ['trends', 'all']:
        console.print(Rule("[bold magenta]Product Keyword Trends[/]", style="magenta"))
        if args.id and args.source_type == 'trends': # ID is keyword
            keyword = args.id
            console.print(f"\n[INFO] Trends for keyword: [bold]{keyword}[/]...", style="cyan")
            trend_data = get_trend_data_for_keyword(KEYWORD_TRENDS_OUTPUT_ROOT_DIR, keyword)
            # Attempt to find a matching product mention (simple match on product_name)
            product_mention_to_display = None
            mention_platforms = get_product_mention_platforms_from_fs(PRODUCT_MENTIONS_OUTPUT_ROOT_DIR)
            for plat in mention_platforms: # Search across all platforms for this keyword
                mentions = get_product_mentions_by_platform(PRODUCT_MENTIONS_OUTPUT_ROOT_DIR / plat, limit=100) # Get more to search
                for mention in mentions:
                    if mention.get("product_name", "").lower() == keyword.lower():
                        product_mention_to_display = mention; break
                if product_mention_to_display: break
            if trend_data or product_mention_to_display:
                display_trends_report_document(console, product_mention_to_display, trend_data)
            else: console.print(f"ℹ️ No trend data or product mention found for keyword: [bold]{keyword}[/].", style="yellow")
        else: # List trends for a few recent product mentions
            console.print(f"\n[INFO] Trends for {args.limit} most recent product mentions...", style="cyan")
            recent_mentions_all_platforms = []
            mention_platforms = get_product_mention_platforms_from_fs(PRODUCT_MENTIONS_OUTPUT_ROOT_DIR)
            for plat in mention_platforms:
                recent_mentions_all_platforms.extend(get_product_mentions_by_platform(PRODUCT_MENTIONS_OUTPUT_ROOT_DIR / plat, limit=args.limit))
            # Sort all collected mentions by retrieved_utc to get overall recent ones
            recent_mentions_all_platforms.sort(key=lambda x: x.get("retrieved_utc", ""), reverse=True)
            
            if not recent_mentions_all_platforms: console.print(f"ℹ️ No product mentions found in '{PRODUCT_MENTIONS_OUTPUT_ROOT_DIR}'.", style="yellow")
            else:
                for i, mention in enumerate(recent_mentions_all_platforms[:args.limit]): # Show trends for top N overall recent mentions
                    keyword = mention.get("product_name")
                    if not keyword: continue
                    console.print(Rule(f"[bold #D2691E]Keyword: {keyword}[/]", style="#A0522D")) # Chocolate/Sienna
                    trend_data = get_trend_data_for_keyword(KEYWORD_TRENDS_OUTPUT_ROOT_DIR, keyword)
                    display_trends_report_document(console, mention, trend_data)
        console.print()

    console.print(Rule("[bold #FFBF00]Report Generation Finished[/bold #FFBF00]", style="#FFBF00"))

if __name__ == "__main__":
    try: main()
    except Exception as e: console = Console(); console.print(f"[CRITICAL_ERROR] {e}",style="red"); import traceback; console.print(f"[TRACE]\n{traceback.format_exc()}",style="dim")
```
