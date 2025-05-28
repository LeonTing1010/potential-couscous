import os
import json
import time # For potential delays
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler

# Assuming modules are in the same directory or PYTHONPATH
from target_config_manager import (
    load_target_apps,
    save_target_apps,
    get_active_target_apps,
    update_app_timestamp,
    add_target_app,
    TARGET_CONFIG_FILE_PATH # Default config file path
)
from app_analyzer_module import process_single_app_reviews

# --- Configuration ---
SCHEDULE_INTERVAL_MINUTES = 15 # How often the scheduler job itself runs to check app schedules
DEFAULT_APP_SCRAPE_INTERVAL_HOURS = 24 # Default interval if not specified in app's config
ANALYSIS_OUTPUT_ROOT_DIR = "./all_app_analyses" # Root directory for saving analysis JSON files

def scheduled_analysis_job():
    """
    The core job executed by the scheduler. It loads app configurations from a JSON file,
    checks if each active app is due for analysis based on its individual schedule,
    processes reviews for due apps, saves the analysis to a JSON file, and updates
    the app's last scraped timestamp in the configuration file.
    """
    job_start_time = datetime.now(timezone.utc)
    print(f"\n[SCHEDULER_JOB][{job_start_time.isoformat()}] --- Starting scheduled analysis job ---")

    try:
        all_apps_data = load_target_apps(TARGET_CONFIG_FILE_PATH)
        if not all_apps_data and all_apps_data != []: # Check for None or other error indicators if load_target_apps could return them
             print("[SCHEDULER_JOB][WARN] No app configuration data loaded. Might be an issue with config file. Aborting job run.")
             # If load_target_apps returns [] for an empty or new file, this is fine.
             # The check `if not all_apps_data:` (when it's an empty list) will be handled below.
        
        active_apps = get_active_target_apps(all_apps_data)

        if not active_apps:
            print("[SCHEDULER_JOB][INFO] No active target apps found in configuration to process at this time.")
            return

        print(f"[SCHEDULER_JOB][INFO] Found {len(active_apps)} active app(s) to check for processing.")
        
        config_changed = False # Flag to track if target_apps.json needs to be re-saved

        for app_config in active_apps:
            app_id = app_config.get("app_id")
            app_name = app_config.get("app_name", "N/A")
            
            if not app_id:
                print("[SCHEDULER_JOB][WARN] Found an active app config with missing app_id. Skipping.")
                continue

            print(f"\n[SCHEDULER_JOB][INFO] Checking schedule for app: '{app_name}' (ID: {app_id})")

            # Scheduling Logic for individual app
            last_ts_str = app_config.get("last_successful_analysis_timestamp_utc")
            interval_hours = app_config.get("custom_scrape_interval_hours", DEFAULT_APP_SCRAPE_INTERVAL_HOURS)

            if last_ts_str:
                try:
                    last_ts_obj = datetime.fromisoformat(last_ts_str.replace('Z', '+00:00'))
                    if not last_ts_obj.tzinfo: # Ensure timezone awareness if fromisoformat doesn't add it
                        last_ts_obj = last_ts_obj.replace(tzinfo=timezone.utc)
                        
                    if datetime.now(timezone.utc) - last_ts_obj < timedelta(hours=interval_hours):
                        print(f"[SCHEDULER_JOB][INFO] App '{app_name}' (ID: {app_id}) is not due for analysis yet. Last analyzed: {last_ts_str}. Interval: {interval_hours}h. Skipping.")
                        continue
                except ValueError as ve:
                    print(f"[SCHEDULER_JOB][WARN] Invalid timestamp format for '{app_name}' (ID: {app_id}): {last_ts_str}. Error: {ve}. Will attempt processing.")
            
            print(f"[SCHEDULER_JOB][INFO] App '{app_name}' (ID: {app_id}) is due for processing.")
            
            try:
                analysis_result = process_single_app_reviews(
                    app_id=app_id,
                    app_name=app_name
                )

                if analysis_result and "error" not in analysis_result:
                    print(f"[SCHEDULER_JOB][SUCCESS] Analysis successful for '{app_name}' (ID: {app_id}). Saving result to file...")
                    
                    # Save output as JSON file
                    app_output_dir = os.path.join(ANALYSIS_OUTPUT_ROOT_DIR, app_id.replace('.', '_')) # Sanitize app_id for dir name
                    try:
                        os.makedirs(app_output_dir, exist_ok=True)
                        
                        # Use analysis_timestamp_utc from the result for filename consistency
                        analysis_ts_str = analysis_result.get('analysis_timestamp_utc', job_start_time.isoformat())
                        analysis_dt_obj = datetime.fromisoformat(analysis_ts_str.replace('Z', '+00:00'))
                        if not analysis_dt_obj.tzinfo:
                            analysis_dt_obj = analysis_dt_obj.replace(tzinfo=timezone.utc)
                        
                        filename_ts_part = analysis_dt_obj.strftime("%Y%m%d%H%M%SZ")
                        output_filename = os.path.join(app_output_dir, f"{app_id.replace('.', '_')}_{filename_ts_part}.json")
                        
                        with open(output_filename, 'w', encoding='utf-8') as f:
                            json.dump(analysis_result, f, indent=2, ensure_ascii=False)
                        print(f"[SCHEDULER_JOB][INFO] Analysis result saved for '{app_name}' to '{output_filename}'.")

                        # Update configuration file with new timestamp
                        timestamp_to_save_in_config = analysis_result['analysis_timestamp_utc']
                        if update_app_timestamp(all_apps_data, app_id, timestamp_to_save_in_config):
                            config_changed = True # Mark that config needs saving
                            print(f"[SCHEDULER_JOB][INFO] Marked 'last_successful_analysis_timestamp_utc' for '{app_name}' (ID: {app_id}) for update in config.")
                        else: # Should not happen if app_id is from loaded config
                            print(f"[SCHEDULER_JOB][WARN] Failed to find app '{app_name}' (ID: {app_id}) in loaded config for timestamp update.")

                    except OSError as ose:
                        print(f"[SCHEDULER_JOB][ERROR] Could not create directory '{app_output_dir}': {ose}")
                    except IOError as ioe:
                        print(f"[SCHEDULER_JOB][ERROR] Could not write analysis file '{output_filename}': {ioe}")
                    except Exception as e_file: # Catch other file-related errors
                         print(f"[SCHEDULER_JOB][ERROR] Unexpected error during file operations for '{app_name}': {e_file}")

                elif analysis_result and "error" in analysis_result:
                    print(f"[SCHEDULER_JOB][ERROR] LLM analysis failed for '{app_name}' (ID: {app_id}). Error: {analysis_result.get('error')}, Details: {analysis_result.get('details')}")
                else:
                    print(f"[SCHEDULER_JOB][WARN] Review processing did not yield an analysis for '{app_name}' (ID: {app_id}). (Scraping might have failed or no reviews found).")

            except Exception as e_app:
                print(f"[SCHEDULER_JOB][CRITICAL_APP_ERROR] An unexpected error occurred while processing app '{app_name}' (ID: {app_id}): {type(e_app).__name__} - {e_app}")
                import traceback
                print(f"[SCHEDULER_JOB][APP_TRACE]\n{traceback.format_exc()}")
            
            print(f"[SCHEDULER_JOB][INFO] Finished checking/processing for app: '{app_name}' (ID: {app_id}).")
        
        # After iterating through all apps, save the configuration if it changed
        if config_changed:
            print("[SCHEDULER_JOB][INFO] Configuration changed, saving updates to target_apps.json...")
            if save_target_apps(all_apps_data, TARGET_CONFIG_FILE_PATH):
                print("[SCHEDULER_JOB][INFO] Successfully saved updated app configurations.")
            else:
                print("[SCHEDULER_JOB][ERROR] Failed to save updated app configurations to JSON file.")

    except Exception as e_job:
        print(f"[SCHEDULER_JOB][CRITICAL_JOB_ERROR] A critical error occurred during the scheduled job run: {type(e_job).__name__} - {e_job}")
        import traceback
        print(f"[SCHEDULER_JOB][JOB_TRACE]\n{traceback.format_exc()}")
    finally:
        job_end_time = datetime.now(timezone.utc)
        duration = job_end_time - job_start_time
        print(f"[SCHEDULER_JOB][{job_end_time.isoformat()}] --- Scheduled analysis job finished. Duration: {duration} ---")


def initial_setup_add_target_apps():
    """
    Helper function to add/update initial target apps in the JSON configuration file.
    """
    print("\n[INITIAL_SETUP] Attempting to add/verify initial target apps in JSON config...")
    
    # Load existing data first
    loaded_apps_data = load_target_apps(TARGET_CONFIG_FILE_PATH)
    
    # Apps to ensure are in the config
    apps_to_configure = [
        {"app_id": "com.google.android.gm", "app_name": "Gmail", "platform": "google_play", "is_active": True, "custom_scrape_interval_hours": 24},
        {"app_id": "com.zhiliaoapp.musically", "app_name": "TikTok", "platform": "google_play", "is_active": True, "custom_scrape_interval_hours": 48},
        {"app_id": "org.mozilla.firefox", "app_name": "Firefox Browser", "platform": "google_play", "is_active": True, "custom_scrape_interval_hours": 72},
        {"app_id": "com.twitter.android", "app_name": "X (Formerly Twitter)", "platform": "google_play", "is_active": False, "custom_scrape_interval_hours": 24},
    ]

    config_updated_by_setup = False
    for app_detail_dict in apps_to_configure:
        # add_target_app modifies loaded_apps_data in-place and returns True if a new app was added
        if add_target_app(loaded_apps_data, app_detail_dict): 
            config_updated_by_setup = True
            print(f"[INITIAL_SETUP] Added '{app_detail_dict['app_name']}' to configuration list.")
        # If app already exists, add_target_app prints a message and returns False.
        # One could add logic here to update existing apps if needed, e.g., by removing and re-adding or merging.

    if config_updated_by_setup:
        if save_target_apps(loaded_apps_data, TARGET_CONFIG_FILE_PATH):
            print("[INITIAL_SETUP] Successfully saved updated configuration from initial setup.")
        else:
            print("[INITIAL_SETUP][ERROR] Failed to save configuration after initial setup.")
    else:
        print("[INITIAL_SETUP] No new apps were added; configuration remains unchanged by setup.")
    
    print("[INITIAL_SETUP] Finished adding/verifying initial target apps.")


if __name__ == "__main__":
    import sys
    if "--setup" in sys.argv:
        initial_setup_add_target_apps()
        print("-" * 70)
        print("Initial setup complete. Target apps configuration file has been populated/updated.")
        print("Scheduler will not start when --setup is used. Run without --setup to start scheduler.")
        print("-" * 70)
        sys.exit(0)

    print(f"[SCHEDULER_MAIN][{datetime.now(timezone.utc).isoformat()}] Initializing scheduler...")
    scheduler = BlockingScheduler(timezone=timezone.utc) 

    print(f"[SCHEDULER_MAIN] Scheduling 'scheduled_analysis_job' to run every {SCHEDULE_INTERVAL_MINUTES} minutes.")
    scheduler.add_job(
        scheduled_analysis_job,
        trigger='interval',
        minutes=SCHEDULE_INTERVAL_MINUTES,
        next_run_time=datetime.now(timezone.utc)
    )

    print(f"[SCHEDULER_MAIN] Scheduler starting. Next run is immediate, then every {SCHEDULE_INTERVAL_MINUTES} minutes.")
    print("[SCHEDULER_MAIN] Press Ctrl+C to exit.")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\n[SCHEDULER_MAIN] Scheduler stopped by user (Ctrl+C or SystemExit).")
    except Exception as e_sched:
        print(f"[SCHEDULER_MAIN][CRITICAL_SCHEDULER_ERROR] Scheduler failed critically: {type(e_sched).__name__} - {e_sched}")
        import traceback
        print(f"[SCHEDULER_MAIN][SCHEDULER_TRACE]\n{traceback.format_exc()}")
    finally:
        if scheduler.running:
            print("[SCHEDULER_MAIN] Shutting down scheduler...")
            scheduler.shutdown()
        print("[SCHEDULER_MAIN] Scheduler shutdown complete.")

```
