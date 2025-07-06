# Article Analyzer

### AI-Powered Web Content Categorization & Analysis

A Python-based web scraping and content classification tool using **Google Gemini AI**. It scrapes JavaScript-rendered pages, extracts main content, classifies websites, identifies content categories, and associates internal links with each category using both AI and heuristic logic.

---

## Features

* **Automated Web Scraping**: Uses [Playwright](https://playwright.dev/python/) to scrape JavaScript-heavy pages.
* **AI-Powered Content Analysis**: Utilizes **Google Gemini 2.0 Flash** via LangChain to categorize content and classify website type.
* **Heuristic Fallbacks**: Extracts meaningful content snippets and links using semantic tags like `<h1>`, `<article>`, etc.
* **Rate Limiting + Exponential Backoff**: Avoids API quota exhaustion gracefully.
* **Batch URL Processing**: Scrape and analyze multiple URLs from a file or predefined list.
* **Robust Output Format**: Returns structured JSON output per URL for further use.

---

## Installation

### 1. Clone & Setup

```bash
git clone https://github.com/your-username/article-analyzer.git
cd article-analyzer
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**`requirements.txt`**

```
# Web scraping and browser automation
playwright>=1.40.0

# HTML parsing
beautifulsoup4>=4.12.0
lxml>=4.9.0

# Async HTTP requests
aiohttp>=3.9.0

# Environment variable management
python-dotenv>=1.0.0

# LangChain and Gemini integration
langchain>=0.1.0
langchain-google-genai>=1.0.0

# Logging and utilities (optional but recommended)
tqdm>=4.66.0

```

### 3. Install Playwright Browsers

```bash
playwright install chromium
```

---

## Environment Setup

Create a `.env` file in your project root:

```bash
touch .env
```

Add your Gemini API key:

```env
GEMINI_API_KEY=your_actual_api_key_here
```

---

## Usage

### 🔹 Default Mode (Predefined URLs)

```bash
python article_analyzer.py
```

### 🔹 Custom URLs from File

```bash
python article_analyzer.py --file urls.txt
```

### 🔹 Advanced Usage

```bash
python article_analyzer.py --file urls.txt --output results.json --rate 3
```

---

## 📟 Command Line Arguments

| Flag             | Description                                     |
| ---------------- | ----------------------------------------------- |
| `--file`, `-f`   | File containing URLs to analyze                 |
| `--output`, `-o` | Output JSON file name (default: `results.json`) |
| `--rate`         | Max API requests per minute (default: `5`)      |

---

## 📂 Output Structure

### Terminal Output Example

```
2025-07-06 13:09:57,141 - INFO - Starting analysis of 10 URLs...
2025-07-06 13:09:57,141 - INFO - Processing URL 1/10: https://example.com
2025-07-06 13:10:00,042 - INFO - [LLM CALL][Categories] Attempt 1
2025-07-06 13:10:04,837 - INFO - [LLM CALL][SiteType] Attempt 1

...
================================================================================
ANALYSIS RESULTS
================================================================================
[
  {
    "URL": "https://www.example.com/news",
    "site_type": "news",
    "extracted_web_content": "...",
    "content": [
      {
        "Blog/News/Press Release": {
          "links": ["https://www.example.com/news/world"],
          "text": "Latest headlines and news updates from BBC..."
        }
      }
    ],
    "errors": null
  }
]
```

---

## Categories Detected

The analyzer can detect and extract content for the following predefined categories:

* About Us
* Products & Services
* Leadership/Team
* Blog/News/Press Release
* Contact/Support
* Privacy/Legal
* Careers/Jobs
* Other

---

## Site Type Classification

* `educational`
* `medical/health`
* `research/academic`
* `news`
* `blog`
* `e-commerce`
* `government`
* `social media`
* `forum`
* `portfolio`
* `non-profit`

---

## How It Works

### Content Extraction

* Parses JavaScript-rendered HTML with **Playwright**
* Filters out boilerplate: `script`, `style`, `nav`, `footer`, etc.
* Looks for `main`, `article`, and `div.post-content` for content fallback
* Trims content to first 10,000 characters
* Stores as `extracted_web_content`

### Link Extraction

* Extracts all `<a>` tags from DOM
* Resolves all relative links to absolute URLs
* Filters internal links based on base domain
* Matches links to categories using anchor text and `href` heuristics

### AI Integration

* Sends first 3000 characters to **Gemini AI** for:

  * Category classification
  * Site type detection
* Uses robust regex + JSON validation to parse AI response
* Fallback logic & retries with exponential backoff if AI fails

---

## Cost Considerations


### Gemini AI Pricing Guide for Web Content Analyzer

#### What Does the Project Use?
Project makes **2 API calls per URL**:
- **Category Identification (LLM)**: ~3000 tokens input, ~100 tokens output.
- **Site Type Detection (LLM)**: ~3000 tokens input, ~50 tokens output.

Each call:
- **Input** ≈ 3000 tokens
- **Output** ≈ 50–100 tokens  
**Total per URL ≈ 6,100–6,200 tokens**

---

## Price Reference Table From Gemini pricing 

| Resource Type             | Free Tier                          | Paid Tier (per 1M tokens)     |
|---------------------------|------------------------------------|-------------------------------|
| Input (text)              | Free of charge                     | $0.10                         |
| Output (text)             | Free of charge                     | $0.40                         |
| Context caching (text)    | Free for 1M/hr                     | $0.025                        |
| Image generation          | Free                               | $0.039 / image                |
| Tuning                    | Not available                      | Not available                 |
| Grounding w/ Google Search| 500 RPD (requests/day) free        | $35 / 1,000 requests          |
| Live API (Text I/O)       | Free                               | $0.35 (input) / $1.50 (output)|

---

## Cost Estimation: Per URL

| Metric                    | Value             |
|--------------------------|-------------------|
| Input tokens per URL     | ~6,000 tokens     |
| Output tokens per URL    | ~150 tokens       |
| **Total tokens per URL** | **~6,150 tokens** |

---

##  Free Tier

- Free up to **1,500 requests/day**
- Enough for **750 URLs/day**
- **Total Cost: $0**

---

##  Paid Tier Calculation

Per 1M tokens:
- **Input**: $0.10
- **Output**: $0.40

### Example Breakdown (approx. per URL):

| URL Count   | Input Tokens | Output Tokens | Total Tokens | Approx. Cost (USD)                 |
|-------------|--------------|----------------|--------------|------------------------------------|
| 100 URLs    | 600,000      | 15,000         | 615,000      | $0.10 × 0.6M + $0.40 × 0.015M = ~$0.09 |
| 1,000 URLs  | 6,000,000    | 150,000        | 6,150,000    | ≈ $0.90                            |
| 10,000 URLs | 60M + 1.5M   | 61.5M tokens   |              | ≈ $9.15                            |
| 100,000 URLs| 615M tokens  |                |              | ≈ $91.50                           |

**Average Paid Cost Per URL ≈ $0.0091**

---



## Summary Table

| URLs Processed | Free Tier (API only) | Paid Estimate (USD) |
|----------------|----------------------|----------------------|
| 100            |    Free              | ~$0.09              |
| 500            |    Free              | ~$0.45              |
| 750            |    Free              | ~$0.68              |
| 1000           |    Exceeds Free      | ~$0.90              |
| 5000           |    Exceeds Free      | ~$4.50              |
| 10000          |    Exceeds Free      | ~$9.15              |
"""


Tip: Use `--rate` to manage usage efficiently.

---

## Troubleshooting

| Issue                      | Solution                                                  |
| -------------------------- | --------------------------------------------------------- |
| `GEMINI_API_KEY not found` | Create a `.env` file with correct key                     |
| Playwright errors          | Run `playwright install` or `playwright install chromium` |
| LLM quota exceeded         | Use backoff & reduce `--rate` to avoid throttling         |
| No content extracted       | Ensure page loads fully and uses standard HTML layout     |

---

