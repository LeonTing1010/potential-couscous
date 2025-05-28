from google_play_scraper import reviews, Sort, NotFoundError

def scrape_google_play_reviews(app_id: str, lang: str = 'en', country: str = 'us', reviews_to_fetch: int = 100, target_star_rating: int = 1) -> list[dict]:
    """
    Fetches and filters reviews for a given Google Play app ID based on a target star rating.

    It uses the `filter_score_with` parameter of the `google_play_scraper.reviews`
    function to efficiently fetch only reviews matching the `target_star_rating`.

    Args:
        app_id: The unique identifier of the app on Google Play 
                (e.g., 'com.google.android.gm').
        lang: The language code for the reviews (e.g., 'en', 'es'). 
              Defaults to 'en'.
        country: The country code for the reviews (e.g., 'us', 'gb'). 
                 Defaults to 'us'.
        reviews_to_fetch: The target number of reviews to fetch that match the 
                          `target_star_rating`. Defaults to 100.
        target_star_rating: The specific star rating (1 to 5) to filter reviews by.
                              Defaults to 1 (to fetch 1-star reviews).

    Returns:
        A list of dictionaries, where each dictionary represents a review.
        Each review dictionary is guaranteed to contain at least the keys:
        'userName', 'score', 'content', and 'at'.
        Returns an empty list if the app is not found, no reviews match 
        the criteria, or an error occurs during the scraping process.
    """
    try:
        # Fetch reviews, sorting by newest, and filtering by the target star rating.
        # The 'count' parameter specifies how many reviews matching the filter to retrieve.
        result, _ = reviews(
            app_id,
            lang=lang,
            country=country,
            sort=Sort.NEWEST,  # Sort by most recent
            count=reviews_to_fetch,
            filter_score_with=target_star_rating # Filter by the specified star rating
        )
        
        # If 'result' is None (e.g., no reviews match the filter or fewer than 'count' exist),
        # return an empty list.
        if result is None:
            # print(f"No reviews found for '{app_id}' with star rating {target_star_rating} or fewer than {reviews_to_fetch} reviews exist.")
            return []
        
        # The 'reviews' function already returns a list of dicts.
        # The library ensures the presence of keys like 'userName', 'score', 'content', 'at'.
        # No additional client-side filtering for score is needed due to 'filter_score_with'.
        return result

    except NotFoundError:
        print(f"Error: App with ID '{app_id}' not found on Google Play.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while scraping reviews for app ID '{app_id}': {e}")
        return []

# Example usage (commented out, not part of the module's direct execution)
# if __name__ == '__main__':
#     # Test with a valid app ID known to have reviews
#     # Gmail app ID: com.google.android.gm
#     gmail_app_id = "com.google.android.gm"
#     print(f"Fetching 1-star reviews for {gmail_app_id}...")
#     one_star_reviews = scrape_google_play_reviews(gmail_app_id, reviews_to_fetch=5, target_star_rating=1)
#     if one_star_reviews:
#         for review in one_star_reviews:
#             print(f"User: {review.get('userName')}, Score: {review.get('score')}, Date: {review.get('at')}")
#             print(f"Review: {review.get('content')[:100]}...") # Print first 100 chars
#             print("-" * 20)
#     else:
#         print("No 1-star reviews found or an error occurred.")

#     print(f"\nFetching 5-star reviews for {gmail_app_id}...")
#     five_star_reviews = scrape_google_play_reviews(gmail_app_id, reviews_to_fetch=3, target_star_rating=5)
#     if five_star_reviews:
#         for review in five_star_reviews:
#             print(f"User: {review.get('userName')}, Score: {review.get('score')}, Date: {review.get('at')}")
#             print(f"Review: {review.get('content')[:100]}...")
#             print("-" * 20)
#     else:
#         print("No 5-star reviews found or an error occurred.")

#     # Test with an invalid app ID
#     invalid_app_id = "com.this.app.does.not.exist.qwerty"
#     print(f"\nFetching reviews for invalid app ID {invalid_app_id}...")
#     invalid_reviews = scrape_google_play_reviews(invalid_app_id)
#     if not invalid_reviews:
#         print("Correctly returned empty list for invalid app ID.")
```
