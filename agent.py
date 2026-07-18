# Generals
import os
import sys
import re
import time
import queue
import threading
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Global queue for streaming progress updates to the UI
_progress_queue: queue.Queue = None

def set_progress_queue(q: queue.Queue):
    """Call this before invoking the agent to wire up live progress."""
    global _progress_queue
    _progress_queue = q

def update_status(message: str):
    """Push a status message. Goes to the queue if set, otherwise just logs."""
    logger.info(message)
    if _progress_queue is not None:
        _progress_queue.put(message)

# LangChain
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_tavily.tavily_search import TavilySearch
from langchain_tavily.tavily_extract import TavilyExtract, TavilyExtractInput
from langgraph.graph import START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

# Other
from logger import logger
from typing import TypedDict, List, Dict
from urllib.parse import urlparse
import json

def is_valid(url):
    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)

@tool
def get_jobs_linkedin(job_role:str, region: str)-> str:
    """
    Tool that gets the latest visa sponsored jobs posted on linkedin for a specific role and region. 
    Don't execute this tool multiple times or in parallel.
    Args:
        job_role : Job role user looking for
        region : Region in which user looking for
    Returns:
        The search result
    """
    logger.info(f"Searching for {job_role} jobs in {region}")
    update_status(f"Searching for {job_role} jobs in {region}...")

    # Implementation of the tool to extract linkedin jobs
    role_fixed = job_role.replace(" ","%20")
    region_fixed = region.replace(" ","%20")
    url = f"https://www.linkedin.com/jobs/search?keywords={role_fixed}&location={region_fixed}&f_TPR=r43200"
    extract_result = tavily_extract_client.invoke({'urls':[url]})
    logger.info(f"EXTRACTED RESULTS FROM URL: \n {extract_result}")

    # Limiting Content to Avoid Model Out of Token Error
    extract_result = str(extract_result)[:20000]

    # Extract Links from Jobs 
    logger.info("Extracting LinkedIn links from posted jobs.")
    update_status("Extracting LinkedIn links from posted jobs.")
    llm1 = ChatOpenAI()
    response = llm1.invoke(f"""You are provided with an extracted content. You need to return the links of jobs found in this
    extracted result. Return all the linkds found in comma separted str. Don't miss any part of link. Also remove any training white spaces in starting or end
    Output format : Link1,Link2,Link3 . Below is the extracted content {extract_result}""")
    links = response.content
    try:
        list_links = links.split(',')
    except:
        logger.info(f'ERROR: Converting Links {links}')
    logger.info(f"EXTRACTED LINKS : \n {list_links}")

    # Fixing Links
    fixed_links = []
    for lnk in list_links:
        lnk = lnk.replace(" ","")
        lnk = lnk.replace(" ","")
        try:
            lnk = lnk.split("?")[0]
        except:
            pass
        fixed_links.append(lnk)

    logger.info(f"FIXED EXTRACTED LINKS : \n {fixed_links}")


    # Extract JD from each link
    logger.info("Extracting Job Descriptions from each posted job.")
    update_status("Extracting Job Descriptions from each posted job.")

    def chunk_list(lst, chunk_size=20):
        return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

    chunks = chunk_list(fixed_links, 20)
    extracted_jds = []
    for i, chunk in enumerate(chunks, 1):
        tavily_extract_client1 = TavilyExtract(extract_depth="basic", include_images=False)
        _jds = tavily_extract_client1.invoke({'urls':chunk})
        try:
            extracted_jds.extend(_jds['results'])
        except:
            logger.error("No JDS found")
    logger.info(f"ALL EXTRACTED JOB DESCRIPTIONS : \n {extracted_jds}")

    # Check for Visa Sponserships 
    logger.info("Checking for Visa Sponserships")
    update_status("Checking for Visa Sponserships")
    llm1 = ChatOpenAI()
    visa_sponsored_jobs = {}
    no_visa_sponsored_jobs = {}
    # Store intermediate results for the judge pass
    classified_jobs = []
    for row in extracted_jds:
        link = row['url']
        title = row['title']
        jd = row['raw_content']

        # Extract date posted directly from raw content via regex
        # LinkedIn embeds it as "X hours ago", "X days ago" etc. (English or Spanish)
        date_posted = "Unknown"
        date_patterns = [
            r'Hace\s+\d+\s+\w+',               # Spanish: "Hace 2 horas", "Hace 3 días"
            r'\d+\s+hours?\s+ago',              # English: "2 hours ago"
            r'\d+\s+days?\s+ago',               # English: "3 days ago"
            r'\d+\s+weeks?\s+ago',              # English: "1 week ago"
            r'\d+\s+months?\s+ago',             # English: "2 months ago"
            r'Hace\s+\d+\s+semanas?',           # Spanish: "Hace 1 semana"
            r'Hace\s+\d+\s+meses?',             # Spanish: "Hace 2 meses"
        ]
        for pattern in date_patterns:
            match = re.search(pattern, jd, re.IGNORECASE)
            if match:
                date_posted = match.group(0).strip()
                break

        response = llm1.invoke(f"""
You are an expert information extraction system.

Your task is to analyze a Job Description (JD) and determine ONLY from the text explicitly present in the JD whether the employer offers visa sponsorship or visa support.

If the Job Description is not in English, first translate it internally into English before performing the analysis.

IMPORTANT PRINCIPLE

Never infer visa sponsorship from company reputation, company size, international presence, relocation benefits, travel requirements, English language requirements, hiring country, or any other indirect clue.

Only classify based on explicit statements in the Job Description.

⸻

Classification Rules

There are only two possible outputs:

* "visa_sponsorship"
* "no_visa_sponsorship"

⸻

Rule 1 — visa_sponsorship

Return "visa_sponsorship" ONLY if the JD explicitly states that the employer provides any of the following:

* visa sponsorship
* work visa sponsorship
* visa support
* work permit sponsorship
* immigration sponsorship
* immigration support
* relocation with visa support
* assistance obtaining a work visa
* assistance obtaining a work permit
* sponsorship for eligible candidates
* sponsorship available
* company will sponsor visas
* company can provide visa sponsorship
* company supports international applicants through visa sponsorship

Examples:

* “Visa sponsorship is available.”
* “We sponsor work visas.”
* “Eligible candidates will receive visa sponsorship.”
* “We provide work permit sponsorship.”
* “Immigration support is available.”
* “Relocation package includes visa assistance.”

If and only if one of these (or an equivalent explicit statement) appears in the JD, classify as:

"visa_flag": "visa_sponsorship"

⸻

Rule 2 — no_visa_sponsorship

Return "no_visa_sponsorship" if ANY of the following is true:

A. No mention

The JD does not mention visa sponsorship, visa support, work permits, immigration support, or work authorization.

B. Existing work authorization required

Examples:

* Must have the right to work
* Must be legally authorized to work
* Must already have work authorization
* Candidates must possess valid work rights
* Eligibility to work in the EU
* Eligibility to work in the UK
* Right to work in Spain required
* Applicant must already be authorized to work

C. Explicit refusal

Examples:

* No visa sponsorship
* Sponsorship is unavailable
* We cannot sponsor visas
* Work permit sponsorship is not provided
* No immigration support
* Applicants requiring sponsorship cannot be considered

D. Remote jobs

If the JD is remote and contains no explicit visa sponsorship statement.

⸻

DO NOT INFER

The following DO NOT imply visa sponsorship:

* multinational company
* international company
* global company
* English language requirement
* relocation package
* relocation assistance
* travel within Europe
* travel internationally
* hybrid role
* remote role
* headquarters in another country
* company has offices worldwide
* aerospace company
* FAANG company
* large company
* company historically sponsors visas
* recruiter may sponsor
* company usually sponsors
* previous hiring history

None of these should ever result in "visa_sponsorship" unless the JD explicitly says so.

⸻

Confidence Score

Return a confidence score between 0 and 100.

Use the following guidance:

100
Explicit visa sponsorship statement.

95
Explicit statement that sponsorship is not provided.

90
Explicit requirement that candidate must already possess work authorization.

85
No visa-related information is mentioned anywhere in the JD.

Do not assign low confidence merely because sponsorship is absent.

⸻

Reference Paragraph

Return the exact paragraph or sentence from which the visa decision was made.

If the JD contains no visa-related text, return:

“No visa sponsorship or work authorization information found in the job description.”

⸻

Metadata Extraction

Extract:

* company_name
* location
Rules:

* If unavailable, return “Unknown”.
* Do not infer missing metadata.

⸻

Output

Return ONLY valid JSON.

{{
  "visa_flag": "visa_sponsorship",
  "reference_paragraph": "Exact sentence or 'No visa sponsorship or work authorization information found in the job description.'",
  "confidence_score": 100,
  "company_name": "Company name or Unknown",
  "location": "City, Country or Unknown"
}}

Job Description:

{jd}
    """)
        res = response.content
        logger.info(f"LINK : {link} \nTITLE : {title} \nRESPONSE:{res}")
        # Strip markdown code fences if the LLM wraps the JSON in ```json ... ```
        res_clean = res.strip()
        if res_clean.startswith("```"):
            res_clean = re.sub(r"^```(?:json)?\s*", "", res_clean)
            res_clean = re.sub(r"\s*```$", "", res_clean).strip()
        try:
            res_parsed = json.loads(res_clean)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM JSON for {title}: {e} | raw: {res}")
            classified_jobs.append({
                'title': title,
                'link': link,
                'visa_flag': 'no_visa_sponsorship',
                'reference_paragraph': '',
                'company_name': 'Unknown',
                'location': 'Unknown',
                'date_posted': 'Unknown',
            })
            continue
        visa_flag = res_parsed.get('visa_flag', 'no_visa_sponsorship')
        reference_paragraph = res_parsed.get('reference_paragraph', '')
        classified_jobs.append({
            'title': title,
            'link': link,
            'visa_flag': visa_flag,
            'reference_paragraph': reference_paragraph,
            'company_name': res_parsed.get('company_name', 'Unknown'),
            'location': res_parsed.get('location', 'Unknown'),
            'date_posted': date_posted,  # extracted via regex, not LLM
        })
    
    # LLM As Judge — verify the visa_flag against the reference_paragraph and correct if needed
    logger.info("Verifying visa flag classifications.")
    update_status("Verifying visa flag classifications.")
    llm_judge = ChatOpenAI(model="gpt-4o")
    for job in classified_jobs:
        judge_response = llm_judge.invoke(f"""You are a strict visa sponsorship classification judge.

You will be given:
- A visa_flag classification: either "visa_sponsorship" or "no_visa_sponsorship"
- A reference_paragraph extracted from a job description that was used to make that classification

Your task:
1. Read the reference_paragraph carefully
2. Decide if the visa_flag is CORRECT or INCORRECT based solely on the reference_paragraph
3. If incorrect, provide the corrected visa_flag

RULES for visa_sponsorship:
- The paragraph must explicitly mention visa sponsorship, visa support, or help with work permits/relocation visas
- Vague statements about "welcoming international candidates" without visa support do NOT count
- Only classify as visa_sponsorship if it is clearly and explicitly stated

RULES for no_visa_sponsorship:
- If the paragraph mentions right-to-work requirements, no sponsorship available, or says nothing about visa support
- If the reference_paragraph is empty or irrelevant, default to no_visa_sponsorship

visa_flag: {job['visa_flag']}
reference_paragraph: {job['reference_paragraph']}

OUTPUT FORMAT (JSON only, no extra text):
{{
    "original_flag": "{job['visa_flag']}",
    "corrected_flag": "visa_sponsorship or no_visa_sponsorship",
    "is_correct": true or false,
    "judge_reasoning": "brief explanation"
}}
""")
        try:
            judge_raw = judge_response.content.strip()
            if judge_raw.startswith("```"):
                judge_raw = re.sub(r"^```(?:json)?\s*", "", judge_raw)
                judge_raw = re.sub(r"\s*```$", "", judge_raw).strip()
            judge_res = json.loads(judge_raw)
            corrected_flag = judge_res.get('corrected_flag', job['visa_flag'])
            is_correct = judge_res.get('is_correct', True)
            logger.info(
                f"JUDGE — Title: {job['title']} | Original: {job['visa_flag']} | "
                f"Corrected: {corrected_flag} | Match: {is_correct} | "
                f"Reason: {judge_res.get('judge_reasoning', '')}"
            )
            if not is_correct:
                update_status(f"Judge corrected '{job['title']}': {job['visa_flag']} → {corrected_flag}")
            job['visa_flag'] = corrected_flag
        except Exception as e:
            logger.error(f"Judge parsing failed for {job['title']}: {e}")

    # Build final dicts from judge-verified results
    for job in classified_jobs:
        if job['visa_flag'] == 'visa_sponsorship':
            visa_sponsored_jobs[job['title']] = job['link']
        else:
            no_visa_sponsored_jobs[job['title']] = job['link']
    
    # Return the list of visa sponsored jobs
    logger.info(f"VISA_SPONSORED: {visa_sponsored_jobs}")
    logger.info(f"NO_VISA_SPONSORED: {no_visa_sponsored_jobs}")
    final_result = f"Below are VISA Sponsored Jobs : {visa_sponsored_jobs}. And these are Non Visa Sponsored Jobs : {no_visa_sponsored_jobs}"
    update_status("Finished")

    # Push structured jobs data to the progress queue so the UI can render the table
    if _progress_queue is not None:
        _progress_queue.put({"__jobs_data__": classified_jobs})

    return final_result

# Model
llm= ChatOpenAI(model="gpt-4o")
tools = [get_jobs_linkedin]
agent = create_agent(model=llm, tools=tools)

# Tavily Client
tavily_search_client = TavilySearch()
tavily_extract_client = TavilyExtract(extract_depth="advanced", include_images=False,)

def main():
    response = agent.invoke({"messages":HumanMessage(content="Give me links of recent jobs posted for Data Scientist role in London on linkedin which provide visa sponsorship")})
    messages = response["messages"]
    final_ai_response = next(
        msg.content
        for msg in reversed(messages)
        if isinstance(msg, AIMessage)
    )
    print(final_ai_response)


def invoke(user_input, progress_queue: queue.Queue = None):
    """
    Run the agent. If progress_queue is provided, status updates from tools
    are pushed into it live. The queue receives None as a sentinel when done.
    """
    set_progress_queue(progress_queue)

    result_container = {}

    def _run():
        response = agent.invoke(
            {"messages": HumanMessage(content=user_input)}
        )
        messages = response["messages"]
        final_ai_response = next(
            msg.content
            for msg in reversed(messages)
            if isinstance(msg, AIMessage)
        )
        result_container["answer"] = final_ai_response

    thread = threading.Thread(target=_run)
    thread.start()
    thread.join()

    # Signal the UI that we're done
    if progress_queue is not None:
        progress_queue.put(None)

    return result_container.get("answer", "")


if __name__=="__main__":
    main()
