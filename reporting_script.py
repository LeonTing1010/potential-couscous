import argparse
import os
import json
import glob # For finding files
from pathlib import Path # For easier path manipulation
from datetime import datetime, timezone # For potentially parsing timestamps if needed beyond string sort

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding
from rich.rule import Rule
from rich.layout import Group # For grouping renderables in Panel
from rich.style import Style

# --- Constants ---
ANALYSIS_OUTPUT_ROOT_DIR = "./all_app_analyses" # Root directory where analysis JSON files are stored

# --- Helper Functions for File System Interaction ---

def get_analyzed_app_ids_from_fs(root_dir_path: Path) -> list[str]:
    """
    Scans the root analysis directory to find all app_ids that have analysis data.
    Subdirectory names are assumed to be sanitized app_ids (underscores instead of dots).

    Args:
        root_dir_path: Path object for the root analysis directory.

    Returns:
        A list of unique app_id strings (unsanitized, with dots).
    """
    app_ids = []
    if not root_dir_path.is_dir():
        print(f"[FS_SCAN_WARN] Root analysis directory '{root_dir_path}' not found.")
        return []
    
    for item in root_dir_path.iterdir():
        if item.is_dir():
            # Unsanitize directory name (e.g., com_example_app -> com.example.app)
            app_id_original = item.name.replace('_', '.') 
            app_ids.append(app_id_original)
    
    if not app_ids:
        print(f"[FS_SCAN_INFO] No app analysis directories found in '{root_dir_path}'.")
    return sorted(list(set(app_ids))) # Return sorted unique list

def load_single_analysis_file(filepath: Path) -> dict | None:
    """
    Loads and parses a single JSON analysis file.

    Args:
        filepath: Path object for the JSON file.

    Returns:
        A dictionary with the analysis data, or None if loading/parsing fails.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError:
        print(f"[FILE_LOAD_ERROR] Failed to decode JSON from '{filepath}'. File might be corrupted.")
        return None
    except IOError:
        print(f"[FILE_LOAD_ERROR] Could not read file '{filepath}'.")
        return None
    except Exception as e:
        print(f"[FILE_LOAD_ERROR] An unexpected error occurred loading '{filepath}': {e}")
        return None

def get_analysis_files_for_app_from_fs(
    app_id_original: str, 
    root_dir_path: Path, 
    limit: int = 1, 
    sort_descending: bool = True
) -> list[dict]:
    """
    Retrieves analysis data for a specific app_id from its JSON files.
    Sorts files by filename (timestamp part) to get latest/oldest.

    Args:
        app_id_original: The original app_id (e.g., 'com.example.app').
        root_dir_path: Path object for the root analysis directory.
        limit: Max number of analysis documents to return.
        sort_descending: True for newest first, False for oldest first.

    Returns:
        A list of loaded analysis dictionaries.
    """
    app_id_sanitized = app_id_original.replace('.', '_')
    app_analysis_dir = root_dir_path / app_id_sanitized

    if not app_analysis_dir.is_dir():
        # This case is handled by the main logic checking if app_id exists in scanned list.
        # print(f"[FS_APP_FILES_WARN] Analysis directory '{app_analysis_dir}' not found for app_id '{app_id_original}'.")
        return []

    # Files are named like [app_id_sanitized]_[YYYYMMDDHHMMSSZ].json
    # String sorting on filename works directly for recency due to this format.
    json_files = sorted(
        list(app_analysis_dir.glob(f"{app_id_sanitized}_*.json")),
        key=lambda p: p.name, # Sort by filename string
        reverse=sort_descending # Newest (largest timestamp string) first if True
    )

    loaded_analyses = []
    for filepath in json_files[:limit]: # Apply limit
        data = load_single_analysis_file(filepath)
        if data:
            loaded_analyses.append(data)
    
    return loaded_analyses


def display_analysis_document(analysis_doc: dict, console: Console):
    """
    Displays a single analysis document in a formatted way using Rich.
    (Content mostly same, but ensuring keys match the JSON structure)
    """
    if not analysis_doc:
        console.print("No analysis document provided to display.", style="yellow")
        return

    app_name = analysis_doc.get("app_name", "N/A")
    app_id = analysis_doc.get("app_id", "N/A") # This should be in the JSON
    timestamp = analysis_doc.get("analysis_timestamp_utc", "N/A")
    
    # Expecting these to be in the JSON from app_analyzer_module
    llm_model_used = analysis_doc.get("llm_model", analysis_doc.get("llm_model_used", "N/A")) # Fallback for older data
    
    scraper_params_dict = analysis_doc.get("scraper_parameters", {})
    target_count = scraper_params_dict.get("reviews_fetched_target_count", "N/A")
    actual_count = scraper_params_dict.get("reviews_fetched_actual_count", "N/A")
    star_rating = scraper_params_dict.get("target_star_rating", "N/A")
    scraper_parameters_info = f"Target: {target_count}, Actual: {actual_count}, Rating: {star_rating}-star"
    source_type_info = analysis_doc.get("source_type", "N/A")


    title_text = f"Analysis for [bold cyan]{app_name}[/] ([italic blue]{app_id}[/])"
    subtitle_text = f"Timestamp: {timestamp}"

    renderables_list = []

    # Using the updated key "analysis_summary"
    summary = analysis_doc.get("analysis_summary", "No overall summary provided.")
    renderables_list.append(Text.from_markup(f"[bold underline]Analysis Summary:[/]\n{summary}\n", justify="full"))

    pain_points = analysis_doc.get("identified_pain_points", [])
    if pain_points:
        table = Table(title="Identified Pain Points", title_style="bold magenta", show_header=True, header_style="bold gold3", expand=True, border_style="dim blue")
        table.add_column("Pain Point Summary", style="cyan", min_width=30, overflow="fold")
        table.add_column("Example Snippets", style="white", min_width=40, overflow="fold")

        for point in pain_points:
            point_summary = point.get("pain_point_summary", "N/A")
            snippets_list = point.get("example_snippets", [])
            if snippets_list:
                snippets_text = Text("\n---\n", style="dim").join([Text(f'"{s}"') for s in snippets_list])
            else:
                snippets_text = Text("N/A", style="italic dim")
            table.add_row(Text(point_summary, overflow="fold"), snippets_text)
        renderables_list.append(table)
        renderables_list.append(Text(""))
    else:
        renderables_list.append(Text("No specific pain points were identified in this analysis.", style="italic yellow"))
    
    meta_text_content = [
        f"[bold]LLM Model Used:[/bold] {llm_model_used}",
        f"[bold]Scraper Parameters:[/bold] {scraper_parameters_info}",
        f"[bold]Source Type:[/bold] {source_type_info}"
    ]
    renderables_list.append(Text.from_markup("\n".join(meta_text_content)))

    panel_content_group = Group(*renderables_list)
    console.print(Panel(Padding(panel_content_group, (1, 2)), 
                        title=title_text, 
                        subtitle=subtitle_text, 
                        border_style="bright_green",
                        expand=False)) 
    console.print() 

def main():
    parser = argparse.ArgumentParser(
        description="Generate a console report of app review analyses from JSON files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--app_id", 
        type=str, 
        help="Report only for this specific app ID (e.g., 'com.example.app')."
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=1, 
        help="Number of latest analyses to show per app (default: 1).\nMust be a positive integer."
    )
    args = parser.parse_args()

    if args.limit <= 0:
        console.print("[ERROR] --limit must be a positive integer.", style="bold red")
        return

    console = Console()
    console.print(Rule("[bold #FFD700]📱 App Review Analysis Report (File System) 📊[/bold #FFD700]", style="#FFBF00"))

    root_dir = Path(ANALYSIS_OUTPUT_ROOT_DIR)

    try:
        if args.app_id:
            app_id_to_report = args.app_id
            console.print(f"\n[INFO] Fetching analyses for app ID: [bold]{app_id_to_report}[/] (limit: {args.limit})...", style="cyan")
            
            # Check if directory for this specific app_id exists
            sanitized_app_id_for_dir = app_id_to_report.replace('.', '_')
            if not (root_dir / sanitized_app_id_for_dir).is_dir():
                 console.print(f"ℹ️ No analysis directory found for app ID: [bold]{app_id_to_report}[/]. Ensure the app_id is correct and analyses have been run.", style="yellow")
            else:
                analyses = get_analysis_files_for_app_from_fs(app_id_to_report, root_dir, limit=args.limit)
                if not analyses:
                    console.print(f"ℹ️ No analysis files found for app ID: [bold]{app_id_to_report}[/] in its directory.", style="yellow")
                else:
                    console.print(f"Found {len(analyses)} analysis document(s) for [bold]{app_id_to_report}[/].")
                    for doc in analyses:
                        display_analysis_document(doc, console)
        else:
            console.print(f"\n[INFO] Scanning for all analyzed app IDs in '{root_dir}'...", style="cyan")
            distinct_app_ids = get_analyzed_app_ids_from_fs(root_dir)
            if not distinct_app_ids:
                console.print(f"ℹ️ No app analysis directories found in '{root_dir}'.", style="yellow")
            else:
                console.print(f"Found [bold]{len(distinct_app_ids)}[/] distinct app(s) with analysis data. Fetching reports (limit: {args.limit} per app)...")
                for i, app_id_str in enumerate(distinct_app_ids):
                    if i > 0: console.print() 
                    console.print(Rule(f"[bold #ADD8E6]Reports for App ID: {app_id_str}[/bold #ADD8E6]", style="#007FFF"))
                    analyses = get_analysis_files_for_app_from_fs(app_id_str, root_dir, limit=args.limit)
                    if not analyses:
                        console.print(f"ℹ️ No analysis files found for app ID: [bold]{app_id_str}[/]", style="italic yellow")
                    else:
                        console.print(f"Found {len(analyses)} analysis document(s) for [bold]{app_id_str}[/].")
                        for doc in analyses:
                            display_analysis_document(doc, console)
    
    except Exception as e:
        console.print(f"[CRITICAL_ERROR] An unexpected error occurred during report generation: {type(e).__name__} - {e}", style="bold red")
        import traceback
        console.print(f"[TRACE]\n{traceback.format_exc()}", style="dim white")
    finally:
        console.print(Rule("[bold #FFBF00]Report Generation Finished[/bold #FFBF00]", style="#FFBF00"))

if __name__ == "__main__":
    main()
```
