import os
import pymongo
from pymongo import MongoClient, errors as pymongo_errors # Use an alias for clarity
from datetime import datetime # Though not directly used for conversion, good to have if needed

# Default MongoDB URI if not provided or found in environment variables
DEFAULT_MONGODB_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "demand_radar_db"
ANALYZED_APPS_COLLECTION = "analyzed_apps"
TARGET_APPS_COLLECTION = "target_apps_config" # New constant for scheduler target apps

def get_db_client(mongodb_uri: str = None) -> MongoClient | None:
    """
    Establishes a connection to a MongoDB server.

    Args:
        mongodb_uri: Optional MongoDB connection URI. If None, it tries to
                     get it from the 'MONGODB_URI' environment variable.
                     If still None, defaults to 'mongodb://localhost:27017/'.

    Returns:
        A pymongo.MongoClient instance if connection is successful, otherwise None.
    """
    uri_to_use = mongodb_uri
    if uri_to_use is None:
        uri_to_use = os.getenv("MONGODB_URI")
    if uri_to_use is None:
        uri_to_use = DEFAULT_MONGODB_URI
        print(f"[DB_CLIENT_INFO] No MongoDB URI provided or found in env 'MONGODB_URI'; using default: {uri_to_use}")

    try:
        print(f"[DB_CLIENT_INFO] Attempting to connect to MongoDB at: {uri_to_use}")
        client = MongoClient(uri_to_use, serverSelectionTimeoutMS=5000)
        client.admin.command('ismaster')
        print(f"[DB_CLIENT_SUCCESS] Successfully connected to MongoDB server at {uri_to_use.split('@')[-1] if '@' in uri_to_use else uri_to_use}.")
        return client
    except pymongo_errors.ConnectionFailure as e:
        print(f"[DB_CLIENT_ERROR] MongoDB connection failed for URI (credentials hidden): {e}")
        return None
    except Exception as e:
        print(f"[DB_CLIENT_ERROR] An unexpected error occurred while creating MongoDB client: {e}")
        return None

def get_demand_radar_db(db_client: MongoClient):
    """
    Gets a handle to the 'demand_radar_db' database from a client instance.

    Args:
        db_client: A pymongo.MongoClient instance.

    Returns:
        A MongoDB database handle if db_client is valid, otherwise None.
    """
    if not isinstance(db_client, MongoClient):
        print("[DB_GET_DB_ERROR] Invalid database client provided. Cannot get database handle.")
        return None
    return db_client[DATABASE_NAME]

def save_analysis_result(db_handle, analysis_data: dict) -> str | None:
    """
    Saves analysis data to the 'analyzed_apps' collection.
    Args:
        db_handle: A MongoDB database handle.
        analysis_data: A dictionary containing the analysis results to save.
    Returns:
        The string representation of the inserted document's _id if successful, otherwise None.
    """
    if not db_handle:
        print("[DB_SAVE_ERROR] Database handle is invalid or None. Cannot save analysis.")
        return None
    if not analysis_data or not isinstance(analysis_data, dict):
        print("[DB_SAVE_ERROR] Invalid analysis data: must be a non-empty dictionary.")
        return None
    
    try:
        collection = db_handle[ANALYZED_APPS_COLLECTION]
        result = collection.insert_one(analysis_data)
        inserted_id_str = str(result.inserted_id)
        print(f"[DB_SAVE_SUCCESS] Analysis data saved to collection '{ANALYZED_APPS_COLLECTION}' with ID: {inserted_id_str}")
        return inserted_id_str
    except pymongo_errors.PyMongoError as e:
        print(f"[DB_SAVE_ERROR] Failed to save analysis data to MongoDB collection '{ANALYZED_APPS_COLLECTION}': {e}")
        return None
    except Exception as e:
        print(f"[DB_SAVE_ERROR] An unexpected error occurred during save operation: {e}")
        return None

def get_analyses_by_app_id(db_handle, app_id: str, limit: int = 5, sort_descending: bool = True) -> list[dict]:
    """
    Retrieves analysis documents for a given app_id, sorted by timestamp.
    Args:
        db_handle: A MongoDB database handle.
        app_id: The app_id to search for.
        limit: The maximum number of documents to return. Defaults to 5.
        sort_descending: If True (default), sorts by 'analysis_timestamp_utc' 
                         in descending order (newest first). Otherwise, ascending.
    Returns:
        A list of analysis documents (dictionaries). Each document's '_id' is
        converted to a string. Returns an empty list if an error occurs or no
        documents are found.
    """
    if not db_handle:
        print("[DB_QUERY_ERROR] Database handle is invalid or None. Cannot query analyses.")
        return []
    
    try:
        collection = db_handle[ANALYZED_APPS_COLLECTION]
        sort_order = pymongo.DESCENDING if sort_descending else pymongo.ASCENDING
        
        cursor = collection.find(
            {"app_id": app_id}
        ).sort("analysis_timestamp_utc", sort_order).limit(limit)
        
        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        
        print(f"[DB_QUERY_INFO] Found {len(results)} analyses for app_id '{app_id}' in collection '{ANALYZED_APPS_COLLECTION}'.")
        return results
    except pymongo_errors.PyMongoError as e:
        print(f"[DB_QUERY_ERROR] Failed to retrieve analyses for app_id '{app_id}' from '{ANALYZED_APPS_COLLECTION}': {e}")
        return []
    except Exception as e:
        print(f"[DB_QUERY_ERROR] An unexpected error occurred while querying for app_id '{app_id}': {e}")
        return []

def get_distinct_analyzed_app_ids(db_handle) -> list[str]:
    """
    Retrieves a list of all unique 'app_id' values from the 'analyzed_apps' collection.
    Args:
        db_handle: A MongoDB database handle.
    Returns:
        A list of unique app_id strings. Returns an empty list if an error occurs.
    """
    if not db_handle:
        print("[DB_DISTINCT_ERROR] Database handle is invalid or None. Cannot get distinct app IDs.")
        return []
        
    try:
        collection = db_handle[ANALYZED_APPS_COLLECTION]
        distinct_ids = collection.distinct("app_id")
        print(f"[DB_DISTINCT_INFO] Found {len(distinct_ids)} distinct app_ids in collection '{ANALYZED_APPS_COLLECTION}'.")
        return distinct_ids
    except pymongo_errors.PyMongoError as e:
        print(f"[DB_DISTINCT_ERROR] Failed to retrieve distinct app_ids from '{ANALYZED_APPS_COLLECTION}': {e}")
        return []
    except Exception as e:
        print(f"[DB_DISTINCT_ERROR] An unexpected error occurred while retrieving distinct app_ids: {e}")
        return []

# --- New functions for Scheduler ---

def add_target_app(db_handle, app_id: str, app_name: str, platform: str = "google_play", is_active: bool = True, custom_tags: list = None) -> str | None:
    """
    Adds a new target app to the 'target_apps_config' collection for the scheduler.

    If an app with the same app_id already exists, it prints a message and returns 
    the existing document's _id. Otherwise, it inserts the new app configuration.

    Args:
        db_handle: A MongoDB database handle.
        app_id: The unique identifier for the app (e.g., 'com.example.app').
        app_name: The human-readable name of the app.
        platform: The platform of the app (e.g., "google_play", "app_store"). 
                  Defaults to "google_play".
        is_active: Boolean indicating if the app should be actively scraped. 
                   Defaults to True.
        custom_tags: A list of custom tags for categorization. Defaults to an empty list.

    Returns:
        The string representation of the document's _id (either new or existing) 
        if successful or app already existed, otherwise None if an error occurs during insertion.
    """
    if not db_handle:
        print(f"[DB_TARGET_ADD_ERROR] Database handle is invalid or None. Cannot add target app '{app_id}'.")
        return None

    collection = db_handle[TARGET_APPS_COLLECTION]

    try:
        # Check if app_id already exists
        existing_doc = collection.find_one({"app_id": app_id})
        if existing_doc:
            existing_id_str = str(existing_doc["_id"])
            print(f"[DB_TARGET_ADD_INFO] Target app '{app_id}' already exists with ID: {existing_id_str}. No new document inserted.")
            return existing_id_str # Return existing ID

        doc_to_insert = {
            "app_id": app_id,
            "app_name": app_name,
            "platform": platform,
            "is_active": is_active,
            "custom_tags": custom_tags if custom_tags is not None else [],
            "last_scraped_timestamp_utc": None  # Initialized to None
        }
        result = collection.insert_one(doc_to_insert)
        inserted_id_str = str(result.inserted_id)
        print(f"[DB_TARGET_ADD_SUCCESS] Target app '{app_id}' added with ID: {inserted_id_str} to collection '{TARGET_APPS_COLLECTION}'.")
        return inserted_id_str
    except pymongo_errors.PyMongoError as e:
        print(f"[DB_TARGET_ADD_ERROR] Failed to add target app '{app_id}' to MongoDB collection '{TARGET_APPS_COLLECTION}': {e}")
        return None
    except Exception as e:
        print(f"[DB_TARGET_ADD_ERROR] An unexpected error occurred while adding target app '{app_id}': {e}")
        return None

def get_active_target_apps(db_handle) -> list[dict]:
    """
    Retrieves all active target app configurations from the 'target_apps_config' collection.

    Args:
        db_handle: A MongoDB database handle.

    Returns:
        A list of dictionaries, where each dictionary is an active app configuration.
        The '_id' of each document is converted to a string.
        Returns an empty list if an error occurs or no active apps are found.
    """
    if not db_handle:
        print("[DB_TARGET_QUERY_ERROR] Database handle is invalid or None. Cannot get active target apps.")
        return []

    try:
        collection = db_handle[TARGET_APPS_COLLECTION]
        cursor = collection.find({"is_active": True})
        
        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        
        print(f"[DB_TARGET_QUERY_INFO] Found {len(results)} active target app(s) in collection '{TARGET_APPS_COLLECTION}'.")
        return results
    except pymongo_errors.PyMongoError as e:
        print(f"[DB_TARGET_QUERY_ERROR] Failed to retrieve active target apps from '{TARGET_APPS_COLLECTION}': {e}")
        return []
    except Exception as e:
        print(f"[DB_TARGET_QUERY_ERROR] An unexpected error occurred while retrieving active target apps: {e}")
        return []

def update_target_app_last_scraped(db_handle, app_id: str, timestamp_utc_iso: str) -> bool:
    """
    Updates the 'last_scraped_timestamp_utc' for a specific target app.

    Args:
        db_handle: A MongoDB database handle.
        app_id: The app_id of the target app to update.
        timestamp_utc_iso: An ISO format UTC timestamp string to set as the 
                           last scraped time.

    Returns:
        True if the app was found and update was attempted (i.e., matched_count > 0), 
        False otherwise or if an error occurs.
    """
    if not db_handle:
        print(f"[DB_TARGET_UPDATE_ERROR] Database handle is invalid or None. Cannot update target app '{app_id}'.")
        return False

    try:
        collection = db_handle[TARGET_APPS_COLLECTION]
        result = collection.update_one(
            {"app_id": app_id},
            {"$set": {"last_scraped_timestamp_utc": timestamp_utc_iso}}
        )
        
        if result.matched_count > 0:
            if result.modified_count > 0:
                print(f"[DB_TARGET_UPDATE_SUCCESS] Updated 'last_scraped_timestamp_utc' for target app '{app_id}' in '{TARGET_APPS_COLLECTION}'.")
            else:
                print(f"[DB_TARGET_UPDATE_INFO] Target app '{app_id}' found but 'last_scraped_timestamp_utc' was already set to the provided value.")
            return True
        else:
            print(f"[DB_TARGET_UPDATE_WARN] Target app '{app_id}' not found in '{TARGET_APPS_COLLECTION}'. No update performed.")
            return False
            
    except pymongo_errors.PyMongoError as e:
        print(f"[DB_TARGET_UPDATE_ERROR] Failed to update 'last_scraped_timestamp_utc' for target app '{app_id}' in '{TARGET_APPS_COLLECTION}': {e}")
        return False
    except Exception as e:
        print(f"[DB_TARGET_UPDATE_ERROR] An unexpected error occurred while updating target app '{app_id}': {e}")
        return False

# No if __name__ == "__main__": block, as this is intended to be a module.
```
