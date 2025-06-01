
# DocAnalyzerOllama

DocAnalyzerOllama is a Python tool that extracts a documentation article from a given URL, analyzes its content using the Ollama local LLM (`qwen2.5:0.5b`), and provides actionable suggestions to improve readability, structure, completeness, and adherence to style guidelines. It can also generate a revised version of the article based on those suggestions.



## Usage

1. Update the url variable in `doc_analyzer.py` to the documentation article you want to analyze.

2. Run the script:

```javascript
python doc_analyzer.py

```
3. When the browser opens, manually solve the CAPTCHA if prompted.

4. The script will display the original article preview, analysis JSON, and a revised article based on suggestions.

## Notes

- This script requires Ollama's local model server (qwen2.5:0.5b) and the ollama CLI installed and configured.

- The Playwright browser is launched in non-headless mode so you can solve any CAPTCHA.

- The analysis JSON is extracted from model output that may contain explanatory text or markdown.


## License

[MIT](https://choosealicense.com/licenses/mit/)

