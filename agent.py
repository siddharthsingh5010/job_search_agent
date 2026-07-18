# Generals
import os
import sys
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
    url = f"https://www.linkedin.com/jobs/search?keywords={role_fixed}&location={region_fixed}&f_TPR=r86400"
    extract_result = tavily_extract_client.invoke({'urls':[url]})
    logger.info(f"EXTRACTED RESULTS FROM URL: \n {extract_result}")

    # Limiting Content to Avoid Model Out of Token Error
    extract_result = str(extract_result)[:20000]

    # Extract Links from Jobs 
    logger.info("Extracting Links from Jobs")
    update_status("Extracting Links from Jobs")
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
    logger.info("Extracting JD from each link")
    update_status("Extracting JD from each link")

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
    logger.info("Checking for Visa Sponserships Jobs")
    update_status("Checking for Visa Sponserships Jobs")
    llm1 = ChatOpenAI()
    visa_sponsored_jobs = {}
    no_visa_sponsored_jobs = {}
    # Store intermediate results for the judge pass
    classified_jobs = []
    for row in extracted_jds:
        link = row['url']
        title = row['title']
        jd = row['raw_content']
        response = llm1.invoke(f"""You are provided with a Job Description of a role. You need to go through the JD and look for if the company
    provide Visa sponsorship or Visa Support for the role. If Job Description is not in English then translate it to English first and look for the information.
    
    STRICT RULES : visa_sponsorship :
    1. if company has mentioned that they can/would provide visa sponsorship for the candidate 
    2. if company has mentioned that they can help with visa for candidate
    3. if company has mentioned that they can help candidate with work rights 
    4. Only and Only if Visa Sponsorship is mentioned in the Job Description
    then only the visa flag will be visa_sponsorship

    Examples of Visa Sponsorhips -
    1. We are providing Visa Sponsorship for this role to eligible candidates
    2. Visa Sponsorship is available 
    3. Visa Sponsorship is available for this role for eligible candidates
    4. We can help with Visa Sponsorship for this role for eligible candidates

    STRICT RULES : no_visa_sponsorship rules :
    1. if company has not mentioned anything on visa sponsorship in job description
    2. if company has specifically mentioned that candidate need to have right work permits for this role
    3. if company has mentioned that they can't help with visa or work permits
    4. if company has mentioned that they won't be able to provide visa sponsorship
    5. if the role is remote and don't have mention of visa sponsorship or work rights
    then visa flag will be no_visa_sponsorship.

    Examples of No Visa Sponsorship -
    1. Candidate must have right to work in UK
    2. Work permit sponsorship is not provided
    3. We are not able to provide Visa Sponsorship
    4. This role is remote and we are not able to provide Visa Sponsorship
    5. This role is remote and we are not able to help with work permits
    6. We are looking for a talented Researcher in Mathematics, Computational Science, and Data Science to join our Research & Development team.
    7. Based in the Netherlands with eligibility to work in the EU.

    Below is the job description {jd}
    OUTPUT FORMAT:
    {{
        "visa_flag" : visa flag indentified from JD
        "reference_paragraph" : reference paragraph from where you got the visa information. Make sure you correctly pick up the visa information.
        "confidence_score" : confidence score out of 100 on visa flag information.
    }}
    """)
        res = response.content
        logger.info(f"LINK : {link} \nTITLE : {title} \nRESPONSE:{res}")
        res = json.loads(res)
        visa_flag = res['visa_flag']
        reference_paragraph = res.get('reference_paragraph', '')
        classified_jobs.append({
            'title': title,
            'link': link,
            'visa_flag': visa_flag,
            'reference_paragraph': reference_paragraph,
        })
    
    # LLM As Judge — verify the visa_flag against the reference_paragraph and correct if needed
    logger.info("Running LLM-as-Judge to verify visa flag classifications")
    update_status("Running LLM-as-Judge to verify classifications...")
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
            judge_res = json.loads(judge_response.content)
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
