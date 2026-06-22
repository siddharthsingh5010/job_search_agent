# Generals
import os
import sys
import time
from dotenv import load_dotenv
# Load .env file
load_dotenv()

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
    print(f"Searching for {job_role} jobs in {region}")

    # Implementation of the tool to extract linkedin jobs
    role_fixed = job_role.replace(" ","%20")
    region_fixed = region.replace(" ","%20")
    url = f"https://www.linkedin.com/jobs/search?keywords={role_fixed}&location={region_fixed}&f_TPR=r86400"
    extract_result = tavily_extract_client.invoke({'urls':[url]})
    logger.info(extract_result)

    # Limiting Content to Avoid Model Out of Token Error
    extract_result = str(extract_result)[:30000]

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
    logger.info(list_links)

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
    logger.info(extracted_jds)

    # Check for Visa Sponserships 
    logger.info("Checking for Visa Sponserships Jobs")
    update_status("Checking for Visa Sponserships Jobs")
    llm1 = ChatOpenAI()
    links = response.content
    visa_sponsored_jobs = {}
    no_visa_sponsored_jobs = {}
    for row in extracted_jds:
        link = row['url']
        title = row['title']
        jd = row['raw_content']
        response = llm1.invoke(f"""You are provided with a Job Description of a role. You need to go through the JD and look for if the company
    provide visa sponsorship or hiring international talent etc. If Job Description is not in English then translate it to English first and look for the information.
    
    STRICT RULES : visa_sponsorship :
    1. if company has mentioned that they can/would provide visa sponsorship for the candidate 
    2. if company has mentioned that they can help with visa for candidate
    3. if company has mentioned that they welcome international candidates and can provide visa 
    4. if company has mentioned that they can help candidate with work rights 
    5. Only and Only if Visa Sponsorship is mentioned in the Job Description
    then only the visa flag will be visa_sponsorship

    STRICT RULES : no_visa_sponsorship rules :
    1. if company has not mentioned anything on visa sponsorship in job description
    2. if company has specifically mentioned that candidate need to have right work permits for this role
    3. if company has mentioned that they can't help with visa or work permits
    4. if company has mentioned that they won't be able to provide visa sponsorship
    5. if the role is remote and don't have mention of visa sponsorship or work rights
    then visa flag will be no_visa_sponsorship.

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
        if visa_flag=='visa_sponsorship':
            visa_sponsored_jobs[title]= link
        else:
            no_visa_sponsored_jobs[title]= link
    

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


def invoke(user_input):

    global STATUS_LOG
    STATUS_LOG = []

    response = agent.invoke(
        {"messages": HumanMessage(content=user_input)}
    )

    messages = response["messages"]

    final_ai_response = next(
        msg.content
        for msg in reversed(messages)
        if isinstance(msg, AIMessage)
    )

    return {
        "answer": final_ai_response,
        "status": STATUS_LOG
    }


if __name__=="__main__":
    main()
