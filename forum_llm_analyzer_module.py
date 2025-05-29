import os
import json
import openai
from datetime import datetime, timezone

def _construct_forum_post_llm_prompt(post_data: dict, max_comments_to_process: int = 10) -> str:
    """
    Constructs a detailed prompt for the LLM to analyze a forum post and its comments.

    Args:
        post_data: A dictionary containing the scraped forum post data.
                   Expected keys: 'id', 'subreddit_name_prefixed', 'title', 
                                  'text_content', 'comments' (list of dicts).
        max_comments_to_process: The maximum number of comments to include in the prompt.

    Returns:
        A string containing the formatted prompt for the LLM.
    """
    post_id = post_data.get('id', 'N/A')
    subreddit_name = post_data.get('subreddit_name_prefixed', 'N/A')
    post_title = post_data.get('title', 'N/A')
    post_selftext = post_data.get('text_content', 'No main content provided by OP.')
    if not post_selftext.strip(): # Handle empty or whitespace-only selftext
        post_selftext = 'No main content provided by OP.'

    comments = post_data.get('comments', [])
    formatted_comments_list = []
    for i, comment in enumerate(comments):
        if i >= max_comments_to_process:
            formatted_comments_list.append("... [further comments truncated] ...")
            break
        author = comment.get('author', '[unknown author]')
        text = comment.get('text_content', '[comment text not available]')
        formatted_comments_list.append(f"Comment by {author}:\n{text}\n---")
    
    formatted_comments_block = "\n".join(formatted_comments_list)
    if not formatted_comments_block:
        formatted_comments_block = "No comments available or processed."

    # LLM Prompt based on Step 7.1
    prompt = f"""
You are an expert discussion analyst. Based *only* on the provided forum post title, its main content (if any), and its comments, perform a detailed analysis.

**Forum Post Details:**
*   **Subreddit:** "{subreddit_name}"
*   **Post ID:** "{post_id}"
*   **Title:** "{post_title}"
*   **Main Content (OP):**
    ```
    {post_selftext}
    ```

**Comments (up to {max_comments_to_process} processed):**
```
{formatted_comments_block}
```

**Analysis Tasks:**

1.  **Primary User Need/Problem:** Identify and describe the core user need, problem, or question being expressed or implied in the post and its comments. (1-2 sentences)
2.  **Key Topics/Keywords:** List 3-5 key topics or keywords that best summarize the discussion.
3.  **Sentiment Regarding Problem/Need:** Describe the overall sentiment (e.g., frustrated, curious, seeking advice, happy with solutions) of the original poster and commenters regarding the identified need or problem. (1-2 sentences)
4.  **Pain Point Indicators (Verbatim):** Quote 2-4 short, verbatim phrases or sentences from the post or comments that clearly indicate user pain points, frustrations, or unmet needs. If not explicitly stated, provide an empty list [].
5.  **Suggested Solutions/Ideas from Comments:** List any solutions, tools, or ideas suggested by commenters to address the need/problem. For each suggestion, provide a brief summary and, if possible, a verbatim quote. If none, provide an empty list [].
6.  **Overall Discussion Summary:** Provide a brief overall summary of the discussion, its main themes, and any notable outcomes or unanswered questions. (2-3 sentences)

**Output Format:**
Return your entire analysis as a single, valid JSON object. Do not include any text outside of this JSON object. The JSON object must strictly follow this structure:

{{
  "source_post_id": "{post_id}",
  "analyzed_subreddit": "{subreddit_name}",
  "primary_user_need_or_problem": "Description of the core user need or problem.",
  "key_topics_keywords": ["keyword1", "topic2", "relevant_term3"],
  "sentiment_regarding_problem_or_need": "Overall sentiment description.",
  "pain_point_indicators_verbatim": [
    "Verbatim quote indicating a pain point 1.",
    "Verbatim quote indicating a pain point 2."
  ],
  "suggested_solutions_from_comments": [
    {{
      "solution_summary": "Summary of solution/idea 1 suggested in comments.",
      "verbatim_quote": "Optional: Verbatim quote for solution 1."
    }}
  ],
  "overall_discussion_summary": "Overall summary of the discussion."
}}

Ensure all verbatim quotes are exact. If a field is not applicable or no information is found, use an empty list [] for arrays (like 'pain_point_indicators_verbatim' or 'suggested_solutions_from_comments' if none are found), or "N/A" or an appropriate empty string for string fields. The fields "source_post_id" and "analyzed_subreddit" must be populated with the provided Post ID and Subreddit name respectively.
"""
    return prompt

def analyze_forum_post_with_llm(
    post_data: dict, 
    llm_api_key: str = None, 
    llm_model: str = "gpt-3.5-turbo", 
    max_comments_to_process: int = 10
) -> dict:
    """
    Analyzes a single forum post's content (including comments) using an LLM.

    Args:
        post_data: A dictionary containing the scraped forum post data. 
                   Expected keys include 'id', 'subreddit_name_prefixed', 'title', 
                   'text_content', and 'comments'.
        llm_api_key: Optional OpenAI API key. If None, attempts to read from 
                     the OPENAI_API_KEY environment variable.
        llm_model: The LLM model to use (e.g., "gpt-3.5-turbo", "gpt-4").
        max_comments_to_process: Max number of comments to include in the LLM prompt.

    Returns:
        A dictionary containing the LLM's structured analysis, augmented with an
        'nlp_analysis_timestamp_utc'. Returns an error dictionary if issues occur.

    Raises:
        ValueError: If the API key is not provided and not found in the environment.
    """
    if not post_data or not isinstance(post_data, dict):
        return {"error": "No post data provided for analysis or data is not a dictionary."}
    if not post_data.get("id") or not post_data.get("subreddit_name_prefixed"):
         return {"error": "Post data is missing required 'id' or 'subreddit_name_prefixed' fields."}


    # API Key Handling
    api_key_to_use = llm_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key_to_use:
        raise ValueError("OpenAI API key not provided as an argument and not found in OPENAI_API_KEY environment variable.")
    openai.api_key = api_key_to_use

    # Prompt Construction
    prompt_content = _construct_forum_post_llm_prompt(post_data, max_comments_to_process)

    try:
        # LLM Interaction
        response = openai.ChatCompletion.create(
            model=llm_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant designed to analyze forum discussions and output a structured JSON response. Ensure your output is only the JSON structure requested, with no additional text before or after it."},
                {"role": "user", "content": prompt_content}
            ],
            temperature=0.5, 
            max_tokens=2000 # Increased to ensure space for detailed JSON and summary of input
        )
        
        llm_response_content = response.choices[0].message['content'].strip()

        # Response Parsing
        try:
            if llm_response_content.startswith("```json"):
                llm_response_content = llm_response_content[len("```json"):].strip()
                if llm_response_content.endswith("```"):
                    llm_response_content = llm_response_content[:-len("```")].strip()
            
            parsed_response = json.loads(llm_response_content)
            
            # Augment with timestamp
            parsed_response['nlp_analysis_timestamp_utc'] = datetime.now(timezone.utc).isoformat()
            
            # Ensure original post ID and subreddit are in the response, as requested from LLM.
            # If LLM somehow missed them, this is a fallback (though ideally prompt ensures it).
            if "source_post_id" not in parsed_response and post_data.get("id"):
                parsed_response["source_post_id"] = post_data["id"]
            if "analyzed_subreddit" not in parsed_response and post_data.get("subreddit_name_prefixed"):
                 parsed_response["analyzed_subreddit"] = post_data["subreddit_name_prefixed"]

            return parsed_response
            
        except json.JSONDecodeError as je:
            error_msg = f"Failed to parse LLM response into JSON. JSONDecodeError: {str(je)}"
            print(f"[LLM_FORUM_ANALYZE_ERROR] {error_msg}\nRaw response snippet (first 500 chars):\n{llm_response_content[:500]}")
            return {"error": "Failed to parse LLM response", "details": str(je), "raw_response": llm_response_content}

    except openai.error.AuthenticationError as e:
        print(f"[LLM_FORUM_ANALYZE_ERROR] OpenAI API AuthenticationError: {e}")
        return {"error": "OpenAI API authentication failed", "details": str(e)}
    except openai.error.RateLimitError as e:
        print(f"[LLM_FORUM_ANALYZE_ERROR] OpenAI API RateLimitError: {e}")
        return {"error": "OpenAI API rate limit exceeded", "details": str(e)}
    # ... other specific OpenAI errors from llm_integration_module can be added here ...
    except openai.error.APIError as e: # General API error from OpenAI
        print(f"[LLM_FORUM_ANALYZE_ERROR] OpenAI API APIError: {e}")
        return {"error": "Generic OpenAI API error occurred", "details": str(e)}
    except Exception as e: # Catch any other unexpected errors
        print(f"[LLM_FORUM_ANALYZE_ERROR] An unexpected error occurred: {type(e).__name__} - {e}")
        return {"error": "An unexpected error occurred", "details": str(e)}

# No main execution block as this is a library module.
```
