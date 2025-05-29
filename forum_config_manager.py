import json
import os

# Module-level constant for the default configuration file path
TARGET_FORUMS_CONFIG_FILE_PATH = "./target_forums.json"

def load_target_forums(filepath: str = TARGET_FORUMS_CONFIG_FILE_PATH) -> list[dict]:
    """
    Loads the target forums configuration from a JSON file.

    If the specified filepath does not exist, it attempts to create an empty
    configuration file (an empty JSON list `[]`) and returns an empty list.

    Args:
        filepath: The path to the JSON configuration file. 
                  Defaults to TARGET_FORUMS_CONFIG_FILE_PATH.

    Returns:
        A list of forum configuration dictionaries. Returns an empty list if
        the file does not exist (after attempting to create it), if JSON
        decoding fails, or if the file content is not a list.
    """
    if not os.path.exists(filepath):
        try:
            dir_name = os.path.dirname(filepath)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
                print(f"[FORUM_CONFIG_LOAD_INFO] Created directory '{dir_name}' for config file.")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([], f)
            print(f"[FORUM_CONFIG_LOAD_INFO] File '{filepath}' not found. Created empty config file.")
            return []
        except OSError as e:
            print(f"[FORUM_CONFIG_LOAD_ERROR] Could not create directory or empty file at '{filepath}': {e}")
            return []
        except IOError as e:
            print(f"[FORUM_CONFIG_LOAD_ERROR] Could not write empty file at '{filepath}': {e}")
            return []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            print(f"[FORUM_CONFIG_LOAD_ERROR] Data in '{filepath}' is not a list. Returning empty config.")
            return []
        return data
    except json.JSONDecodeError:
        print(f"[FORUM_CONFIG_LOAD_ERROR] Failed to decode JSON from '{filepath}'. File might be corrupted. Returning empty config.")
        return []
    except IOError as e:
        print(f"[FORUM_CONFIG_LOAD_ERROR] Could not read file '{filepath}': {e}")
        return []
    except Exception as e:
        print(f"[FORUM_CONFIG_LOAD_ERROR] Unexpected error loading '{filepath}': {e}")
        return []

def save_target_forums(forums_data: list[dict], filepath: str = TARGET_FORUMS_CONFIG_FILE_PATH) -> bool:
    """
    Saves the list of forum configuration dictionaries to a JSON file.

    Args:
        forums_data: A list of forum configuration dictionaries to save.
        filepath: The path to the JSON configuration file. 
                  Defaults to TARGET_FORUMS_CONFIG_FILE_PATH.

    Returns:
        True if saving was successful, False otherwise.
    """
    try:
        dir_name = os.path.dirname(filepath)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)
            print(f"[FORUM_CONFIG_SAVE_INFO] Created directory '{dir_name}' for config file.")
            
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(forums_data, f, indent=2, ensure_ascii=False)
        print(f"[FORUM_CONFIG_SAVE_SUCCESS] Saved configuration for {len(forums_data)} forum(s) to '{filepath}'.")
        return True
    except OSError as e:
        print(f"[FORUM_CONFIG_SAVE_ERROR] Could not create directory for '{filepath}': {e}")
        return False
    except IOError as e:
        print(f"[FORUM_CONFIG_SAVE_ERROR] Could not write config to file '{filepath}': {e}")
        return False
    except TypeError as e:
        print(f"[FORUM_CONFIG_SAVE_ERROR] Data for forums is not JSON serializable for '{filepath}': {e}")
        return False
    except Exception as e:
        print(f"[FORUM_CONFIG_SAVE_ERROR] Unexpected error saving to '{filepath}': {e}")
        return False

def get_active_target_forums(forums_data: list[dict]) -> list[dict]:
    """
    Filters a list of forum configurations to return only active ones.

    Args:
        forums_data: A list of forum configuration dictionaries.

    Returns:
        A new list containing only those forum configurations where 'is_active' is True.
    """
    if not isinstance(forums_data, list):
        print("[FORUM_CONFIG_FILTER_WARN] Input 'forums_data' is not a list. Returning empty list.")
        return []
    active_forums = [
        forum for forum in forums_data 
        if isinstance(forum, dict) and forum.get("is_active") is True
    ]
    print(f"[FORUM_CONFIG_FILTER_INFO] Found {len(active_forums)} active forum(s) out of {len(forums_data)} total.")
    return active_forums

def update_forum_timestamp(forums_data: list[dict], platform: str, forum_identifier: str, timestamp_utc_iso: str) -> bool:
    """
    Updates the 'last_scraped_timestamp_utc' for a specific forum in the list.

    This function modifies the `forums_data` list in place.

    Args:
        forums_data: The list of forum configuration dictionaries.
        platform: The platform of the forum to update (e.g., "reddit").
        forum_identifier: The identifier of the forum (e.g., "Python" for r/Python).
        timestamp_utc_iso: The new ISO format UTC timestamp string.

    Returns:
        True if the forum was found and its timestamp updated, False otherwise.
    """
    if not isinstance(forums_data, list):
        print("[FORUM_CONFIG_UPDATE_ERROR] 'forums_data' must be a list.")
        return False
        
    forum_found = False
    for forum_config in forums_data:
        if isinstance(forum_config, dict) and \
           forum_config.get("platform") == platform and \
           forum_config.get("forum_identifier") == forum_identifier:
            forum_config["last_scraped_timestamp_utc"] = timestamp_utc_iso
            forum_found = True
            break 
    
    if forum_found:
        print(f"[FORUM_CONFIG_UPDATE_INFO] Timestamp updated for forum '{platform}:{forum_identifier}' to '{timestamp_utc_iso}'.")
    else:
        print(f"[FORUM_CONFIG_UPDATE_WARN] Forum '{platform}:{forum_identifier}' not found in config. Timestamp not updated.")
    return forum_found

def add_target_forum(forums_data: list[dict], forum_config_to_add: dict) -> bool:
    """
    Adds a new target forum to the list of forum configurations.

    Checks if a forum with the same 'platform' and 'forum_identifier' already exists.
    If so, it does not add the forum and returns False. Otherwise, it adds the new
    forum configuration with defaults for any missing optional fields.
    This function modifies `forums_data` in place.

    Args:
        forums_data: The list of forum configuration dictionaries.
        forum_config_to_add: A dictionary containing details for the new forum.
                           Must include 'platform' and 'forum_identifier'.
                           Optional fields: 'forum_display_name', 'is_active', 
                           'search_keywords', 'post_limit', 'comment_limit_per_post',
                           'time_filter', 'scrape_method', 'custom_scrape_interval_hours'.

    Returns:
        True if the forum was successfully added to the list, False if the forum
        already exists or if `forum_config_to_add` is invalid.
    """
    if not isinstance(forums_data, list):
        print("[FORUM_CONFIG_ADD_ERROR] 'forums_data' must be a list.")
        return False
    if not isinstance(forum_config_to_add, dict) or \
       "platform" not in forum_config_to_add or \
       "forum_identifier" not in forum_config_to_add:
        print("[FORUM_CONFIG_ADD_ERROR] 'forum_config_to_add' must be a dict and contain 'platform' and 'forum_identifier'.")
        return False

    target_platform = forum_config_to_add['platform']
    target_identifier = forum_config_to_add['forum_identifier']
    
    for existing_forum in forums_data:
        if isinstance(existing_forum, dict) and \
           existing_forum.get("platform") == target_platform and \
           existing_forum.get("forum_identifier") == target_identifier:
            print(f"[FORUM_CONFIG_ADD_INFO] Forum '{target_platform}:{target_identifier}' already exists. Not adding.")
            return False

    new_entry = {
        "platform": target_platform,
        "forum_identifier": target_identifier,
        "forum_display_name": forum_config_to_add.get('forum_display_name', target_identifier),
        "is_active": forum_config_to_add.get('is_active', True),
        "search_keywords": forum_config_to_add.get('search_keywords', []),
        "post_limit": forum_config_to_add.get('post_limit', 25),
        "comment_limit_per_post": forum_config_to_add.get('comment_limit_per_post', 10),
        "time_filter": forum_config_to_add.get('time_filter', 'week'), # e.g., for Reddit
        "scrape_method": forum_config_to_add.get('scrape_method', 'new'), # e.g., 'new', 'search', 'top'
        "custom_scrape_interval_hours": forum_config_to_add.get('custom_scrape_interval_hours', 24),
        "last_scraped_timestamp_utc": None # Always initialized to None for a new entry
    }
    forums_data.append(new_entry)
    print(f"[FORUM_CONFIG_ADD_SUCCESS] Forum '{target_platform}:{target_identifier}' added to configuration list.")
    return True

# No main execution block as this is a library module.
```
