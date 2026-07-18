# 🤖 AI Powered Job Search Assistant

An intelligent job search assistant that scrapes LinkedIn for recent job postings, extracts job descriptions, and uses an LLM to identify which roles offer **visa sponsorship** — all through a custom-styled Streamlit UI.

---

## What It Does

1. Takes a natural language query (e.g. *"Give me visa sponsored Data Scientist jobs in Netherlands"*)
2. Searches LinkedIn for matching job postings using **Tavily Extract**
3. Extracts job description content from each posting
4. Uses **GPT-4o** to analyze each JD and classify it as `visa_sponsorship` or `no_visa_sponsorship`
5. Returns a categorized list of roles with direct links

---

## Project Structure

```
job_search_agent/
├── app.py              # Streamlit frontend — custom dark UI with live progress
├── agent.py            # LangChain agent, tools, and invoke logic
├── s3_connector.py     # AWS S3 helper — upload, download, rename, delete files
├── get_env.py          # Downloads .env file from S3 at startup
├── logger.py           # Logging setup
├── icon.png            # Profile/logo image shown in the UI
├── .streamlit/
│   └── config.toml     # Dark AI/data theme configuration
├── Dockerfile          # Container setup for deployment
├── requirements.txt
```

---

## Key Modules & Libraries

| Library | Purpose |
|---|---|
| `streamlit` | Web UI with custom CSS styling |
| `langchain` / `langgraph` | Agent orchestration and tool calling |
| `langchain-openai` | GPT-4o as the reasoning model |
| `langchain-tavily` | Web search and content extraction from LinkedIn |
| `boto3` | AWS SDK — used by `S3Connector` to manage `.env` and other files |
| `openai` | Underlying LLM API |
| `python-dotenv` | Loading API keys from `.env` |

---

## Setup

### 1. Clone the repo

```bash
git clone <repo-url>
cd job_search_agent
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API keys

You can either create a `.env` file manually or pull it from S3 using `get_env.py`.

**Option A — Manual**

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key
TAVILY_API_KEY=your_tavily_api_key
```

**Option B — Pull from S3**

If the `.env` is stored in an S3 bucket, run:

```bash
python get_env.py
```

This uses `S3Connector` to download the env file from the configured bucket (`siddharthsingh701`, `eu-west-1`). Make sure your AWS credentials are set up via environment variables or `~/.aws/credentials`.

- Get your OpenAI key at [platform.openai.com](https://platform.openai.com)
- Get your Tavily key at [tavily.com](https://tavily.com)

### 5. Run the app

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`

---

## Usage

1. Open the app in your browser
2. Type your job search query in the text box — e.g.:
   - *"Give me visa sponsored Data Scientist jobs in Netherlands"*
   - *"Find ML Engineer roles in Germany with visa sponsorship"*
3. Watch the live progress panel as the agent searches and processes listings
4. Review the final result with jobs split into **visa sponsored** and **non-visa sponsored**

---

## Docker

To run in a container:

```bash
docker build -t job-search-agent .
docker run -p 8502:8502 --env-file .env job-search-agent
```

App will be available at `http://localhost:8502/job-search-agent`

---

## Notes

- LinkedIn scraping depends on Tavily's extraction capability — results may vary based on LinkedIn's page structure
- GPT-4o is used for both link extraction and visa sponsorship classification
- Processing time scales with the number of job listings found (each JD is analyzed individually)
- The `.env` file is excluded from version control — use `get_env.py` to pull it from S3 in deployment environments
