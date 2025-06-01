import subprocess
import json
import re
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


def extract_article_with_playwright(url):
    """
    Uses Playwright to open the given URL, waits for the article content to load,
    and extracts the article title and body text after manual CAPTCHA solving if required.

    Args:
        url (str): URL of the documentation article to extract.

    Returns:
        tuple: (title (str), article_text (str)) or (None, None) if extraction failed.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("Opening browser. Please solve the CAPTCHA manually if prompted...")
        page.goto(url, timeout=60000)

        try:
            # Wait for article content selector to appear within 60 seconds
            page.wait_for_selector("div.article__body.markdown", timeout=60000)
        except Exception:
            print("Timeout waiting for article content. Try solving the CAPTCHA and re-run.")
            browser.close()
            return None, None

        # Get full HTML content of the page
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title else "No title found"
        article_div = soup.select_one("div.article__body.markdown")

        browser.close()

        if not article_div:
            raise Exception("Article content not found after CAPTCHA.")

        # Extract article text with line breaks separating paragraphs
        return title, article_div.get_text(separator="\n", strip=True)


def query_ollama(prompt):
    """
    Runs the Ollama CLI tool to query the qwen2.5:0.5b model with the provided prompt.
    
    Args:
        prompt (str): Text prompt to send to the model.
    
    Returns:
        str: Model's response output.
    
    Raises:
        Exception: If the Ollama command fails.
    """
    cmd = ['ollama', 'run', 'qwen2.5:0.5b']
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    stdout, stderr = proc.communicate(prompt)

    if proc.returncode != 0:
        raise Exception(f"Ollama error: {stderr.strip()}")

    return stdout.strip()


def extract_json(text):
    """
    Extracts the first JSON object found in a given text string.
    This helps to isolate JSON from explanatory text or markdown.

    Args:
        text (str): Text that contains a JSON object.

    Returns:
        str: JSON string extracted.

    Raises:
        ValueError: If no JSON object is found.
    """
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in text")
    return match.group(1)


def normalize_analysis_json(raw_json):
    """
    Normalizes the raw JSON from the analysis to ensure
    each key contains an 'assessment' and 'suggestions' list,
    adapting flat or nested formats for uniform access.

    Args:
        raw_json (dict): Raw JSON object from the model.

    Returns:
        dict: Normalized JSON with expected structure.
    """
    def wrap(key):
        return {
            "assessment": raw_json[key],
            "suggestions": [
                f"Improve {key} clarity",
                f"Use simpler structure for {key}"
            ]
        }

    if isinstance(raw_json.get("readability"), str):
        # Wrap string assessments into the expected nested format
        return {
            "readability": wrap("readability"),
            "structure": wrap("structure"),
            "completeness": wrap("completeness"),
            "style_guidelines": {
                "assessment": "Review",
                "suggestions": raw_json.get("style_guidelines", [])
            }
        }
    return raw_json


def build_analysis_prompt(title, article_text):
    """
    Constructs the prompt sent to the model to analyze the documentation.

    Args:
        title (str): Article title.
        article_text (str): Full text of the article.

    Returns:
        str: Prompt formatted as instruction for analysis.
    """
    return f"""
You are a documentation analyzer assistant.

Analyze the following documentation article and provide actionable suggestions based on:

1. Readability for a marketer (explain why it is or isn't readable).
2. Structure and flow (headings, paragraphs, lists, logical order).
3. Completeness of information and examples (are details and examples sufficient?).
4. Adherence to Microsoft Style Guide tips:
   - Use bigger ideas, fewer words.
   - Write like you speak.
   - Project friendliness with contractions.

Article Title: {title}

Article Content:
{article_text}

Provide your analysis as a JSON object with keys: readability, structure, completeness, style_guidelines.
Each key should have 'assessment' (string) and 'suggestions' (list of strings).
"""


def build_revision_prompt(article_text, suggestions):
    """
    Constructs the prompt for the model to revise the article
    based on provided suggestions.

    Args:
        article_text (str): Original article text.
        suggestions (dict): Suggestions extracted from analysis.

    Returns:
        str: Prompt formatted to request a revised article.
    """
    readability_suggestions = suggestions.get('readability', {}).get('suggestions', [])

    style_guidelines = suggestions.get('style_guidelines', [])
    if isinstance(style_guidelines, dict):
        style_suggestions = style_guidelines.get('suggestions', [])
    elif isinstance(style_guidelines, list):
        style_suggestions = style_guidelines
    else:
        style_suggestions = []

    combined_suggestions = readability_suggestions + style_suggestions
    suggestions_text = "\n- " + "\n- ".join(combined_suggestions) if combined_suggestions else "No suggestions provided."

    return f"""
You are a skilled technical writer assistant.

Here is an original documentation article:

{article_text}

Based on the following suggestions, please rewrite the article to improve readability and style while keeping the original meaning intact:

{suggestions_text}

Please output only the revised article text.
"""


if __name__ == "__main__":
    # URL of the documentation article to analyze
    url = "https://help.moengage.com/hc/en-us/articles/18060739634580-Understanding-Count-Differences-in-Behavior-and-Funnel-Analyses"
    
    title, article = extract_article_with_playwright(url)

    if title and article:
        print("Title:", title)
        print("\nArticle Preview:\n", article[:1000])

        print("\nSending article to Ollama for analysis...")
        analysis_response = query_ollama(build_analysis_prompt(title, article))

        try:
            json_str = extract_json(analysis_response)
            raw_analysis_json = json.loads(json_str)
            analysis_json = normalize_analysis_json(raw_analysis_json)

            print("\nAnalysis Result (parsed JSON):\n")
            print(json.dumps(analysis_json, indent=2))

            print("\nGenerating revised article based on readability and style suggestions...\n")
            revision_prompt = build_revision_prompt(article, analysis_json)
            revised_article = query_ollama(revision_prompt)

            print("\nRevised Article:\n")
            print(revised_article)

        except (json.JSONDecodeError, ValueError) as e:
            print("Failed to parse JSON from analysis response. Raw output:")
            print(analysis_response)
            print(f"Parsing error: {e}")
        except Exception as e:
            print(f"Error during processing: {e}")
