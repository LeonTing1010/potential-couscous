import time
import pandas as pd # For type hinting and DataFrame operations
from pytrends.request import TrendReq
from pytrends.exceptions import ResponseError # For specific pytrends error handling

# Module-level comment about Google Trends API rate limits
# Google Trends API (via pytrends) can be sensitive to rate limits.
# If making many requests, consider adding delays between calls or implementing
# more sophisticated retry logic with exponential backoff if not handled by pytrends' retries.

def init_pytrends(hl: str = 'en-US', tz: int = 360, retries: int = 3, backoff_factor: float = 0.5) -> TrendReq | None:
    """
    Initializes and returns a TrendReq (pytrends) object.

    Args:
        hl: Language for results (e.g., 'en-US', 'fr'). Defaults to 'en-US'.
        tz: Timezone offset in minutes (e.g., 360 for US CST). Defaults to 360.
        retries: Number of retries for failed requests. Defaults to 3.
        backoff_factor: Factor to determine delay between retries (e.g., 0.5 means 
                        sleep for {backoff factor} * (2 ** ({number of total retries} - 1)) seconds).
                        Defaults to 0.5.

    Returns:
        A TrendReq object if initialization is successful, otherwise None.
    """
    try:
        print(f"[G_TRENDS_INIT_INFO] Initializing Pytrends with hl='{hl}', tz={tz}, retries={retries}, backoff={backoff_factor}")
        pytrends_obj = TrendReq(hl=hl, tz=tz, retries=retries, backoff_factor=backoff_factor)
        print("[G_TRENDS_INIT_SUCCESS] Pytrends TrendReq object initialized successfully.")
        return pytrends_obj
    except Exception as e:
        print(f"[G_TRENDS_INIT_ERROR] Failed to initialize Pytrends TrendReq object: {e}")
        return None

def get_interest_over_time(
    pytrends_obj: TrendReq, 
    keyword_list: list[str], 
    timeframe: str = 'today 3-m', 
    geo: str = '', 
    gprop: str = ''
) -> dict | None:
    """
    Fetches Google Trends interest over time for a list of keywords.

    Args:
        pytrends_obj: An initialized TrendReq object.
        keyword_list: A list of keywords (max 5 by Google Trends).
        timeframe: Timeframe for the data (e.g., 'today 3-m', 'now 7-d', '2020-01-01 2020-12-31').
                   Defaults to 'today 3-m' (last 3 months).
        geo: Geographical region for the trend data (e.g., 'US', 'GB', 'US-CA' for California).
             Defaults to worldwide.
        gprop: Google property to filter results (e.g., 'images', 'news', 'youtube', 'froogle').
               Defaults to web search.

    Returns:
        A dictionary containing interest over time data and 'isPartial' status, 
        or None if an error occurs or no data is found.
        Format: {"date_points": {"YYYY-MM-DD": {"kw1": value1, ...}}, "isPartial": True/False}
    """
    if not isinstance(pytrends_obj, TrendReq):
        print("[G_TRENDS_IOT_ERROR] Invalid Pytrends object provided.")
        return None
    if not keyword_list or not isinstance(keyword_list, list) or len(keyword_list) == 0 or len(keyword_list) > 5:
        print("[G_TRENDS_IOT_ERROR] Keyword list must be a list containing 1 to 5 keywords.")
        return None

    print(f"[G_TRENDS_IOT_INFO] Fetching interest over time for keywords: {keyword_list}, timeframe: '{timeframe}', geo: '{geo}', gprop: '{gprop}'")
    try:
        pytrends_obj.build_payload(kw_list=keyword_list, cat=0, timeframe=timeframe, geo=geo, gprop=gprop)
        data_df = pytrends_obj.interest_over_time()

        if data_df.empty:
            print("[G_TRENDS_IOT_INFO] No interest over time data found for the given parameters.")
            return {"date_points": {}, "isPartial": False} # Return empty structure for no data

        # Convert DataFrame to the specified dictionary format
        result_dict = {"date_points": {}}
        is_partial_value = False # Default if 'isPartial' column is not present

        if 'isPartial' in data_df.columns:
            # Check the last value of 'isPartial' or if any value is True
            # For simplicity, taking the last value. Google Trends usually marks the last point.
            is_partial_value = bool(data_df['isPartial'].iloc[-1]) if not data_df['isPartial'].empty else False
            # Drop the 'isPartial' column before converting to dict to avoid it being treated as a keyword
            data_df = data_df.drop(columns=['isPartial'])
        
        result_dict["isPartial"] = is_partial_value
        
        for date_index, row in data_df.iterrows():
            # Convert Timestamp index to 'YYYY-MM-DD' string
            date_str = date_index.strftime('%Y-%m-%d')
            result_dict["date_points"][date_str] = row.to_dict()
            
        print(f"[G_TRENDS_IOT_SUCCESS] Successfully fetched and processed interest over time data for {len(data_df)} date points.")
        return result_dict

    except ResponseError as re:
        print(f"[G_TRENDS_IOT_ERROR] Pytrends API ResponseError: {re}")
        if "Too Many Requests" in str(re) or "429" in str(re):
            print("[G_TRENDS_IOT_ERROR] Rate limit likely exceeded. Consider adding delays or reducing request frequency.")
        return None
    except Exception as e:
        print(f"[G_TRENDS_IOT_ERROR] An unexpected error occurred: {e}")
        return None

def get_related_topics(
    pytrends_obj: TrendReq, 
    keyword: str, 
    timeframe: str = 'today 1-m', 
    geo: str = '', 
    gprop: str = ''
) -> dict | None:
    """
    Fetches related topics for a single keyword from Google Trends.

    Args:
        pytrends_obj: An initialized TrendReq object.
        keyword: The keyword to find related topics for.
        timeframe: Timeframe for the data. Defaults to 'today 1-m'.
        geo: Geographical region. Defaults to worldwide.
        gprop: Google property. Defaults to web search.

    Returns:
        A dictionary with 'rising' and 'top' related topics, each being a list of dicts,
        or None if an error occurs or no related topics are found.
        Format: {"rising": [list_of_rising_topic_dicts], "top": [list_of_top_topic_dicts]}
    """
    if not isinstance(pytrends_obj, TrendReq):
        print("[G_TRENDS_RELATED_TOPICS_ERROR] Invalid Pytrends object provided.")
        return None
    if not keyword or not isinstance(keyword, str):
        print("[G_TRENDS_RELATED_TOPICS_ERROR] A valid single keyword string must be provided.")
        return None

    print(f"[G_TRENDS_RELATED_TOPICS_INFO] Fetching related topics for keyword: '{keyword}', timeframe: '{timeframe}', geo: '{geo}', gprop: '{gprop}'")
    try:
        # Build payload for a single keyword
        pytrends_obj.build_payload(kw_list=[keyword], cat=0, timeframe=timeframe, geo=geo, gprop=gprop)
        related_topics_data = pytrends_obj.related_topics()

        if not related_topics_data or keyword not in related_topics_data or not related_topics_data[keyword]:
            print(f"[G_TRENDS_RELATED_TOPICS_INFO] No related topics data found for keyword '{keyword}'.")
            return {"rising": [], "top": []} # Return empty structure

        processed_data = {"rising": [], "top": []}
        
        # Process 'rising' topics DataFrame
        if 'rising' in related_topics_data[keyword] and isinstance(related_topics_data[keyword]['rising'], pd.DataFrame):
            rising_df = related_topics_data[keyword]['rising']
            if not rising_df.empty:
                processed_data["rising"] = rising_df.to_dict('records')
        
        # Process 'top' topics DataFrame
        if 'top' in related_topics_data[keyword] and isinstance(related_topics_data[keyword]['top'], pd.DataFrame):
            top_df = related_topics_data[keyword]['top']
            if not top_df.empty:
                processed_data["top"] = top_df.to_dict('records')
        
        print(f"[G_TRENDS_RELATED_TOPICS_SUCCESS] Successfully fetched related topics for '{keyword}'. "
              f"Rising: {len(processed_data['rising'])}, Top: {len(processed_data['top'])}.")
        return processed_data

    except ResponseError as re:
        print(f"[G_TRENDS_RELATED_TOPICS_ERROR] Pytrends API ResponseError for '{keyword}': {re}")
        return None
    except Exception as e:
        print(f"[G_TRENDS_RELATED_TOPICS_ERROR] An unexpected error occurred for '{keyword}': {e}")
        return None

def get_related_queries(
    pytrends_obj: TrendReq, 
    keyword: str, 
    timeframe: str = 'today 1-m', 
    geo: str = '', 
    gprop: str = ''
) -> dict | None:
    """
    Fetches related queries for a single keyword from Google Trends.

    Args:
        pytrends_obj: An initialized TrendReq object.
        keyword: The keyword to find related queries for.
        timeframe: Timeframe for the data. Defaults to 'today 1-m'.
        geo: Geographical region. Defaults to worldwide.
        gprop: Google property. Defaults to web search.

    Returns:
        A dictionary with 'rising' and 'top' related queries, each being a list of dicts,
        or None if an error occurs or no related queries are found.
        Format: {"rising": [list_of_rising_query_dicts], "top": [list_of_top_query_dicts]}
    """
    if not isinstance(pytrends_obj, TrendReq):
        print("[G_TRENDS_RELATED_QUERIES_ERROR] Invalid Pytrends object provided.")
        return None
    if not keyword or not isinstance(keyword, str):
        print("[G_TRENDS_RELATED_QUERIES_ERROR] A valid single keyword string must be provided.")
        return None

    print(f"[G_TRENDS_RELATED_QUERIES_INFO] Fetching related queries for keyword: '{keyword}', timeframe: '{timeframe}', geo: '{geo}', gprop: '{gprop}'")
    try:
        pytrends_obj.build_payload(kw_list=[keyword], cat=0, timeframe=timeframe, geo=geo, gprop=gprop)
        related_queries_data = pytrends_obj.related_queries()

        if not related_queries_data or keyword not in related_queries_data or not related_queries_data[keyword]:
            print(f"[G_TRENDS_RELATED_QUERIES_INFO] No related queries data found for keyword '{keyword}'.")
            return {"rising": [], "top": []} # Return empty structure

        processed_data = {"rising": [], "top": []}

        if 'rising' in related_queries_data[keyword] and isinstance(related_queries_data[keyword]['rising'], pd.DataFrame):
            rising_df = related_queries_data[keyword]['rising']
            if not rising_df.empty:
                processed_data["rising"] = rising_df.to_dict('records')
        
        if 'top' in related_queries_data[keyword] and isinstance(related_queries_data[keyword]['top'], pd.DataFrame):
            top_df = related_queries_data[keyword]['top']
            if not top_df.empty:
                processed_data["top"] = top_df.to_dict('records')
        
        print(f"[G_TRENDS_RELATED_QUERIES_SUCCESS] Successfully fetched related queries for '{keyword}'. "
              f"Rising: {len(processed_data['rising'])}, Top: {len(processed_data['top'])}.")
        return processed_data

    except ResponseError as re:
        print(f"[G_TRENDS_RELATED_QUERIES_ERROR] Pytrends API ResponseError for '{keyword}': {re}")
        return None
    except Exception as e:
        print(f"[G_TRENDS_RELATED_QUERIES_ERROR] An unexpected error occurred for '{keyword}': {e}")
        return None

def get_keyword_suggestions(pytrends_obj: TrendReq, keyword: str) -> list[dict] | None:
    """
    Fetches keyword suggestions from Google Trends for a given keyword.

    Args:
        pytrends_obj: An initialized TrendReq object.
        keyword: The keyword to get suggestions for.

    Returns:
        A list of dictionaries, where each dictionary contains a suggestion 
        (e.g., {'mid': '/m/0c1dj', 'title': 'Artificial intelligence', 'type': 'Topic'}),
        or None if an error occurs or no suggestions are found.
    """
    if not isinstance(pytrends_obj, TrendReq):
        print("[G_TRENDS_SUGGESTIONS_ERROR] Invalid Pytrends object provided.")
        return None
    if not keyword or not isinstance(keyword, str):
        print("[G_TRENDS_SUGGESTIONS_ERROR] A valid keyword string must be provided.")
        return None

    print(f"[G_TRENDS_SUGGESTIONS_INFO] Fetching keyword suggestions for: '{keyword}'")
    try:
        suggestions_data = pytrends_obj.suggestions(keyword)
        
        if not suggestions_data:
            print(f"[G_TRENDS_SUGGESTIONS_INFO] No suggestions found for keyword '{keyword}'.")
            return [] # Return empty list for no suggestions
            
        print(f"[G_TRENDS_SUGGESTIONS_SUCCESS] Successfully fetched {len(suggestions_data)} suggestions for '{keyword}'.")
        return suggestions_data

    except ResponseError as re: # Though suggestions() is less likely to hit typical API limits like other methods
        print(f"[G_TRENDS_SUGGESTIONS_ERROR] Pytrends API ResponseError for '{keyword}': {re}")
        return None
    except Exception as e:
        print(f"[G_TRENDS_SUGGESTIONS_ERROR] An unexpected error occurred for '{keyword}': {e}")
        return None

# No main execution block (`if __name__ == "__main__":`) as this is intended to be an importable module.
```
