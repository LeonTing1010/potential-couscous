import json
import os
from datetime import datetime, timezone # For potential timestamp validation/manipulation if needed

# Module-level constant for the default configuration file path
TARGET_CONFIG_FILE_PATH = "./target_apps.json"

def load_target_apps(filepath: str = TARGET_CONFIG_FILE_PATH) -> list[dict]:
    """
    Loads the target apps configuration from a JSON file.

    If the specified filepath does not exist, it attempts to create an empty
    configuration file (an empty JSON list `[]`) and returns an empty list.

    Args:
        filepath: The path to the JSON configuration file. 
                  Defaults to TARGET_CONFIG_FILE_PATH.

    Returns:
        A list of app configuration dictionaries. Returns an empty list if
        the file does not exist (after attempting to create it), if JSON
        decoding fails, or if the file content is not a list.
    """
    if not os.path.exists(filepath):
        try:
            # Ensure directory exists if filepath includes one
            dir_name = os.path.dirname(filepath)
            if dir_name and not os.path.exists(dir_name): # Only create if there's a directory part and it doesn't exist
                os.makedirs(dir_name, exist_ok=True)
                print(f"[CONFIG_LOAD_INFO] Created directory '{dir_name}' for configuration file.")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f)
            print(f"[CONFIG_LOAD_INFO] File '{filepath}' not found. Created an empty configuration file.")
            return []
        except OSError as e:
            print(f"[CONFIG_LOAD_ERROR] Could not create directory for empty file at '{filepath}': {e}")
            return []
        except IOError as e:
            print(f"[CONFIG_LOAD_ERROR] Could not write empty file at '{filepath}': {e}")
            return []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            print(f"[CONFIG_LOAD_ERROR] Data in '{filepath}' is not a list. Returning empty configuration.")
            return []
        # Optionally, add validation for the structure of each dict in the list here
        return data
    except json.JSONDecodeError:
        print(f"[CONFIG_LOAD_ERROR] Failed to decode JSON from '{filepath}'. File might be corrupted or not valid JSON. Returning empty configuration.")
        return []
    except IOError as e:
        print(f"[CONFIG_LOAD_ERROR] Could not read file '{filepath}': {e}")
        return []
    except Exception as e: # Catch-all for other unexpected errors
        print(f"[CONFIG_LOAD_ERROR] An unexpected error occurred while loading configuration from '{filepath}': {e}")
        return []

def save_target_apps(apps_data: list[dict], filepath: str = TARGET_CONFIG_FILE_PATH) -> bool:
    """
    Saves the list of app configuration dictionaries to a JSON file.

    Args:
        apps_data: A list of app configuration dictionaries to save.
        filepath: The path to the JSON configuration file. 
                  Defaults to TARGET_CONFIG_FILE_PATH.

    Returns:
        True if saving was successful, False otherwise.
    """
    try:
        dir_name = os.path.dirname(filepath)
        if dir_name and not os.path.exists(dir_name): # Only create if there's a directory part and it doesn't exist
            os.makedirs(dir_name, exist_ok=True)
            print(f"[CONFIG_SAVE_INFO] Created directory '{dir_name}' for configuration file.")
            
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(apps_data, f, indent=2, ensure_ascii=False)
        print(f"[CONFIG_SAVE_SUCCESS] Successfully saved configuration ({len(apps_data)} app(s)) to '{filepath}'.")
        return True
    except OSError as e: # For os.makedirs error
        print(f"[CONFIG_SAVE_ERROR] Could not create directory for '{filepath}': {e}")
        return False
    except IOError as e: # For file writing error
        print(f"[CONFIG_SAVE_ERROR] Could not write configuration to file '{filepath}': {e}")
        return False
    except TypeError as e: # For json.dump if apps_data is not serializable (e.g., contains non-basic types)
        print(f"[CONFIG_SAVE_ERROR] Data provided is not JSON serializable for '{filepath}': {e}")
        return False
    except Exception as e: # Catch-all for other unexpected errors
        print(f"[CONFIG_SAVE_ERROR] An unexpected error occurred while saving configuration to '{filepath}': {e}")
        return False

def get_active_target_apps(apps_data: list[dict]) -> list[dict]:
    """
    Filters a list of app configurations to return only active ones.

    Args:
        apps_data: A list of app configuration dictionaries.

    Returns:
        A new list containing only those app configurations where 'is_active' is True.
    """
    if not isinstance(apps_data, list):
        print("[CONFIG_FILTER_WARN] Input 'apps_data' is not a list. Returning empty list.")
        return []
    active_apps = [app for app in apps_data if isinstance(app, dict) and app.get("is_active") is True]
    print(f"[CONFIG_FILTER_INFO] Found {len(active_apps)} active app(s) out of {len(apps_data)} total.")
    return active_apps

def update_app_timestamp(apps_data: list[dict], app_id: str, timestamp_utc_iso: str) -> bool:
    """
    Updates the 'last_successful_analysis_timestamp_utc' for a specific app in the list.

    This function modifies the `apps_data` list in place.

    Args:
        apps_data: The list of app configuration dictionaries.
        app_id: The 'app_id' of the app to update.
        timestamp_utc_iso: The new ISO format UTC timestamp string.

    Returns:
        True if the app was found and its timestamp updated, False otherwise.
    """
    if not isinstance(apps_data, list):
        print("[CONFIG_UPDATE_ERROR] 'apps_data' must be a list.")
        return False
        
    app_found = False
    for app_config in apps_data:
        if isinstance(app_config, dict) and app_config.get("app_id") == app_id:
            app_config["last_successful_analysis_timestamp_utc"] = timestamp_utc_iso
            app_found = True
            break 
    
    if app_found:
        print(f"[CONFIG_UPDATE_INFO] Timestamp updated for app_id '{app_id}' to '{timestamp_utc_iso}'.")
    else:
        print(f"[CONFIG_UPDATE_WARN] app_id '{app_id}' not found in configuration. Timestamp not updated.")
    return app_found

def add_target_app(apps_data: list[dict], app_config_to_add: dict, platform: str = "google_play", custom_scrape_interval_hours: int = 24) -> bool:
    """
    Adds a new target app to the list of app configurations.

    Checks if an app with the same 'app_id' already exists. If so, it does not add
    the app and returns False. Otherwise, it adds the new app configuration.
    This function modifies `apps_data` in place.

    Args:
        apps_data: The list of app configuration dictionaries.
        app_config_to_add: A dictionary containing details for the new app. 
                           Must include 'app_id' and 'app_name'.
                           Can optionally include 'platform', 'is_active', 
                           and 'custom_scrape_interval_hours' to override defaults.
        platform: Default platform if not specified in `app_config_to_add`.
        custom_scrape_interval_hours: Default scrape interval if not in `app_config_to_add`.

    Returns:
        True if the app was successfully added to the list, False if the app
        already exists or if `app_config_to_add` is invalid.
    """
    if not isinstance(apps_data, list):
        print("[CONFIG_ADD_ERROR] 'apps_data' must be a list.")
        return False
    if not isinstance(app_config_to_add, dict) or \
       "app_id" not in app_config_to_add or \
       "app_name" not in app_config_to_add:
        print("[CONFIG_ADD_ERROR] 'app_config_to_add' dictionary must be valid and contain 'app_id' and 'app_name'.")
        return False

    target_app_id = app_config_to_add['app_id']
    
    for existing_app in apps_data:
        if isinstance(existing_app, dict) and existing_app.get("app_id") == target_app_id:
            print(f"[CONFIG_ADD_INFO] App '{target_app_id}' ({existing_app.get('app_name')}) already exists in configuration. Not adding.")
            return False # App already exists

    new_entry = {
        "app_id": target_app_id,
        "app_name": app_config_to_add['app_name'],
        "platform": app_config_to_add.get('platform', platform),
        "is_active": app_config_to_add.get('is_active', True), # Default to active
        "custom_scrape_interval_hours": app_config_to_add.get('custom_scrape_interval_hours', custom_scrape_interval_hours),
        "last_successful_analysis_timestamp_utc": None # Initialized to None
    }
    apps_data.append(new_entry)
    print(f"[CONFIG_ADD_SUCCESS] App '{target_app_id}' ({new_entry['app_name']}) added to configuration list.")
    return True

# No main execution block as this is a library module.
```
