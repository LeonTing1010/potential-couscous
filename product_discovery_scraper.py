import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin

# --- Constants ---
DEFAULT_PRODUCT_HUNT_NEWEST_URL = "https://www.producthunt.com/newest"
DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# --- Main Scraping Function ---

def scrape_product_hunt_newest(target_url: str = DEFAULT_PRODUCT_HUNT_NEWEST_URL) -> list[dict]:
    """
    Scrapes product information from Product Hunt's "newest" page.

    IMPORTANT: HTML web scraping is highly dependent on the website's structure.
    The CSS selectors used in this function are based on past observations or
    examples and ARE VERY LIKELY TO BE OUTDATED. They will almost certainly
    need to be updated by inspecting the live Product Hunt website's HTML structure
    to make this scraper work correctly.

    Args:
        target_url: The URL of the Product Hunt page to scrape (defaults to the "newest" page).

    Returns:
        A list of dictionaries, where each dictionary contains information
        about a scraped product. Returns an empty list if fetching or parsing fails,
        or if no products are found with the current selectors.
    """
    print(f"[PH_SCRAPER_INFO] Starting scrape for URL: {target_url}")
    headers = {'User-Agent': DEFAULT_USER_AGENT}
    products_data = []
    retrieved_time_utc_iso = datetime.now(timezone.utc).isoformat()

    try:
        response = requests.get(target_url, headers=headers, timeout=10) # Added timeout
        response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
        print(f"[PH_SCRAPER_INFO] Successfully fetched HTML content (Status: {response.status_code}).")
    except requests.exceptions.HTTPError as e:
        print(f"[PH_SCRAPER_ERROR] HTTP error occurred: {e.response.status_code} - {e.response.reason} for URL: {target_url}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"[PH_SCRAPER_ERROR] Failed to fetch HTML from {target_url}: {e}")
        return []
    except Exception as e: # Catch any other unexpected error during request
        print(f"[PH_SCRAPER_ERROR] An unexpected error occurred during fetch for {target_url}: {e}")
        return []

    try:
        soup = BeautifulSoup(response.text, 'html.parser') # or 'lxml' if installed and preferred

        # --- !!! CRITICAL NOTE: SELECTOR UPDATE REQUIRED !!! ---
        # The following selectors are EXAMPLES and LIKELY OUTDATED.
        # You MUST inspect Product Hunt's live HTML to find the correct selectors.
        # Look for repeating patterns that define each product "card" or "item".
        
        # Conceptual: Find a main container if one exists, then find individual product cards.
        # This might be a direct find_all for product cards.
        # Example placeholder from prompt (almost certainly outdated):
        # product_cards_container = soup.find('div', class_='styles_container__... or similar') 
        # if not product_cards_container:
        #    product_cards = [] # handle if container not found
        # else:
        #    product_cards = product_cards_container.find_all('div', class_='styles_item__YY5AU') 

        # Direct attempt with a hypothetical product card selector (NEEDS UPDATE)
        # This selector `styles_item__YY5AU` is illustrative from the prompt.
        product_cards = soup.find_all('div', class_='styles_item__YY5AU') 
        # If the above doesn't work, try a more generic approach or inspect Product Hunt's HTML.
        # For example, Product Hunt might use semantic tags like <article> or list items <li>
        # or data attributes like `data-test="product-item"`.

        if not product_cards:
            print("[PH_SCRAPER_WARN] No product cards found using the current selectors. "
                  "The website structure might have changed, or selectors need an update. "
                  "Please inspect the HTML of Product Hunt's 'newest' page.")
            # Try an alternative generic selector if the primary one fails (example)
            # This is a GUESS and unlikely to work without inspection.
            # product_cards = soup.find_all('div', attrs={'data-test': lambda x: x and x.startswith('product-item')})
            # if not product_cards:
            #    print("[PH_SCRAPER_WARN] Alternative generic selector also found no product cards.")


        print(f"[PH_SCRAPER_INFO] Found {len(product_cards)} potential product card(s) with current selectors.")

        for card_index, card in enumerate(product_cards):
            product_name, tagline, ph_url, external_url, launch_date_str, upvotes_str, topics_list = (None,) * 7
            
            # --- !!! SELECTOR UPDATE REQUIRED FOR EACH FIELD BELOW !!! ---
            # These are conceptual examples. Replace with actual selectors after inspection.

            # Product Name & Product Hunt URL
            # Example: name_tag = card.find('a', class_='styles_title__2_089') (from prompt)
            name_tag = card.find('a', class_='styles_title__2_089') # NEEDS UPDATE
            if name_tag and name_tag.get_text(strip=True):
                product_name = name_tag.get_text(strip=True)
                ph_url_relative = name_tag.get('href')
                if ph_url_relative:
                    ph_url = urljoin(target_url, ph_url_relative) # Ensure absolute URL
            else: # Try another common pattern for name if first fails
                name_h_tag = card.find(['h2', 'h3', 'h4'], class_=lambda x: x and "title" in x.lower()) # NEEDS UPDATE
                if name_h_tag and name_h_tag.get_text(strip=True):
                     product_name = name_h_tag.get_text(strip=True)
                     if name_h_tag.name == 'a' and name_h_tag.get('href'):
                         ph_url = urljoin(target_url, name_h_tag.get('href'))
                     elif name_h_tag.find('a') and name_h_tag.find('a').get('href'): # Name in Hx, link inside
                         ph_url = urljoin(target_url, name_h_tag.find('a').get('href'))


            # Tagline/Description
            # Example: tagline_tag = card.find('p', class_='styles_tagline__351DE') (from prompt)
            tagline_tag = card.find('p', class_='styles_tagline__351DE') # NEEDS UPDATE
            if tagline_tag:
                tagline = tagline_tag.get_text(strip=True)
            else: # Try another common pattern
                tagline_div = card.find('div', class_=lambda x: x and ("description" in x.lower() or "tagline" in x.lower())) # NEEDS UPDATE
                if tagline_div: tagline = tagline_div.get_text(strip=True)

            # Upvotes
            # Example: upvote_tag_container = card.find('button', attrs={'data-test': 'vote-button'}) (from prompt)
            upvote_tag_container = card.find('button', attrs={'data-test': 'vote-button'}) # NEEDS UPDATE
            if upvote_tag_container:
                # Upvote count might be in a specific span inside the button
                upvote_span = upvote_tag_container.find('span', class_=lambda x: x and "count" in x.lower()) # NEEDS UPDATE
                if not upvote_span: upvote_span = upvote_tag_container # If count is directly in button text
                
                if upvote_span:
                    upvotes_str_raw = upvote_span.get_text(strip=True)
                    # Clean up common formats like "1.2k" or remove non-digits
                    if 'k' in upvotes_str_raw.lower():
                        upvotes_str_raw = upvotes_str_raw.lower().replace('k', '')
                        try: upvotes_str = str(int(float(upvotes_str_raw) * 1000))
                        except ValueError: upvotes_str = "0" # Default on parse error
                    else:
                        upvotes_str = ''.join(filter(str.isdigit, upvotes_str_raw))
            if not upvotes_str: # Fallback if specific button not found
                # Look for a div/span that looks like an upvote count near a vote icon/button
                # This is highly speculative and needs inspection.
                potential_upvote_tags = card.find_all(['div', 'span'], class_=lambda x: x and ("vote" in x.lower() or "count" in x.lower())) # NEEDS UPDATE
                for tag in potential_upvote_tags:
                    text = tag.get_text(strip=True)
                    if text.isdigit():
                        upvotes_str = text
                        break
                    elif 'k' in text.lower(): # Handle "1.2k" format
                         cleaned_text = text.lower().replace('k', '')
                         try: upvotes_str = str(int(float(cleaned_text) * 1000)); break
                         except ValueError: pass


            upvotes = int(upvotes_str) if upvotes_str and upvotes_str.isdigit() else 0

            # Topics/Categories
            # Example: topic_tags_elements = card.find_all('a', class_='styles_topic__1_sNm') (from prompt)
            topic_tags_elements = card.find_all('a', class_='styles_topic__1_sNm') # NEEDS UPDATE
            if not topic_tags_elements: # Fallback
                # Look for a div containing multiple topic-like links/buttons
                topics_container = card.find('div', class_=lambda x: x and "topics" in x.lower()) # NEEDS UPDATE
                if topics_container:
                    topic_tags_elements = topics_container.find_all('a') # NEEDS UPDATE
            
            topics_list = [tag.get_text(strip=True) for tag in topic_tags_elements if tag.get_text(strip=True)] if topic_tags_elements else []

            # Launch Date (raw string extraction)
            # Often in a span or time tag. May be relative ("Launched X days ago").
            # Needs inspection. Example: <span class="styles_launchDate__...">
            launch_date_tag = card.find(['span', 'time'], class_=lambda x: x and ("date" in x.lower() or "launch" in x.lower() or "timestamp" in x.lower())) # NEEDS UPDATE
            if launch_date_tag:
                launch_date_str = launch_date_tag.get_text(strip=True)
                if launch_date_tag.has_attr('datetime'): # Prefer datetime attribute if available
                    launch_date_str = launch_date_tag['datetime']


            # External URL (Product's own website)
            # This is often NOT on the listing card directly. Might be a link with text "Visit website" or similar.
            # For MVP, if not easily found on card, set to None or ph_url.
            # Example: external_link_tag = card.find('a', attrs={'rel': 'noopener noreferrer nofollow', 'target': '_blank', 'href': lambda x: x and not x.startswith('/posts/')})
            # This is a complex selector that tries to find an outbound link not pointing to producthunt.com itself.
            # NEEDS HEAVY INSPECTION AND TESTING.
            external_link_tag = card.find('a', class_='styles_websiteLink__...', target='_blank') # Highly speculative, NEEDS UPDATE
            if external_link_tag and external_link_tag.get('href'):
                external_url = external_link_tag['href']
                # Ensure it's absolute and not just another PH link if possible
                if not external_url.startswith(('http://', 'https://')):
                    external_url = urljoin(target_url, external_url)
                if "producthunt.com" in external_url and ph_url and external_url != ph_url: # Heuristic
                    external_url = None # Reset if it seems to be just another PH link but not the main one
            
            if not external_url and ph_url: # Fallback if no distinct external URL found
                 pass # Keep external_url as None or could set to ph_url if desired. Defaulting to None is cleaner.


            # Only add if essential data like name and PH URL were found
            if product_name and ph_url:
                product_info = {
                    "product_name": product_name,
                    "tagline": tagline,
                    "ph_url": ph_url,
                    "external_url": external_url,
                    "launch_date_str": launch_date_str,
                    "upvotes": upvotes,
                    "topics": topics_list,
                    "platform_source": "product_hunt",
                    "retrieved_utc": retrieved_time_utc_iso
                }
                products_data.append(product_info)
                print(f"[PH_SCRAPER_INFO] Extracted: {product_name[:50]}... (Card {card_index+1}/{len(product_cards)})")
            else:
                print(f"[PH_SCRAPER_WARN] Could not extract essential data (name/PH URL) for a card (Index {card_index}). Selectors might need update or card structure differs.")
                # Optionally log the HTML of the problematic card for debugging:
                # print(f"[PH_SCRAPER_DEBUG] Card HTML: {card.prettify()[:500]}...")


    except Exception as e:
        print(f"[PH_SCRAPER_ERROR] An error occurred during HTML parsing or data extraction: {e}")
        import traceback
        print(f"[PH_SCRAPER_TRACE]\n{traceback.format_exc()}")

    if not products_data:
        print("[PH_SCRAPER_INFO] No products were successfully scraped with the current configuration.")
    else:
        print(f"[PH_SCRAPER_INFO] Successfully scraped {len(products_data)} product(s) from {target_url}.")
        
    return products_data

# No main execution block (`if __name__ == "__main__":`) as this is intended to be an importable module.
```
