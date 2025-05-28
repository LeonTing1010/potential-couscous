import os
import json
import openai

def _construct_llm_prompt(reviews_texts: list[str], app_name: str) -> str:
    """
    Constructs a detailed prompt for the LLM to analyze app reviews.

    Args:
        reviews_texts: A list of review strings.
        app_name: The name of the app being reviewed.

    Returns:
        A string containing the formatted prompt for the LLM.
    """
    formatted_reviews = "\n".join([f"- \"{review}\"" for review in reviews_texts]) # Added quotes for clarity

    # Note: The JSON structure below is part of the instruction to the LLM.
    # It's crucial that the LLM adheres to this format.
    prompt = f"""
You are an expert app review analyst. Analyze the following 1-star app reviews for the app named "{app_name}".

Provided Reviews:
{formatted_reviews}

Based *only* on the reviews provided above, please perform the following tasks:
1. Identify the top 3 to 5 most common pain points mentioned by users. If fewer than 3 distinct pain points are evident, list as many as you can identify.
2. For each identified pain point:
    a. Provide a concise summary (1-2 sentences) describing the pain point.
    b. List up to 3 short, verbatim snippets (direct quotes) from the provided reviews that clearly illustrate this pain point. If verbatim snippets are very long, you can use "..." to indicate omitted parts, but the core of the snippet must be verbatim.
3. Provide an overall summary of these 1-star reviews, capturing the general sentiment and major issues.

Format your entire output as a single, valid JSON object. Do not include any explanatory text, headings, or markdown before or after the JSON object. The JSON object must strictly follow this structure:

{{
  "app_name": "{app_name}",
  "identified_pain_points": [
    {{
      "pain_point_summary": "Concise summary of the first identified pain point.",
      "example_snippets": [
        "Verbatim snippet from a review illustrating this pain point.",
        "Another verbatim snippet for the same pain point."
      ]
    }},
    {{
      "pain_point_summary": "Concise summary of the second identified pain point.",
      "example_snippets": [
        "Verbatim snippet for this second pain point."
      ]
    }}
    // Add more pain point objects here as identified (up to 5)
  ],
  "overall_summary_of_1_star_reviews": "A brief general summary of the sentiment and major issues highlighted in these 1-star reviews."
}}

Important considerations for your response:
- Ensure the "app_name" field in the JSON output is exactly "{app_name}".
- Ensure all "example_snippets" are direct, verbatim quotes from the provided reviews.
- If no relevant snippets are found for a pain point, provide an empty list [] for "example_snippets".
- If no pain points can be clearly identified, the "identified_pain_points" list can be empty.
"""
    return prompt

def analyze_reviews_with_llm(reviews_texts: list[str], app_name: str = "this app", llm_api_key: str = None, llm_model: str = "gpt-3.5-turbo") -> dict:
    """
    Analyzes a list of review texts using an LLM to identify pain points and summarize feedback.

    Args:
        reviews_texts: A list of strings, where each string is a user review.
        app_name: The name of the app being reviewed. Defaults to "this app".
        llm_api_key: The OpenAI API key. If None, attempts to read from 
                     the OPENAI_API_KEY environment variable.
        llm_model: The LLM model to use (e.g., "gpt-3.5-turbo", "gpt-4"). 
                   Defaults to "gpt-3.5-turbo".

    Returns:
        A dictionary containing the LLM's analysis, formatted as specified in
        the prompt. Returns an error dictionary if issues occur (e.g., no reviews,
        API key missing, API error, failed to parse response).

    Raises:
        ValueError: If the API key is not provided and not found in the environment.
    """
    if not reviews_texts:
        return {"error": "No review texts provided for analysis."}

    # API Key Handling
    api_key_to_use = llm_api_key
    if api_key_to_use is None:
        api_key_to_use = os.getenv("OPENAI_API_KEY")
    
    if api_key_to_use is None:
        # Raising ValueError as per requirement for missing API key
        raise ValueError("OpenAI API key not provided as an argument and not found in OPENAI_API_KEY environment variable.")
    
    openai.api_key = api_key_to_use

    # Prompt Construction
    prompt_content = _construct_llm_prompt(reviews_texts, app_name)

    try:
        # LLM Interaction
        # Using the newer openai client syntax if available, but sticking to ChatCompletion for now
        response = openai.ChatCompletion.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes app reviews. Your output must be a single, valid JSON object as per the user's instructions, with no other text or explanations before or after it."},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.5,  # For a balance of creativity and predictability
            max_tokens=2000   # Increased to accommodate potentially larger review lists and detailed JSON
        )
        
        llm_response_content = response.choices[0].message['content'].strip()

        # Response Parsing
        try:
            # Sometimes the LLM might still wrap the JSON in ```json ... ```
            if llm_response_content.startswith("```json"):
                llm_response_content = llm_response_content[7:] # Remove ```json\n
                if llm_response_content.endswith("```"):
                    llm_response_content = llm_response_content[:-3] # Remove ```
            
            parsed_response = json.loads(llm_response_content)
            return parsed_response
        except json.JSONDecodeError as je:
            error_message = f"Error: Failed to parse LLM response into JSON. JSONDecodeError: {str(je)}"
            print(f"{error_message}\nRaw response snippet (first 500 chars):\n{llm_response_content[:500]}")
            return {"error": "Failed to parse LLM response", "details": str(je), "raw_response": llm_response_content}

    except openai.error.AuthenticationError as e:
        print(f"OpenAI API AuthenticationError: {e}")
        return {"error": "OpenAI API authentication failed", "details": str(e)}
    except openai.error.RateLimitError as e:
        print(f"OpenAI API RateLimitError: {e}")
        return {"error": "OpenAI API rate limit exceeded", "details": str(e)}
    except openai.error.APIConnectionError as e:
        print(f"OpenAI API APIConnectionError: {e}")
        return {"error": "Failed to connect to OpenAI API", "details": str(e)}
    except openai.error.InvalidRequestError as e:
        # This can happen if the prompt + reviews are too long for the model's context window
        print(f"OpenAI API InvalidRequestError: {e}")
        return {"error": "Invalid request to OpenAI API (potentially too much text)", "details": str(e), "prompt_sent_length_approx": len(prompt_content)}
    except openai.error.Timeout as e:
        print(f"OpenAI API Timeout: {e}")
        return {"error": "OpenAI API request timed out", "details": str(e)}
    except openai.error.APIError as e: # General API error from OpenAI
        print(f"OpenAI API APIError: {e}")
        return {"error": "Generic OpenAI API error occurred", "details": str(e)}
    except Exception as e: # Catch any other unexpected errors during the process
        print(f"An unexpected error occurred: {type(e).__name__} - {e}")
        return {"error": "An unexpected error occurred", "details": str(e)}

# Note: No main execution block (if __name__ == '__main__':) as per instructions.
```
