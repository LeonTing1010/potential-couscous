import os
import json
import time # For potential delays
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
import sys # For --setup argument
from pathlib import Path # For easier path manipulation
import re # For sanitizing filenames

# App processing modules
from target_config_manager import (
    load_target_apps,
    save_target_apps,
    get_active_target_apps,
    update_app_timestamp,
    add_target_app as add_app_target_to_config, 
    TARGET_CONFIG_FILE_PATH as APP_TARGET_CONFIG_FILE_PATH
)
from app_analyzer_module import process_single_app_reviews

# Forum processing modules
from forum_config_manager import (
    load_target_forums,
    save_target_forums,
    get_active_target_forums,
    update_forum_timestamp,
    add_target_forum as add_forum_target_to_config, 
    TARGET_FORUMS_CONFIG_FILE_PATH
)
from reddit_scraper_module import init_praw_from_env, fetch_subreddit_posts
from forum_llm_analyzer_module import analyze_forum_post_with_llm

# Product Discovery modules
from discovery_sources_config_manager import (
    load_discovery_sources,
    save_discovery_sources,
    get_active_discovery_sources,
    update_source_timestamp,
    add_discovery_source,
    TARGET_DISCOVERY_CONFIG_FILE_PATH
)
from product_discovery_scraper import scrape_product_hunt_newest

# Google Trends modules
from google_trends_analyzer import (
    init_pytrends,
    get_interest_over_time,
    get_related_topics,
    get_related_queries
)

# Topic Consolidation module
from topic_consolidator import (
    consolidate_topics,
    SYNTHESIS_OUTPUT_DIR # For initial setup
)


# --- Configuration ---
SCHEDULE_INTERVAL_MINUTES = 15 

DEFAULT_APP_SCRAPE_INTERVAL_HOURS = 24
ANALYSIS_OUTPUT_ROOT_DIR = Path("./all_app_analyses") 

DEFAULT_FORUM_SCRAPE_INTERVAL_HOURS = 6 
FORUM_ANALYSIS_OUTPUT_ROOT_DIR = Path("./all_forum_data") 
FORUM_NLP_ANALYSIS_OUTPUT_ROOT_DIR = Path("./all_forum_nlp_analyses") 

DEFAULT_DISCOVERY_SCRAPE_INTERVAL_HOURS = 24
PRODUCT_MENTIONS_OUTPUT_ROOT_DIR = Path("./all_product_mentions")

KEYWORD_TRENDS_OUTPUT_ROOT_DIR = Path("./all_keyword_trends")
PROCESSED_KEYWORDS_TRACKING_FILE = Path("./processed_keywords_tracking.json")
KEYWORD_PROCESSING_DELAY_SECONDS = 10 
REPROCESS_KEYWORD_TREND_AFTER_DAYS = 30

USE_STEMMING_FOR_CONSOLIDATION = False # Set to True if NLTK is installed and 'punkt' downloaded


# --- Helper Function for NLP Processing ---
def _process_pending_forum_nlp_tasks():
    print(f"\n[SCHEDULER_JOB][FORUM_NLP_PROCESSING] --- Starting Pending Forum NLP Task Processing ---")
    if not FORUM_ANALYSIS_OUTPUT_ROOT_DIR.is_dir():
        print(f"[SCHEDULER_JOB][FORUM_NLP_PROCESSING][INFO] Raw forum data directory '{FORUM_ANALYSIS_OUTPUT_ROOT_DIR}' not found. Nothing to process.")
        return
    processed_count = 0; skipped_count = 0; error_count = 0
    for platform_dir in FORUM_ANALYSIS_OUTPUT_ROOT_DIR.iterdir():
        if not platform_dir.is_dir(): continue
        platform_name = platform_dir.name
        for forum_id_dir in platform_dir.iterdir():
            if not forum_id_dir.is_dir(): continue
            forum_id_sanitized = forum_id_dir.name
            for raw_post_file in forum_id_dir.glob("*.json"):
                post_id = raw_post_file.stem
                nlp_output_subdir = FORUM_NLP_ANALYSIS_OUTPUT_ROOT_DIR / platform_name / forum_id_sanitized
                nlp_output_file = nlp_output_subdir / f"{post_id}_nlp.json"
                if nlp_output_file.exists(): skipped_count +=1; continue
                try:
                    with open(raw_post_file, 'r', encoding='utf-8') as f: raw_post_data = json.load(f)
                    if not raw_post_data: error_count +=1; print(f"[WARN] Raw post data file '{raw_post_file}' is empty."); continue
                    nlp_result = analyze_forum_post_with_llm(raw_post_data)
                    if nlp_result and "error" not in nlp_result:
                        nlp_output_subdir.mkdir(parents=True, exist_ok=True)
                        with open(nlp_output_file, 'w', encoding='utf-8') as f_out: json.dump(nlp_result, f_out, indent=2, ensure_ascii=False)
                        processed_count += 1
                    else: error_count += 1; print(f"[ERROR] NLP analysis for post '{post_id}' failed. Details: {nlp_result.get('error', 'Unknown') if nlp_result else 'No result'}")
                except Exception as e_nlp_file: error_count += 1; print(f"[ERROR] Exception during NLP for {raw_post_file}: {e_nlp_file}"); import traceback; traceback.print_exc()
    print(f"[SCHEDULER_JOB][FORUM_NLP_PROCESSING] Summary: Processed={processed_count}, Skipped(already done)={skipped_count}, Errors={error_count}")
    print(f"[SCHEDULER_JOB][FORUM_NLP_PROCESSING] --- Finished Pending Forum NLP Tasks ---")

# --- Helper Functions for Keyword Trend Analysis ---
def _load_processed_keywords_tracking(filepath: Path) -> dict:
    if not filepath.exists(): return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f: data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IOError) as e:
        print(f"[KEYWORD_TRACKING_ERROR] Error loading tracking file '{filepath}': {e}. Returning empty tracking."); return {}

def _save_processed_keywords_tracking(data: dict, filepath: Path):
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[KEYWORD_TRACKING_INFO] Saved processed keywords tracking to '{filepath}'.")
    except Exception as e: print(f"[KEYWORD_TRACKING_ERROR] Failed to save tracking to '{filepath}': {e}")

def _get_new_keywords_from_product_mentions(processed_keywords_tracking: dict) -> list[str]:
    print("[KEYWORD_EXTRACTION_INFO] Scanning product mentions for new keywords...")
    if not PRODUCT_MENTIONS_OUTPUT_ROOT_DIR.is_dir():
        print(f"[KEYWORD_EXTRACTION_WARN] Product mentions directory '{PRODUCT_MENTIONS_OUTPUT_ROOT_DIR}' not found."); return []
    
    all_product_names = set()
    for platform_dir in PRODUCT_MENTIONS_OUTPUT_ROOT_DIR.iterdir():
        if platform_dir.is_dir():
            for product_file in platform_dir.glob("*.json"):
                try:
                    with open(product_file, 'r', encoding='utf-8') as f: data = json.load(f)
                    if data and isinstance(data, dict) and data.get("product_name"):
                        all_product_names.add(data["product_name"])
                except Exception as e: print(f"[KEYWORD_EXTRACTION_ERROR] Failed to process '{product_file}': {e}")
    
    new_keywords = []
    now_utc = datetime.now(timezone.utc)
    for name in all_product_names:
        last_processed_ts_str = processed_keywords_tracking.get(name)
        if not last_processed_ts_str: new_keywords.append(name)
        else:
            try:
                last_processed_dt = datetime.fromisoformat(last_processed_ts_str.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
                if now_utc - last_processed_dt > timedelta(days=REPROCESS_KEYWORD_TREND_AFTER_DAYS): new_keywords.append(name)
            except ValueError: new_keywords.append(name)
    print(f"[KEYWORD_EXTRACTION_INFO] Found {len(all_product_names)} unique names. {len(new_keywords)} new/due for reprocessing.")
    return list(set(new_keywords))

def _sanitize_filename_component(name: str, max_len: int = 50) -> str:
    s = name.lower(); s = re.sub(r'\s+', '_', s); s = re.sub(r'[^\w-]', '', s); return s[:max_len]

def _analyze_and_save_single_keyword_trends(pytrends_obj, keyword: str, processed_keywords_tracking: dict) -> bool:
    print(f"[KEYWORD_TREND_ANALYSIS_INFO] Analyzing keyword: '{keyword}'")
    sanitized_keyword_dir_name = _sanitize_filename_component(keyword)
    keyword_output_dir = KEYWORD_TRENDS_OUTPUT_ROOT_DIR / sanitized_keyword_dir_name
    keyword_output_dir.mkdir(parents=True, exist_ok=True)
    success_flags = {"iot": False, "related_topics": False, "related_queries": False}
    try:
        iot_data = get_interest_over_time(pytrends_obj, [keyword])
        if iot_data:
            with open(keyword_output_dir / "interest_over_time.json", 'w', encoding='utf-8') as f: json.dump(iot_data, f, indent=2); success_flags["iot"] = True
        related_topics_data = get_related_topics(pytrends_obj, keyword)
        if related_topics_data:
            with open(keyword_output_dir / "related_topics.json", 'w', encoding='utf-8') as f: json.dump(related_topics_data, f, indent=2); success_flags["related_topics"] = True
        related_queries_data = get_related_queries(pytrends_obj, keyword)
        if related_queries_data:
            with open(keyword_output_dir / "related_queries.json", 'w', encoding='utf-8') as f: json.dump(related_queries_data, f, indent=2); success_flags["related_queries"] = True
    except Exception as e: print(f"[KEYWORD_TREND_ANALYSIS_ERROR] Exception during Google Trends fetch for '{keyword}': {e}"); return False
    
    if success_flags["iot"] or success_flags["related_topics"] or success_flags["related_queries"]: 
        processed_keywords_tracking[keyword] = datetime.now(timezone.utc).isoformat()
        print(f"[KEYWORD_TREND_ANALYSIS_SUCCESS] Processed and saved some data for '{keyword}'.")
        return True
    print(f"[KEYWORD_TREND_ANALYSIS_WARN] No significant data fetched for '{keyword}'. Timestamp not updated."); return False

def _run_keyword_trend_analysis_stage():
    print(f"\n[SCHEDULER_JOB][KEYWORD_TREND_ANALYSIS] --- Starting Keyword Trend Analysis Stage ---")
    pytrends = init_pytrends()
    if not pytrends: print("[SCHEDULER_JOB][KEYWORD_TREND_ANALYSIS][ERROR] Failed to init Pytrends. Skipping stage."); return
    processed_tracking = _load_processed_keywords_tracking(PROCESSED_KEYWORDS_TRACKING_FILE)
    new_keywords = _get_new_keywords_from_product_mentions(processed_tracking)
    if not new_keywords: print("[SCHEDULER_JOB][KEYWORD_TREND_ANALYSIS][INFO] No new keywords to analyze.");
    else:
        print(f"[SCHEDULER_JOB][KEYWORD_TREND_ANALYSIS][INFO] Found {len(new_keywords)} new keyword(s).")
        keywords_processed_in_run = 0
        for i, keyword in enumerate(new_keywords):
            if _analyze_and_save_single_keyword_trends(pytrends, keyword, processed_tracking): keywords_processed_in_run += 1
            if i < len(new_keywords) - 1: print(f"[INFO] Delaying for {KEYWORD_PROCESSING_DELAY_SECONDS}s..."); time.sleep(KEYWORD_PROCESSING_DELAY_SECONDS)
        if keywords_processed_in_run > 0 or len(new_keywords) > 0: _save_processed_keywords_tracking(processed_tracking, PROCESSED_KEYWORDS_TRACKING_FILE)
    print(f"[SCHEDULER_JOB][KEYWORD_TREND_ANALYSIS] --- Finished Keyword Trend Analysis Stage ---")

# --- Main Scheduled Job ---
def scheduled_analysis_job():
    job_start_time = datetime.now(timezone.utc)
    print(f"\n[SCHEDULER_JOB][{job_start_time.isoformat()}] --- Starting Master Job ---")
    
    # --- 1. App Processing ---
    try:
        print(f"\n[SCHEDULER_JOB][APP_PROCESSING] --- Starting App Target Processing ---")
        all_apps_data = load_target_apps(str(APP_TARGET_CONFIG_FILE_PATH)); active_apps = get_active_target_apps(all_apps_data); config_changed_apps = False
        if not active_apps: print("[INFO] No active app targets.")
        else:
            for app_config in active_apps:
                app_id=app_config.get("app_id"); app_name=app_config.get("app_name","N/A")
                if not app_id: print("[WARN] Skipping app with no ID."); continue
                last_ts=app_config.get("last_successful_analysis_timestamp_utc"); interval=app_config.get("custom_scrape_interval_hours",DEFAULT_APP_SCRAPE_INTERVAL_HOURS)
                if last_ts and (datetime.now(timezone.utc) - datetime.fromisoformat(last_ts.replace('Z','+00:00')).replace(tzinfo=timezone.utc) < timedelta(hours=interval)): print(f"[INFO] App '{app_name}' not due. Skipping."); continue
                print(f"[INFO] App '{app_name}' due. Processing..."); analysis_result = process_single_app_reviews(app_id=app_id,app_name=app_name)
                if analysis_result and "error" not in analysis_result:
                    out_dir=ANALYSIS_OUTPUT_ROOT_DIR/app_id.replace('.','_'); out_dir.mkdir(parents=True,exist_ok=True)
                    ts_part=datetime.fromisoformat(analysis_result.get('analysis_timestamp_utc').replace('Z','+00:00')).strftime("%Y%m%d%H%M%SZ")
                    out_fn=out_dir/f"{app_id.replace('.','_')}_{ts_part}.json"
                    with open(out_fn,'w',encoding='utf-8') as f: json.dump(analysis_result,f,indent=2)
                    if update_app_timestamp(all_apps_data,app_id,analysis_result['analysis_timestamp_utc']): config_changed_apps=True
            if config_changed_apps: save_target_apps(all_apps_data, str(APP_TARGET_CONFIG_FILE_PATH))
    except Exception as e: print(f"[FATAL_APP_ERROR] {e}"); import traceback; traceback.print_exc()
    
    # --- 2. Forum Scraping ---
    try:
        print(f"\n[SCHEDULER_JOB][FORUM_SCRAPING] --- Starting Forum Target Scraping ---"); reddit_instance=None; config_changed_forums=False
        all_forums_data=load_target_forums(str(TARGET_FORUMS_CONFIG_FILE_PATH)); active_forums=get_active_target_forums(all_forums_data)
        if not active_forums: print("[INFO] No active forum targets.")
        else:
            if any(f.get("platform")=="reddit" for f in active_forums): reddit_instance=init_praw_from_env()
            for forum_conf in active_forums:
                plat=forum_conf.get("platform");fid=forum_conf.get("forum_identifier");dname=forum_conf.get("forum_display_name",fid)
                if not plat or not fid: print("[WARN] Skipping forum with no platform/ID."); continue
                last_ts=forum_conf.get("last_scraped_timestamp_utc");interval=forum_conf.get("custom_scrape_interval_hours",DEFAULT_FORUM_SCRAPE_INTERVAL_HOURS)
                if last_ts and (datetime.now(timezone.utc)-datetime.fromisoformat(last_ts.replace('Z','+00:00')).replace(tzinfo=timezone.utc)<timedelta(hours=interval)): print(f"[INFO] Forum '{dname}' not due. Skipping."); continue
                print(f"[INFO] Forum '{dname}' due. Processing...")
                if plat=="reddit":
                    if not reddit_instance: print("[ERROR] PRAW not init. Skipping Reddit forum."); continue
                    sname=fid.split('/')[-1] if '/' in fid else fid
                    posts=fetch_subreddit_posts(reddit_instance,sname,post_limit=forum_conf.get("post_limit",25),comment_limit_per_post=forum_conf.get("comment_limit_per_post",10),time_filter=forum_conf.get("time_filter","week"),search_keywords=forum_conf.get("search_keywords",[]))
                    if posts:
                        sfid=fid.replace('/','_').replace(':','_');fout_dir=FORUM_ANALYSIS_OUTPUT_ROOT_DIR/plat/sfid;fout_dir.mkdir(parents=True,exist_ok=True)
                        for pdata in posts: pid=pdata.get("id",f"unkn_{int(time.time())}");out_fn=fout_dir/f"{pid}.json";with open(out_fn,'w',encoding='utf-8') as f:json.dump(pdata,f,indent=2)
                    if update_forum_timestamp(all_forums_data,plat,fid,datetime.now(timezone.utc).isoformat()): config_changed_forums=True
            if config_changed_forums: save_target_forums(all_forums_data,str(TARGET_FORUMS_CONFIG_FILE_PATH))
    except Exception as e: print(f"[FATAL_FORUM_SCRAPE_ERROR] {e}"); import traceback; traceback.print_exc()
    
    # --- 3. Forum NLP ---
    try: _process_pending_forum_nlp_tasks()
    except Exception as e: print(f"[FATAL_FORUM_NLP_ERROR] {e}"); import traceback; traceback.print_exc()
    
    # --- 4. Discovery Processing ---
    try:
        print(f"\n[SCHEDULER_JOB][DISCOVERY_PROCESSING] --- Starting Product Discovery Source Processing ---"); config_changed_discovery=False
        all_discovery_data=load_discovery_sources(str(TARGET_DISCOVERY_CONFIG_FILE_PATH)); active_sources=get_active_discovery_sources(all_discovery_data)
        if not active_sources: print("[INFO] No active discovery sources.")
        else:
            for src_conf in active_sources:
                sid=src_conf.get("source_id");sname=src_conf.get("source_display_name","N/A");ptype=src_conf.get("platform_type");turl=src_conf.get("target_url")
                if not all([sid,sname,ptype,turl]): print("[WARN] Skipping discovery source with missing config."); continue
                last_ts=src_conf.get("last_scraped_timestamp_utc");interval=src_conf.get("custom_scrape_interval_hours",DEFAULT_DISCOVERY_SCRAPE_INTERVAL_HOURS)
                if last_ts and (datetime.now(timezone.utc)-datetime.fromisoformat(last_ts.replace('Z','+00:00')).replace(tzinfo=timezone.utc)<timedelta(hours=interval)): print(f"[INFO] Source '{sname}' not due. Skipping."); continue
                print(f"[INFO] Source '{sname}' due. Processing..."); prods=[]
                if ptype=="product_hunt": prods=scrape_product_hunt_newest(target_url=turl)
                else: print(f"[WARN] Platform '{ptype}' for '{sname}' not supported. Skipping."); continue
                if prods:
                    for pdata in prods:
                        d_date_str=datetime.fromisoformat(pdata.get('retrieved_utc').replace('Z','+00:00')).strftime('%Y-%m-%d')
                        pname_raw=pdata.get('product_name',f'unkn_{int(time.time())}'); san_pname=_sanitize_filename_component(pname_raw)
                        out_dir=PRODUCT_MENTIONS_OUTPUT_ROOT_DIR/ptype;out_dir.mkdir(parents=True,exist_ok=True)
                        out_fn=out_dir/f"{d_date_str}_{san_pname}.json";with open(out_fn,'w',encoding='utf-8') as f:json.dump(pdata,f,indent=2)
                if update_source_timestamp(all_discovery_data,sid,datetime.now(timezone.utc).isoformat()): config_changed_discovery=True
            if config_changed_discovery: save_discovery_sources(all_discovery_data,str(TARGET_DISCOVERY_CONFIG_FILE_PATH))
    except Exception as e: print(f"[FATAL_DISCOVERY_ERROR] {e}"); import traceback; traceback.print_exc()
    
    # --- 5. Keyword Trends ---
    try: _run_keyword_trend_analysis_stage()
    except Exception as e: print(f"[FATAL_KEYWORD_TREND_ERROR] {e}"); import traceback; traceback.print_exc()

    # --- 6. Consolidate All Topics ---
    try:
        print(f"\n[SCHEDULER_JOB][TOPIC_CONSOLIDATION] --- Starting Topic Consolidation Stage ---")
        if consolidate_topics(use_stemming=USE_STEMMING_FOR_CONSOLIDATION):
            print("[SCHEDULER_JOB][TOPIC_CONSOLIDATION] Topic consolidation completed successfully.")
        else:
            print("[SCHEDULER_JOB][TOPIC_CONSOLIDATION][ERROR] Topic consolidation failed or produced no output.")
    except Exception as e_consolidate:
        print(f"[SCHEDULER_JOB][TOPIC_CONSOLIDATION][FATAL_ERROR] Error during topic consolidation: {e_consolidate}")
        import traceback; traceback.print_exc()

    job_end_time = datetime.now(timezone.utc); print(f"\n[SCHEDULER_JOB][{job_end_time.isoformat()}] --- Master Job Finished. Duration: {job_end_time - job_start_time} ---")

# --- Initial Setup Functions ---
def _setup_app_targets():
    print("\n[INITIAL_SETUP][APPS] Configuring app targets..."); ANALYSIS_OUTPUT_ROOT_DIR.mkdir(parents=True, exist_ok=True)
    data=load_target_apps(str(APP_TARGET_CONFIG_FILE_PATH)); conf=[{"app_id":"com.google.android.gm","app_name":"Gmail","is_active":True},{"app_id":"com.zhiliaoapp.musically","app_name":"TikTok","is_active":True}]
    if any(add_app_target_to_config(data,d) for d in conf): save_target_apps(data,str(APP_TARGET_CONFIG_FILE_PATH))
    print("[APPS] Finished.")
def _setup_forum_targets():
    print("\n[INITIAL_SETUP][FORUMS] Configuring forum targets..."); FORUM_ANALYSIS_OUTPUT_ROOT_DIR.mkdir(parents=True,exist_ok=True); FORUM_NLP_ANALYSIS_OUTPUT_ROOT_DIR.mkdir(parents=True,exist_ok=True)
    data=load_target_forums(str(TARGET_FORUMS_CONFIG_FILE_PATH)); conf=[{"platform":"reddit","forum_identifier":"r/SideProject","search_keywords":["tool idea"],"post_limit":5,"is_active":True},{"platform":"reddit","forum_identifier":"r/Python","post_limit":10,"is_active":True}]
    if any(add_forum_target_to_config(data,d) for d in conf): save_target_forums(data,str(TARGET_FORUMS_CONFIG_FILE_PATH))
    print("[FORUMS] Finished.")
def _setup_discovery_targets():
    print("\n[INITIAL_SETUP][DISCOVERY] Configuring discovery targets..."); PRODUCT_MENTIONS_OUTPUT_ROOT_DIR.mkdir(parents=True,exist_ok=True)
    data=load_discovery_sources(str(TARGET_DISCOVERY_CONFIG_FILE_PATH)); conf=[{"source_id":"ph_new","source_display_name":"Product Hunt Newest","platform_type":"product_hunt","target_url":"https://www.producthunt.com/newest","is_active":True}]
    if any(add_discovery_source(data,d) for d in conf): save_discovery_sources(data,str(TARGET_DISCOVERY_CONFIG_FILE_PATH))
    print("[DISCOVERY] Finished.")
def _setup_keyword_trends_infrastructure():
    print("\n[INITIAL_SETUP][KEYWORDS] Configuring keyword trends infrastructure..."); KEYWORD_TRENDS_OUTPUT_ROOT_DIR.mkdir(parents=True,exist_ok=True)
    if not PROCESSED_KEYWORDS_TRACKING_FILE.exists(): _save_processed_keywords_tracking({},PROCESSED_KEYWORDS_TRACKING_FILE)
    print("[KEYWORDS] Finished.")
def _setup_synthesis_infrastructure(): # New setup helper
    print("\n[INITIAL_SETUP][SYNTHESIS] Configuring synthesis infrastructure...")
    SYNTHESIS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[INITIAL_SETUP][SYNTHESIS] Ensured synthesis output directory exists: '{SYNTHESIS_OUTPUT_DIR}'")
    # CONSOLIDATED_TOPICS_FILE will be created by consolidate_topics if it runs successfully.
    print("[SYNTHESIS] Finished.")

def initial_setup():
    print("\n[INITIAL_SETUP] --- Starting Initial Configuration Setup ---")
    _setup_app_targets()
    _setup_forum_targets()
    _setup_discovery_targets() 
    _setup_keyword_trends_infrastructure()
    _setup_synthesis_infrastructure() # New call
    print("\n[INITIAL_SETUP] --- Initial Configuration Setup Finished ---")


if __name__ == "__main__":
    if "--setup" in sys.argv: initial_setup(); sys.exit(0)
    print(f"[SCHEDULER_MAIN][{datetime.now(timezone.utc).isoformat()}] Initializing scheduler...")
    scheduler=BlockingScheduler(timezone=timezone.utc)
    scheduler.add_job(scheduled_analysis_job, 'interval', minutes=SCHEDULE_INTERVAL_MINUTES, next_run_time=datetime.now(timezone.utc)+timedelta(seconds=5))
    print(f"[SCHEDULER_MAIN] Scheduler starting... Next run in ~5s, then every {SCHEDULE_INTERVAL_MINUTES} mins. Press Ctrl+C to exit.")
    try: scheduler.start()
    except (KeyboardInterrupt,SystemExit): print("\n[SCHEDULER_MAIN] Scheduler stopped.")
    finally:
        if scheduler.running: scheduler.shutdown(wait=False)
        print("[SCHEDULER_MAIN] Shutdown complete.")
```
