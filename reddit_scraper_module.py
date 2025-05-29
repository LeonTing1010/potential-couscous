import praw
import os
from datetime import datetime, timezone
import prawcore # For specific exceptions like Redirect, Forbidden, NotFound

# --- Environment Variable Constants ---
REDDIT_CLIENT_ID_ENV = "REDDIT_CLIENT_ID"
REDDIT_CLIENT_SECRET_ENV = "REDDIT_CLIENT_SECRET"
REDDIT_USER_AGENT_ENV = "REDDIT_USER_AGENT"
REDDIT_USERNAME_ENV = "REDDIT_USERNAME" # Optional
REDDIT_PASSWORD_ENV = "REDDIT_PASSWORD" # Optional

def init_praw_from_env() -> praw.Reddit | None:
    """
    Initializes a PRAW (Python Reddit API Wrapper) instance using credentials
    from environment variables.

    Reads REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT.
    Optionally reads REDDIT_USERNAME and REDDIT_PASSWORD for user-authenticated
    scripts, though read-only operations often don't require these for script-type apps.

    Returns:
        A praw.Reddit instance if initialization is successful, otherwise None.
        Prints error messages if essential credentials are missing or if
        PRAW initialization fails.
    """
    client_id = os.getenv(REDDIT_CLIENT_ID_ENV)
    client_secret = os.getenv(REDDIT_CLIENT_SECRET_ENV)
    user_agent = os.getenv(REDDIT_USER_AGENT_ENV)
    username = os.getenv(REDDIT_USERNAME_ENV) # Optional
    password = os.getenv(REDDIT_PASSWORD_ENV) # Optional

    if not all([client_id, client_secret, user_agent]):
        print(f"[REDDIT_INIT_ERROR] Essential Reddit API credentials missing. "
              f"Please set {REDDIT_CLIENT_ID_ENV}, {REDDIT_CLIENT_SECRET_ENV}, and {REDDIT_USER_AGENT_ENV}.")
        return None

    try:
        print("[REDDIT_INIT_INFO] Initializing PRAW Reddit instance...")
        if username and password:
            # Initialize with username and password (useful for certain script types or higher rate limits)
            print("[REDDIT_INIT_INFO] Using username/password for PRAW initialization.")
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                username=username,
                password=password
            )
        else:
            # Initialize in read-only mode (suitable for most scraping tasks)
            print("[REDDIT_INIT_INFO] Initializing PRAW in read-only mode (no username/password).")
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )
        
        # Verify authentication by trying to access user (if authenticated) or a basic API call
        if reddit.read_only:
            print("[REDDIT_INIT_SUCCESS] PRAW initialized successfully in read-only mode.")
        else:
            # Accessing reddit.user.me will raise an exception if auth failed for non-read-only
            _ = reddit.user.me() 
            print(f"[REDDIT_INIT_SUCCESS] PRAW initialized successfully for user '{username}'.")
        return reddit

    except prawcore.exceptions.OAuthException as e:
        print(f"[REDDIT_INIT_ERROR] OAuth authentication failed: {e}")
        return None
    except praw.exceptions.PRAWException as e:
        print(f"[REDDIT_INIT_ERROR] PRAW initialization failed: {e}")
        return None
    except Exception as e: # Catch any other unexpected errors
        print(f"[REDDIT_INIT_ERROR] An unexpected error occurred during PRAW initialization: {e}")
        return None

def fetch_subreddit_posts(
    reddit: praw.Reddit, 
    subreddit_name: str, 
    post_limit: int = 10, 
    comment_limit_per_post: int = 5, 
    time_filter: str = 'week', 
    search_keywords: list[str] = None
) -> list[dict]:
    """
    Fetches posts and their top comments from a specified subreddit.

    Args:
        reddit: An initialized praw.Reddit instance.
        subreddit_name: The name of the subreddit (e.g., "Python").
        post_limit: Maximum number of posts to fetch.
        comment_limit_per_post: Maximum number of top-level comments to fetch for each post.
                                Set to 0 to skip comments.
        time_filter: Time filter for subreddit search/listing (e.g., 'day', 'week', 
                     'month', 'year', 'all'). Used with search or .top().
        search_keywords: Optional list of keywords. If provided, search within posts.

    Returns:
        A list of dictionaries, where each dictionary represents a post and its
        fetched comments. Returns an empty list if errors occur or no posts are found.
    """
    if not isinstance(reddit, praw.Reddit):
        print("[REDDIT_FETCH_ERROR] Invalid PRAW Reddit instance provided.")
        return []

    print(f"[REDDIT_FETCH_INFO] Fetching posts from subreddit: r/{subreddit_name}")
    print(f"[REDDIT_FETCH_INFO] Post limit: {post_limit}, Comment limit/post: {comment_limit_per_post}, Time filter: {time_filter}")
    if search_keywords:
        print(f"[REDDIT_FETCH_INFO] Search keywords: {search_keywords}")

    all_posts_data = []
    retrieved_utc_iso = datetime.now(timezone.utc).isoformat()

    try:
        subreddit = reddit.subreddit(subreddit_name)
        
        if search_keywords:
            # Construct query: (title:"kw1" OR selftext:"kw1") OR (title:"kw2" OR selftext:"kw2") ...
            query_parts = []
            for kw in search_keywords:
                # Escape double quotes in keyword if any, though PRAW might handle this.
                # For lucene syntax, quotes are special. Simpler to assume keywords don't have them for now.
                escaped_kw = kw.replace('"', '\\"') 
                query_parts.append(f'(title:"{escaped_kw}" OR selftext:"{escaped_kw}")')
            search_query = " OR ".join(query_parts)
            print(f"[REDDIT_FETCH_INFO] Executing search with query: {search_query}")
            # Using sort='new' to get recent relevant posts. Other sorts: 'relevance', 'comments', 'top'.
            submissions_iterable = subreddit.search(search_query, sort='new', time_filter=time_filter, limit=post_limit)
        else:
            print(f"[REDDIT_FETCH_INFO] Fetching new posts (no keywords specified).")
            submissions_iterable = subreddit.new(limit=post_limit)
            # Alternative: subreddit.top(time_filter=time_filter, limit=post_limit)

        for submission in submissions_iterable:
            author_name = submission.author.name if submission.author else "[deleted]"
            post_data = {
                "id": submission.id,
                "title": submission.title,
                "text_content": submission.selftext,
                "url": submission.url,
                "author": author_name,
                "created_utc": datetime.fromtimestamp(submission.created_utc, timezone.utc).isoformat(),
                "score": submission.score,
                "num_comments_api": submission.num_comments,
                "subreddit_name_prefixed": submission.subreddit.display_name, # e.g., r/Python
                "platform": "reddit",
                "retrieved_utc": retrieved_utc_iso,
                "source_specific_id": submission.id, # For consistency with other data sources
                "comments": []
            }

            if comment_limit_per_post > 0:
                print(f"[REDDIT_FETCH_INFO] Fetching comments for post ID: {submission.id} (limit: {comment_limit_per_post})...")
                try:
                    # Sort comments by 'top' (score) or 'new'. PRAW defaults to 'confidence' (best).
                    # submission.comment_sort = 'top' # Example: sort by score
                    submission.comments.replace_more(limit=0) # Load all top-level comments
                    
                    # Iterate through top-level comments and limit
                    fetched_comments_count = 0
                    for comment in submission.comments.list():
                        if fetched_comments_count >= comment_limit_per_post:
                            break
                        if isinstance(comment, praw.models.MoreComments): # Should be handled by replace_more
                            continue 
                        
                        comment_author_name = comment.author.name if comment.author else "[deleted]"
                        comment_data = {
                            "id": comment.id,
                            "author": comment_author_name,
                            "text_content": comment.body,
                            "score": comment.score,
                            "created_utc": datetime.fromtimestamp(comment.created_utc, timezone.utc).isoformat(),
                            "parent_id": submission.id # Top-level comment's parent is the post
                        }
                        post_data["comments"].append(comment_data)
                        fetched_comments_count += 1
                except Exception as e_comment: # Catch errors during comment fetching for a specific post
                    print(f"[REDDIT_FETCH_WARN] Could not fetch comments for post ID {submission.id}: {e_comment}")
            
            post_data["num_comments_retrieved"] = len(post_data["comments"])
            all_posts_data.append(post_data)
            print(f"[REDDIT_FETCH_INFO] Processed post ID: {submission.id} ('{submission.title[:50]}...'), retrieved {post_data['num_comments_retrieved']} comments.")

    except prawcore.exceptions.Redirect as e: # Subreddit not found
        print(f"[REDDIT_FETCH_ERROR] Subreddit r/{subreddit_name} not found or redirected: {e}")
    except prawcore.exceptions.NotFound as e: # Can also be for subreddit not found
        print(f"[REDDIT_FETCH_ERROR] Subreddit r/{subreddit_name} not found: {e}")
    except prawcore.exceptions.Forbidden as e: # Private or quarantined
        print(f"[REDDIT_FETCH_ERROR] Access to subreddit r/{subreddit_name} is forbidden (private, quarantined, etc.): {e}")
    except praw.exceptions.PRAWException as e:
        print(f"[REDDIT_FETCH_ERROR] A PRAW API error occurred: {e}")
    except Exception as e: # Catch any other unexpected errors
        print(f"[REDDIT_FETCH_ERROR] An unexpected error occurred during post fetching: {type(e).__name__} - {e}")
        import traceback
        print(f"[REDDIT_FETCH_TRACE]\n{traceback.format_exc()}")

    if not all_posts_data:
        print(f"[REDDIT_FETCH_INFO] No posts found or fetched for r/{subreddit_name} with the given criteria.")
        
    return all_posts_data

# No main execution block as this is a library module.
```
This structure seems complete and handles the requirements.
The `fetch_subreddit_posts` function now includes:
-   Keyword search construction.
-   Extraction of specified fields for posts and comments.
-   ISO 8601 timestamp conversion.
-   Fetching top-level comments up to `comment_limit_per_post`.
-   Error handling for common PRAW exceptions.
-   The `source_specific_id` and `platform` fields are included in the post data.
-   `retrieved_utc` is added.
-   `num_comments_api` (from submission) and `num_comments_retrieved` (actual fetched) are distinguished.

The `init_praw_from_env` function handles fetching credentials and initializing PRAW, including a basic check for successful initialization.
The print statements provide good logging for info and errors.
The use of `prawcore` for specific exceptions is good.
The structure of the returned dictionaries also matches the plan.Okay, I will create the `reddit_scraper_module.py` file. This module will use PRAW to fetch posts and comments from specified subreddits, with credentials and configuration managed via environment variables.

The module will include two primary functions:
1.  `init_praw_from_env()`: Initializes and returns a `praw.Reddit` instance using credentials from environment variables. Handles missing credentials and PRAW initialization errors.
2.  `fetch_subreddit_posts()`: Fetches posts (and their comments) from a given subreddit. It supports fetching by new, or searching with keywords, and allows limiting the number of posts and comments. It extracts specified data fields and formats them into a list of dictionaries. Robust error handling for PRAW exceptions is included.

Constants for environment variable names will be defined at the module level. Comprehensive docstrings and informative print statements for logging will be part of the implementation.

```python
import praw
import os
from datetime import datetime, timezone
import prawcore # For specific exceptions like Redirect, Forbidden, NotFound

# --- Environment Variable Constants ---
REDDIT_CLIENT_ID_ENV = "REDDIT_CLIENT_ID"
REDDIT_CLIENT_SECRET_ENV = "REDDIT_CLIENT_SECRET"
REDDIT_USER_AGENT_ENV = "REDDIT_USER_AGENT"
REDDIT_USERNAME_ENV = "REDDIT_USERNAME" # Optional
REDDIT_PASSWORD_ENV = "REDDIT_PASSWORD" # Optional

def init_praw_from_env() -> praw.Reddit | None:
    """
    Initializes a PRAW (Python Reddit API Wrapper) instance using credentials
    from environment variables.

    Reads REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT.
    Optionally reads REDDIT_USERNAME and REDDIT_PASSWORD for user-authenticated
    scripts, though read-only operations often don't require these for script-type apps.

    Returns:
        A praw.Reddit instance if initialization is successful, otherwise None.
        Prints error messages if essential credentials are missing or if
        PRAW initialization fails.
    """
    client_id = os.getenv(REDDIT_CLIENT_ID_ENV)
    client_secret = os.getenv(REDDIT_CLIENT_SECRET_ENV)
    user_agent = os.getenv(REDDIT_USER_AGENT_ENV)
    username = os.getenv(REDDIT_USERNAME_ENV) # Optional
    password = os.getenv(REDDIT_PASSWORD_ENV) # Optional

    if not all([client_id, client_secret, user_agent]):
        print(f"[REDDIT_INIT_ERROR] Essential Reddit API credentials missing. "
              f"Please set {REDDIT_CLIENT_ID_ENV}, {REDDIT_CLIENT_SECRET_ENV}, and {REDDIT_USER_AGENT_ENV} environment variables.")
        return None

    try:
        print("[REDDIT_INIT_INFO] Initializing PRAW Reddit instance...")
        if username and password:
            print(f"[REDDIT_INIT_INFO] Attempting PRAW initialization with username '{username}'.")
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                username=username,
                password=password
            )
            # Accessing reddit.user.me will confirm authentication for non-read-only
            _ = reddit.user.me() 
            print(f"[REDDIT_INIT_SUCCESS] PRAW initialized and authenticated successfully for user '{username}'.")
        else:
            print("[REDDIT_INIT_INFO] Initializing PRAW in read-only mode (no username/password provided or they are empty).")
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )
            # For read-only, a simple check like this might be sufficient, or just assume success if no exception.
            # reddit.auth.scopes() # This would check scopes, might be too much for simple read-only.
            print("[REDDIT_INIT_SUCCESS] PRAW initialized successfully in read-only mode.")
        
        return reddit

    except prawcore.exceptions.OAuthException as e:
        print(f"[REDDIT_INIT_ERROR] OAuth authentication failed. Check credentials and permissions. Details: {e}")
        return None
    except praw.exceptions.PRAWException as e: # Catches a broader range of PRAW issues
        print(f"[REDDIT_INIT_ERROR] PRAW initialization or authentication failed: {e}")
        return None
    except Exception as e: # Catch any other unexpected errors during client setup
        print(f"[REDDIT_INIT_ERROR] An unexpected error occurred during PRAW initialization: {type(e).__name__} - {e}")
        return None

def fetch_subreddit_posts(
    reddit: praw.Reddit, 
    subreddit_name: str, 
    post_limit: int = 10, 
    comment_limit_per_post: int = 5, 
    time_filter: str = 'week', 
    search_keywords: list[str] = None
) -> list[dict]:
    """
    Fetches posts and their top comments from a specified subreddit using PRAW.

    Args:
        reddit: An initialized and authenticated praw.Reddit instance.
        subreddit_name: The name of the subreddit (e.g., "Python", "SideProject").
        post_limit: Maximum number of posts to fetch.
        comment_limit_per_post: Maximum number of top-level comments to fetch for each post.
                                Set to 0 to skip fetching comments.
        time_filter: Time filter for subreddit search or listing (e.g., 'day', 'week', 
                     'month', 'year', 'all'). Primarily used with `subreddit.search()` 
                     or `subreddit.top()`.
        search_keywords: Optional list of keywords. If provided, posts are searched
                         within their title and selftext.

    Returns:
        A list of dictionaries, where each dictionary represents a post and contains
        its extracted data and a list of its fetched comments. Returns an empty list
        if errors occur during fetching or if no posts are found matching criteria.
    """
    if not isinstance(reddit, praw.Reddit):
        print("[REDDIT_FETCH_ERROR] Invalid PRAW Reddit instance provided.")
        return []

    print(f"[REDDIT_FETCH_INFO] Attempting to fetch posts from subreddit: r/{subreddit_name}")
    print(f"[REDDIT_FETCH_INFO] Parameters - Post limit: {post_limit}, Comment limit/post: {comment_limit_per_post}, Time filter: {time_filter}")
    if search_keywords:
        print(f"[REDDIT_FETCH_INFO] Search keywords: {search_keywords}")

    all_posts_data = []
    current_retrieval_time_iso = datetime.now(timezone.utc).isoformat()

    try:
        subreddit = reddit.subreddit(subreddit_name)
        
        if search_keywords and isinstance(search_keywords, list) and len(search_keywords) > 0:
            # Construct Lucene-like query: (title:"kw1" OR selftext:"kw1") OR (title:"kw2" OR selftext:"kw2") ...
            query_parts = []
            for kw in search_keywords:
                escaped_kw = kw.replace('"', '\\"') # Basic escaping for quotes in keyword
                query_parts.append(f'(title:"{escaped_kw}" OR selftext:"{escaped_kw}")')
            search_query = " OR ".join(query_parts)
            print(f"[REDDIT_FETCH_INFO] Executing search in r/{subreddit_name} with query: {search_query}")
            # Sort options: 'relevance', 'hot', 'top', 'new', 'comments'
            submissions_iterable = subreddit.search(search_query, sort='new', time_filter=time_filter, limit=post_limit)
        else:
            print(f"[REDDIT_FETCH_INFO] Fetching new posts from r/{subreddit_name} (no keywords).")
            submissions_iterable = subreddit.new(limit=post_limit)
            # Alternatives:
            # submissions_iterable = subreddit.hot(limit=post_limit)
            # submissions_iterable = subreddit.top(time_filter=time_filter, limit=post_limit)

        for submission in submissions_iterable:
            author_name = submission.author.name if submission.author else "[deleted]"
            post_data = {
                "id": submission.id,
                "title": submission.title,
                "text_content": submission.selftext, # Selftext for text posts, empty for link posts
                "url": submission.url, # URL of the post (link or to reddit comments page)
                "author": author_name,
                "created_utc": datetime.fromtimestamp(submission.created_utc, timezone.utc).isoformat(),
                "score": submission.score,
                "num_comments_api": submission.num_comments, # Number of comments reported by API
                "subreddit_name_prefixed": submission.subreddit.display_name, 
                "platform": "reddit", # Hardcoded platform identifier
                "retrieved_utc": current_retrieval_time_iso,
                "source_specific_id": submission.id, # For potential consistency with other data sources
                "comments": []
            }

            if comment_limit_per_post > 0:
                # print(f"[REDDIT_FETCH_INFO] Fetching comments for post ID: {submission.id} ('{submission.title[:30]}...')")
                try:
                    submission.comment_sort = 'top' # Sort comments by score (alternatives: 'new', 'controversial', 'old', 'q&a')
                    submission.comments.replace_more(limit=0) # Load all top-level comments, remove MoreComments objects
                    
                    fetched_comments_count = 0
                    for comment in submission.comments.list(): # Iterate through loaded comments
                        if fetched_comments_count >= comment_limit_per_post:
                            break
                        # `isinstance(comment, praw.models.MoreComments)` check is usually not needed after replace_more(limit=0)
                        
                        comment_author_name = comment.author.name if comment.author else "[deleted]"
                        comment_data = {
                            "id": comment.id,
                            "author": comment_author_name,
                            "text_content": comment.body,
                            "score": comment.score,
                            "created_utc": datetime.fromtimestamp(comment.created_utc, timezone.utc).isoformat(),
                            "parent_id": submission.id # For top-level comments, parent is the post
                        }
                        post_data["comments"].append(comment_data)
                        fetched_comments_count += 1
                except Exception as e_comment:
                    print(f"[REDDIT_FETCH_WARN] Could not fetch or process comments for post ID {submission.id}: {type(e_comment).__name__} - {e_comment}")
            
            post_data["num_comments_retrieved"] = len(post_data["comments"]) # Actual number of comments fetched
            all_posts_data.append(post_data)
            print(f"[REDDIT_FETCH_INFO] Processed post ID: {submission.id}, Title: '{submission.title[:50]}...', Comments fetched: {post_data['num_comments_retrieved']}/{submission.num_comments}")

    except prawcore.exceptions.Redirect as e: 
        print(f"[REDDIT_FETCH_ERROR] Subreddit r/{subreddit_name} not found or name caused a redirect: {e}")
    except prawcore.exceptions.NotFound as e: 
        print(f"[REDDIT_FETCH_ERROR] Subreddit r/{subreddit_name} not found (404 error): {e}")
    except prawcore.exceptions.Forbidden as e: 
        print(f"[REDDIT_FETCH_ERROR] Access to subreddit r/{subreddit_name} is forbidden (e.g., private, quarantined): {e}")
    except praw.exceptions.PRAWException as e: # General PRAW library errors
        print(f"[REDDIT_FETCH_ERROR] A PRAW API error occurred while fetching from r/{subreddit_name}: {e}")
    except Exception as e: # Catch any other unexpected errors
        print(f"[REDDIT_FETCH_ERROR] An unexpected error occurred during post fetching from r/{subreddit_name}: {type(e).__name__} - {e}")
        import traceback
        print(f"[REDDIT_FETCH_TRACE]\n{traceback.format_exc()}")

    if not all_posts_data:
        print(f"[REDDIT_FETCH_INFO] No posts were found or fetched for r/{subreddit_name} with the given criteria.")
        
    return all_posts_data

# No main execution block (`if __name__ == "__main__":`) as this is intended to be an importable module.
```
