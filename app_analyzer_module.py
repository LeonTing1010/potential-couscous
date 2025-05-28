from scraper_module import scrape_google_play_reviews
from llm_integration_module import analyze_reviews_with_llm
# No json or datetime needed here directly as timestamping is in llm_integration_module
# and output is a dictionary.

def process_single_app_reviews(
    app_id: str, 
    app_name: str, 
    reviews_to_fetch: int = 100, 
    target_star_rating: int = 1, 
    llm_model: str = "gpt-3.5-turbo"
) -> dict | None:
    """
    Fetches, analyzes, and processes reviews for a single app.

    This function orchestrates the scraping of reviews for a specific app ID and
    analyzes their content using an LLM. It's designed to be a core reusable 
    component for processing individual apps.

    Args:
        app_id: The unique identifier of the app on Google Play 
                (e.g., 'com.google.android.gm').
        app_name: The human-readable name of the app, used in prompts and outputs.
        reviews_to_fetch: The target number of reviews to fetch that match the 
                          `target_star_rating`. Defaults to 100.
        target_star_rating: The specific star rating (1 to 5) to filter reviews by.
                              Defaults to 1 (typically for negative feedback analysis).
        llm_model: The LLM model to use for analysis (e.g., "gpt-3.5-turbo", "gpt-4").
                   Defaults to "gpt-3.5-turbo".

    Returns:
        A dictionary containing the LLM's analysis if successful. This dictionary
        is expected to include 'app_id', 'app_name', 'identified_pain_points', 
        'analysis_summary' (formerly 'overall_summary_of_1_star_reviews'), 
        'analysis_timestamp_utc', and now also 'scraper_parameters' and 'source_type'.
        Returns None if scraping yields no reviews or if all fetched reviews 
        have empty content.
        Returns an error dictionary (as returned by `analyze_reviews_with_llm`) 
        if the LLM analysis itself encounters an error.
    """
    print(f"\n[INFO] Starting review processing for app: '{app_name}' (ID: {app_id}, Target Rating: {target_star_rating}-star)")

    # 1. Fetch reviews using scraper_module
    print(f"[INFO] Fetching up to {reviews_to_fetch} {target_star_rating}-star reviews for '{app_id}'...")
    scraped_reviews = scrape_google_play_reviews(
        app_id=app_id,
        lang='en',  # Currently hardcoded; could be parameterized if multi-language support is needed
        country='us', # Currently hardcoded; could be parameterized for different regions
        reviews_to_fetch=reviews_to_fetch,
        target_star_rating=target_star_rating
    )

    if not scraped_reviews:
        print(f"[WARN] No {target_star_rating}-star reviews found, or scraping failed for '{app_name}' (ID: {app_id}).")
        return None

    print(f"[INFO] Successfully fetched {len(scraped_reviews)} {target_star_rating}-star reviews for '{app_id}'.")

    # 2. Prepare review texts for LLM
    # Ensure 'content' exists and is not None or empty string before adding.
    review_texts = [review['content'] for review in scraped_reviews if review.get('content')]

    if not review_texts:
        print(f"[WARN] No actual review content available from the {len(scraped_reviews)} fetched reviews for '{app_name}' (ID: {app_id}). All reviews might have empty content.")
        return None
    
    # Determine actual count of non-empty reviews processed
    reviews_fetched_actual_count = len(review_texts)
    print(f"[INFO] Prepared {reviews_fetched_actual_count} non-empty review texts for LLM analysis.")

    # 3. Analyze reviews with LLM using llm_integration_module
    print(f"[INFO] Analyzing {reviews_fetched_actual_count} review texts for '{app_name}' with LLM ({llm_model})...")
    
    llm_analysis_result = analyze_reviews_with_llm(
        reviews_texts=review_texts,
        app_id=app_id, 
        app_name=app_name,
        llm_model=llm_model
    )

    # Check if LLM analysis returned an error
    if "error" in llm_analysis_result:
        print(f"[ERROR] LLM analysis failed for '{app_name}' (ID: {app_id}). Error: {llm_analysis_result.get('error')}")
        if llm_analysis_result.get('details'):
            print(f"[ERROR] Details: {llm_analysis_result.get('details')}")
        return llm_analysis_result # Return the error dictionary from LLM module

    # If successful, augment the result with scraper_parameters and source_type
    print(f"[SUCCESS] Successfully processed and analyzed reviews for '{app_name}' (ID: {app_id}).")
    if 'analysis_timestamp_utc' in llm_analysis_result:
        print(f"[INFO] Analysis timestamp: {llm_analysis_result['analysis_timestamp_utc']}")
    
    # Add scraper_parameters to the successful result
    llm_analysis_result["scraper_parameters"] = {
        "reviews_fetched_target_count": reviews_to_fetch,
        "reviews_fetched_actual_count": reviews_fetched_actual_count,
        "target_star_rating": target_star_rating
    }
    
    # Add source_type to the successful result
    llm_analysis_result["source_type"] = "google_play_reviews" # Hardcoded for now

    print(f"[INFO] Added 'scraper_parameters' and 'source_type' to the analysis result for '{app_name}'.")
    
    return llm_analysis_result

# No if __name__ == "__main__": block as this is intended to be an importable module.
```
