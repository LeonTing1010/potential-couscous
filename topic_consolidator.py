import json
import os
from pathlib import Path
from collections import defaultdict

# Optional NLTK imports for stemming
try:
    from nltk.stem import PorterStemmer
    from nltk.tokenize import word_tokenize
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    PorterStemmer = None
    word_tokenize = None
    print("[TOPIC_CONSOLIDATOR_WARN] NLTK library not found. Stemming will not be available. "
          "Install NLTK (e.g., 'pip install nltk') and download 'punkt' (nltk.download('punkt')) for stemming capabilities.")

# --- Constants ---
APP_ANALYSES_DIR = Path("./all_app_analyses")
FORUM_NLP_ANALYSES_DIR = Path("./all_forum_nlp_analyses")
PRODUCT_MENTIONS_DIR = Path("./all_product_mentions")
SYNTHESIS_OUTPUT_DIR = Path("./all_synthesis_output")
CONSOLIDATED_TOPICS_FILE = SYNTHESIS_OUTPUT_DIR / "consolidated_topics.json"

# --- Core Functions ---

def _normalize_term(term: str, stemmer=None) -> str:
    """
    Normalizes a term by converting to lowercase and optionally stemming.

    Args:
        term: The term string to normalize.
        stemmer: An optional NLTK stemmer instance (e.g., PorterStemmer).
                 If None or NLTK is unavailable, only lowercasing is performed.

    Returns:
        The normalized term string.
    """
    term = term.lower()
    if stemmer and NLTK_AVAILABLE and word_tokenize:
        try:
            tokens = word_tokenize(term)
            stemmed_tokens = [stemmer.stem(token) for token in tokens]
            return " ".join(stemmed_tokens)
        except Exception as e: # Catch potential NLTK errors if punkt is missing etc.
            print(f"[NORMALIZE_WARN] Error during stemming for term '{term}': {e}. Returning lowercased term only.")
            return term 
    return term

def extract_terms_from_file(filepath: Path, source_type: str, normalize_func) -> list[dict]:
    """
    Loads JSON data from a file and extracts relevant terms based on source type.

    Args:
        filepath: Path to the JSON file.
        source_type: Type of the source file ("app_review", "forum_nlp", "product_mention").
        normalize_func: The function to use for normalizing extracted terms.

    Returns:
        A list of dictionaries, each representing an extracted term and its metadata.
        Returns an empty list if file loading fails or no terms are extracted.
    """
    raw_terms_extracted = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"[EXTRACT_TERMS_ERROR] Failed to load or parse JSON from '{filepath}': {e}")
        return []
    if not isinstance(data, dict): # Expecting a dictionary at the root
        print(f"[EXTRACT_TERMS_WARN] Data in '{filepath}' is not a dictionary. Skipping.")
        return []

    if source_type == "app_review":
        # From app_analyzer_module output (via llm_integration_module)
        raw_terms_extracted.extend(data.get("key_topics_keywords", []))
        for pain_point in data.get("identified_pain_points", []):
            if isinstance(pain_point, dict) and pain_point.get("pain_point_summary"):
                raw_terms_extracted.append(pain_point["pain_point_summary"])
        if data.get("analysis_summary"): # Previously overall_summary_of_1_star_reviews
             raw_terms_extracted.append(data.get("analysis_summary"))


    elif source_type == "forum_nlp":
        # From forum_llm_analyzer_module output
        raw_terms_extracted.extend(data.get("key_topics_keywords", []))
        if data.get("primary_user_need_or_problem"):
            raw_terms_extracted.append(data["primary_user_need_or_problem"])
        # Pain point indicators are verbatim quotes, might be too specific or long for direct "topics"
        # but could be considered. For now, focusing on keywords and summaries.
        # for verbatim_quote in data.get("pain_point_indicators_verbatim", []):
        #     raw_terms_extracted.append(verbatim_quote) # Decided against this for now
        if data.get("overall_discussion_summary"):
            raw_terms_extracted.append(data["overall_discussion_summary"])

    elif source_type == "product_mention":
        # From product_discovery_scraper output
        if data.get("product_name"):
            raw_terms_extracted.append(data["product_name"])
        if data.get("tagline"):
            raw_terms_extracted.append(data["tagline"])
        raw_terms_extracted.extend(data.get("topics", [])) # PH topics are usually good keywords

    else:
        print(f"[EXTRACT_TERMS_WARN] Unknown source_type '{source_type}' for file '{filepath}'.")
        return []

    # Create structured term list
    structured_terms = []
    for raw_term in raw_terms_extracted:
        if not raw_term or not isinstance(raw_term, str) or not raw_term.strip():
            continue # Skip empty or non-string terms
        
        # Basic filtering for very short terms (e.g., single characters, "N/A") might be useful here
        if len(raw_term.strip()) <= 2 and raw_term.lower() != "ai": # Allow "ai" but filter other short terms
            if raw_term.lower() not in ["ai", "vr", "ar"]: # Example exceptions
                continue
        if raw_term.lower() == "n/a":
            continue

        structured_terms.append({
            "original_term": raw_term.strip(),
            "normalized_term": normalize_func(raw_term.strip()),
            "source_file": str(filepath),
            "source_type": source_type
        })
    return structured_terms

def consolidate_topics(output_filepath: Path = CONSOLIDATED_TOPICS_FILE, use_stemming: bool = False) -> bool:
    """
    Consolidates keywords, topics, and product names from all data sources.

    Args:
        output_filepath: Path to save the consolidated JSON output.
        use_stemming: If True, attempts to use NLTK PorterStemmer for normalization.

    Returns:
        True if consolidation and saving were successful, False otherwise.
    """
    print("[CONSOLIDATE_INFO] Starting topic consolidation process...")
    stemmer_instance = None
    if use_stemming:
        if NLTK_AVAILABLE and PorterStemmer and word_tokenize:
            try:
                # Download 'punkt' if not already present (for word_tokenize)
                # nltk.download('punkt', quiet=True) # This line can cause issues in restricted envs
                # It's better to assume user has run nltk.download('punkt') once if they want stemming.
                stemmer_instance = PorterStemmer()
                print("[CONSOLIDATE_INFO] NLTK PorterStemmer initialized for term normalization.")
            except Exception as e: # Catch LookupError if 'punkt' is not downloaded
                print(f"[CONSOLIDATE_WARN] Failed to initialize NLTK stemmer or download 'punkt': {e}. "
                      "Proceeding without stemming. For stemming, ensure NLTK's 'punkt' resource is downloaded "
                      "by running: import nltk; nltk.download('punkt')")
                use_stemming = False # Disable stemming if it failed to init
        else:
            print("[CONSOLIDATE_WARN] 'use_stemming' is True, but NLTK is not available or "
                  "PorterStemmer/word_tokenize could not be imported. Proceeding without stemming.")
            use_stemming = False # Ensure it's disabled

    normalize_function = lambda term: _normalize_term(term, stemmer_instance if use_stemming else None)
    
    all_extracted_terms = []
    source_configs = [
        {"dir": APP_ANALYSES_DIR, "type": "app_review", "glob_pattern": "**/*.json"},
        {"dir": FORUM_NLP_ANALYSES_DIR, "type": "forum_nlp", "glob_pattern": "**/*_nlp.json"},
        {"dir": PRODUCT_MENTIONS_DIR, "type": "product_mention", "glob_pattern": "**/*.json"}
    ]

    for config in source_configs:
        source_dir = config["dir"]
        source_type = config["type"]
        glob_pattern = config["glob_pattern"]
        
        if not source_dir.is_dir():
            print(f"[CONSOLIDATE_WARN] Directory not found for {source_type}: '{source_dir}'. Skipping.")
            continue
        
        print(f"[CONSOLIDATE_INFO] Processing {source_type} from '{source_dir}'...")
        file_count = 0
        for filepath in source_dir.rglob(glob_pattern): # rglob for recursive search
            if filepath.is_file():
                file_count += 1
                extracted = extract_terms_from_file(filepath, source_type, normalize_function)
                all_extracted_terms.extend(extracted)
        print(f"[CONSOLIDATE_INFO] Processed {file_count} files for {source_type}, found {len(all_extracted_terms)} terms so far.")

    if not all_extracted_terms:
        print("[CONSOLIDATE_INFO] No terms extracted from any source. Output file will not be created/updated.")
        # Optionally create an empty file or structure:
        # SYNTHESIS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        # with open(output_filepath, 'w', encoding='utf-8') as f:
        #     json.dump({"message": "No terms found to consolidate."}, f, indent=2)
        return True # Considered success as process ran, just no data

    # Group and Count
    consolidated = defaultdict(lambda: {"count": 0, "original_terms": set(), "sources": []})
    for item in all_extracted_terms:
        norm_term = item['normalized_term']
        if not norm_term: continue # Skip if normalization resulted in empty string

        consolidated[norm_term]['count'] += 1
        consolidated[norm_term]['original_terms'].add(item['original_term'])
        # To keep sources list manageable, maybe only store unique file paths or a sample
        # For now, storing all as per prompt structure
        consolidated[norm_term]['sources'].append({
            "source_file": item['source_file'], 
            "source_type": item['source_type'],
            "original_mention": item['original_term'] 
        })
    
    # Convert sets to sorted lists and sort final list by count
    final_consolidated_list = []
    for term, data in consolidated.items():
        final_consolidated_list.append({
            "normalized_term": term,
            "count": data["count"],
            "original_terms": sorted(list(data["original_terms"])),
            "sources": data["sources"] # Sources list can be large, consider summarizing if needed
        })
    
    # Sort by count (descending)
    final_consolidated_list.sort(key=lambda x: x["count"], reverse=True)

    try:
        output_filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(final_consolidated_list, f, indent=2, ensure_ascii=False)
        print(f"[CONSOLIDATE_SUCCESS] Consolidated {len(final_consolidated_list)} unique normalized terms into '{output_filepath}'.")
        return True
    except (IOError, OSError) as e:
        print(f"[CONSOLIDATE_ERROR] Failed to save consolidated topics to '{output_filepath}': {e}")
        return False
    except Exception as e:
        print(f"[CONSOLIDATE_ERROR] An unexpected error occurred during saving: {e}")
        return False

# No main execution block as this is a library module.
```
