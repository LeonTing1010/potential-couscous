import json
import os # Included as per example, though API key is handled by llm_integration_module
from scraper_module import scrape_google_play_reviews
from llm_integration_module import analyze_reviews_with_llm

# --- Configuration ---
APP_ID_TO_ANALYZE = "com.google.android.gm"  # Example: Gmail app ID
APP_NAME = "Gmail"  # Human-readable name for the app
REVIEWS_TO_FETCH_COUNT = 100  # Target number of matching-star reviews to fetch
TARGET_STAR_RATING_FILTER = 1  # Fetch only 1-star reviews

# Make app_id more filename-friendly (e.g., replace dots with underscores)
APP_ID_FILENAME_SAFE = APP_ID_TO_ANALYZE.replace('.', '_')
OUTPUT_FILENAME_TEMPLATE = "{app_id_safe}_{rating}star_analysis.json" # Simplified template name
LLM_MODEL_NAME = "gpt-3.5-turbo"
# The OPENAI_API_KEY is handled by llm_integration_module (checks arg, then env var)

def run_analysis():
    """
    Orchestrates the fetching, analysis, and saving of app reviews.
    """
    print(f"Starting analysis for app: {APP_NAME} (ID: {APP_ID_TO_ANALYZE})")

    output_filename = OUTPUT_FILENAME_TEMPLATE.format(
        app_id_safe=APP_ID_FILENAME_SAFE, 
        rating=TARGET_STAR_RATING_FILTER
    )

    # 1. Fetch reviews
    print(f"\nFetching up to {REVIEWS_TO_FETCH_COUNT} {TARGET_STAR_RATING_FILTER}-star reviews for {APP_NAME}...")
    scraped_reviews = scrape_google_play_reviews(
        app_id=APP_ID_TO_ANALYZE,
        lang='en', # Hardcoded for MVP
        country='us', # Hardcoded for MVP
        reviews_to_fetch=REVIEWS_TO_FETCH_COUNT,
        target_star_rating=TARGET_STAR_RATING_FILTER
    )

    if not scraped_reviews:
        print(f"No {TARGET_STAR_RATING_FILTER}-star reviews found for {APP_NAME}, or an error occurred during scraping.")
        return

    print(f"Successfully fetched {len(scraped_reviews)} {TARGET_STAR_RATING_FILTER}-star reviews.")

    # 2. Prepare review texts for LLM
    # Ensure 'content' exists and is not None or empty string before adding.
    review_texts = [review['content'] for review in scraped_reviews if review.get('content')]

    if not review_texts:
        print("No review content available from the fetched reviews to analyze (e.g., all reviews had empty content field).")
        return
    
    print(f"Prepared {len(review_texts)} non-empty review texts for LLM analysis.")
    # Example: print first few characters of the first review if available
    # if review_texts:
    #     print(f"Snippet of the first review text: '{review_texts[0][:100]}...'")


    # 3. Analyze reviews with LLM
    print(f"\nAnalyzing {len(review_texts)} review texts with LLM ({LLM_MODEL_NAME})... This may take some time.")
    # API key is handled by analyze_reviews_with_llm (arg -> env var OPENAI_API_KEY)
    llm_analysis_result = analyze_reviews_with_llm(
        reviews_texts=review_texts,
        app_name=APP_NAME, # Pass the human-readable app name
        llm_model=LLM_MODEL_NAME
        # llm_api_key can be passed here if needed, but module checks env var
    )

    if "error" in llm_analysis_result:
        print("\nLLM analysis failed.")
        print(f"Error type: {llm_analysis_result.get('error')}")
        print(f"Error details: {llm_analysis_result.get('details', 'No specific details provided.')}")
        if "raw_response" in llm_analysis_result:
            print(f"Raw LLM response snippet (first 500 chars): {llm_analysis_result['raw_response'][:500]}...")
        return

    print("LLM analysis successful.")

    # 4. Save output
    try:
        print(f"\nSaving analysis to '{output_filename}'...")
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(llm_analysis_result, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved analysis to '{os.path.abspath(output_filename)}'") # Show absolute path
    except IOError as e:
        print(f"\nError saving analysis to file '{output_filename}': {e}")
    except Exception as e: # Catch any other unexpected error during file save
        print(f"\nAn unexpected error occurred while saving the file '{output_filename}': {e}")


if __name__ == "__main__":
    print("--- 1-Star Review Analyzer MVP ---")
    try:
        run_analysis()
    except ValueError as ve:
        # This primarily catches the API key missing error if raised from llm_integration_module
        print(f"\n[CRITICAL ERROR] Configuration Error: {ve}")
        print("This usually means the OpenAI API key is missing.")
        print("Please ensure the OPENAI_API_KEY environment variable is set, or pass the key directly if the function supports it.")
    except ImportError as ie:
        print(f"\n[CRITICAL ERROR] Import Error: {ie}.")
        print("Please ensure all required modules (scraper_module.py, llm_integration_module.py) are in the same directory as main.py or correctly installed and accessible in your Python path.")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] An unexpected critical error occurred in the main execution: {type(e).__name__} - {e}")
    finally:
        print("\n--- Analysis run finished ---")
```
