import json
import os

# Module-level constant for the default configuration file path
TARGET_DISCOVERY_CONFIG_FILE_PATH = "./target_discovery_sources.json"

def load_discovery_sources(filepath: str = TARGET_DISCOVERY_CONFIG_FILE_PATH) -> list[dict]:
    """
    Loads the target discovery sources configuration from a JSON file.

    If the specified filepath does not exist, it attempts to create an empty
    configuration file (an empty JSON list `[]`) and returns an empty list.

    Args:
        filepath: The path to the JSON configuration file. 
                  Defaults to TARGET_DISCOVERY_CONFIG_FILE_PATH.

    Returns:
        A list of discovery source configuration dictionaries. Returns an empty list if
        the file does not exist (after attempting to create it), if JSON
        decoding fails, or if the file content is not a list.
    """
    if not os.path.exists(filepath):
        try:
            dir_name = os.path.dirname(filepath)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
                print(f"[DISCOVERY_CONFIG_LOAD_INFO] Created directory '{dir_name}' for config file.")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f)
            print(f"[DISCOVERY_CONFIG_LOAD_INFO] File '{filepath}' not found. Created empty config file.")
            return []
        except OSError as e:
            print(f"[DISCOVERY_CONFIG_LOAD_ERROR] Could not create directory or empty file at '{filepath}': {e}")
            return []
        except IOError as e:
            print(f"[DISCOVERY_CONFIG_LOAD_ERROR] Could not write empty file at '{filepath}': {e}")
            return []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            print(f"[DISCOVERY_CONFIG_LOAD_ERROR] Data in '{filepath}' is not a list. Returning empty config.")
            return []
        return data
    except json.JSONDecodeError:
        print(f"[DISCOVERY_CONFIG_LOAD_ERROR] Failed to decode JSON from '{filepath}'. File might be corrupted. Returning empty config.")
        return []
    except IOError as e:
        print(f"[DISCOVERY_CONFIG_LOAD_ERROR] Could not read file '{filepath}': {e}")
        return []
    except Exception as e:
        print(f"[DISCOVERY_CONFIG_LOAD_ERROR] Unexpected error loading '{filepath}': {e}")
        return []

def save_discovery_sources(sources_data: list[dict], filepath: str = TARGET_DISCOVERY_CONFIG_FILE_PATH) -> bool:
    """
    Saves the list of discovery source configuration dictionaries to a JSON file.

    Args:
        sources_data: A list of discovery source configuration dictionaries to save.
        filepath: The path to the JSON configuration file. 
                  Defaults to TARGET_DISCOVERY_CONFIG_FILE_PATH.

    Returns:
        True if saving was successful, False otherwise.
    """
    try:
        dir_name = os.path.dirname(filepath)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            print(f"[DISCOVERY_CONFIG_SAVE_INFO] Created directory '{dir_name}' for config file.")
            
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(sources_data, f, indent=2, ensure_ascii=False)
        print(f"[DISCOVERY_CONFIG_SAVE_SUCCESS] Saved configuration for {len(sources_data)} discovery source(s) to '{filepath}'.")
        return True
    except OSError as e:
        print(f"[DISCOVERY_CONFIG_SAVE_ERROR] Could not create directory for '{filepath}': {e}")
        return False
    except IOError as e:
        print(f"[DISCOVERY_CONFIG_SAVE_ERROR] Could not write config to file '{filepath}': {e}")
        return False
    except TypeError as e:
        print(f"[DISCOVERY_CONFIG_SAVE_ERROR] Data for discovery sources is not JSON serializable for '{filepath}': {e}")
        return False
    except Exception as e:
        print(f"[DISCOVERY_CONFIG_SAVE_ERROR] Unexpected error saving to '{filepath}': {e}")
        return False

def get_active_discovery_sources(sources_data: list[dict]) -> list[dict]:
    """
    Filters a list of discovery source configurations to return only active ones.

    Args:
        sources_data: A list of discovery source configuration dictionaries.

    Returns:
        A new list containing only those configurations where 'is_active' is True.
    """
    if not isinstance(sources_data, list):
        print("[DISCOVERY_CONFIG_FILTER_WARN] Input 'sources_data' is not a list. Returning empty list.")
        return []
    active_sources = [
        source for source in sources_data 
        if isinstance(source, dict) and source.get("is_active") is True
    ]
    print(f"[DISCOVERY_CONFIG_FILTER_INFO] Found {len(active_sources)} active discovery source(s) out of {len(sources_data)} total.")
    return active_sources

def update_source_timestamp(sources_data: list[dict], source_id: str, timestamp_utc_iso: str) -> bool:
    """
    Updates the 'last_scraped_timestamp_utc' for a specific discovery source in the list.

    This function modifies the `sources_data` list in place.

    Args:
        sources_data: The list of discovery source configuration dictionaries.
        source_id: The 'source_id' of the discovery source to update.
        timestamp_utc_iso: The new ISO format UTC timestamp string.

    Returns:
        True if the source was found and its timestamp updated, False otherwise.
    """
    if not isinstance(sources_data, list):
        print("[DISCOVERY_CONFIG_UPDATE_ERROR] 'sources_data' must be a list.")
        return False
        
    source_found = False
    for source_config in sources_data:
        if isinstance(source_config, dict) and source_config.get("source_id") == source_id:
            source_config["last_scraped_timestamp_utc"] = timestamp_utc_iso
            source_found = True
            break 
    
    if source_found:
        print(f"[DISCOVERY_CONFIG_UPDATE_INFO] Timestamp updated for source_id '{source_id}' to '{timestamp_utc_iso}'.")
    else:
        print(f"[DISCOVERY_CONFIG_UPDATE_WARN] source_id '{source_id}' not found in configuration. Timestamp not updated.")
    return source_found

def add_discovery_source(sources_data: list[dict], source_config_to_add: dict) -> bool:
    """
    Adds a new discovery source to the list of configurations.

    Checks if a source with the same 'source_id' already exists. If so, it does not 
    add the source and returns False. Otherwise, it adds the new configuration with 
    defaults for any missing optional fields. This function modifies `sources_data` in place.

    Args:
        sources_data: The list of discovery source configuration dictionaries.
        source_config_to_add: A dictionary containing details for the new source.
                              Must include 'source_id', 'source_display_name', 
                              'platform_type', and 'target_url'.
                              Optional fields: 'is_active' (default True), 
                              'custom_scrape_interval_hours' (default 24).
                              'last_scraped_timestamp_utc' is always initialized to None.

    Returns:
        True if the source was successfully added, False if it already exists or
        if `source_config_to_add` is invalid.
    """
    if not isinstance(sources_data, list):
        print("[DISCOVERY_CONFIG_ADD_ERROR] 'sources_data' must be a list.")
        return False
    
    required_keys = ["source_id", "source_display_name", "platform_type", "target_url"]
    if not isinstance(source_config_to_add, dict) or \
       not all(key in source_config_to_add for key in required_keys):
        print(f"[DISCOVERY_CONFIG_ADD_ERROR] 'source_config_to_add' must be a dict and contain required keys: {', '.join(required_keys)}.")
        return False

    target_source_id = source_config_to_add['source_id']
    
    for existing_source in sources_data:
        if isinstance(existing_source, dict) and existing_source.get("source_id") == target_source_id:
            print(f"[DISCOVERY_CONFIG_ADD_INFO] Discovery source '{target_source_id}' already exists. Not adding.")
            return False

    new_entry = {
        "source_id": target_source_id,
        "source_display_name": source_config_to_add['source_display_name'],
        "platform_type": source_config_to_add['platform_type'], # e.g., "product_hunt", "generic_website"
        "target_url": source_config_to_add['target_url'],
        "is_active": source_config_to_add.get('is_active', True),
        "custom_scrape_interval_hours": source_config_to_add.get('custom_scrape_interval_hours', 24),
        "last_scraped_timestamp_utc": None # Always initialized to None for a new entry
        # Add other platform-specific parameters here if needed, e.g., "parser_type"
    }
    sources_data.append(new_entry)
    print(f"[DISCOVERY_CONFIG_ADD_SUCCESS] Discovery source '{target_source_id}' ({new_entry['source_display_name']}) added to configuration list.")
    return True

# No main execution block as this is a library module.
```
