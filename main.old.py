# Generals
import os
import sys
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


# Tools
# @tool
# def search(query: str) -> str:
#     """
#     Tool that searches over internet
#     Args:
#         query: The query to search for
#     Returns:
#         The search result
#     """
#     print(f"Searching for {query}")
#     search_result = tavily_client.invoke(query)
#     return search_result

@tool
def get_jobs_linkedin(job_role:str, region: str)-> str:
    """
    Tool that gets the latest jobs posted on linkedin for a specific role and region. 
    It uses Tavily extract to extract the content and return the extracted content which have 
    titles of jobs, jobs links etc.
    
    Args:
        job_role : Job role user looking for
        region : Region in which user looking for
    Returns:
        The search result
    """
    print(f"Searching for {job_role} jobs in {region}")
    # Implementation of the tool to extract linkedin jobs
    role_fixed = job_role.replace(" ","%20")
    region_fixed = region.replace(" ","%20")
    url = f"https://www.linkedin.com/jobs/search?keywords={role_fixed}&location={region_fixed}&f_TPR=r86400"
    extract_result = tavily_extract_client.invoke({'urls':[url]})
    # with open("extract.txt","w") as f:
    #     f.write(str(extract_result))
    return str(extract_result)

@tool
def get_links_from_jobs_extract(extract_result: str)-> str:
    """
    Tool that extracts the links of jobs from the extracted result.
    It resturns only the links in a comma seperated list format that can be further extracted using a tool to get Job Description.
    
    Args:
        extract_result : The extracted result from the tool get_jobs_linkedin
    Returns:
        The list of links
    """
    # Implementation of the tool to extract links from the extracted result
    print(f"Extracting links from extract result")
    llm1 = ChatOpenAI()
    response = llm1.invoke(f"""You are provided with an extracted content. You need to return the links of jobs found in this
    extracted result. Return all the linkds found in comma separted str. Don't miss any part of link.
    Output format : 'Link1','Link2','Link3' . Below is the extracted content {extract_result}""")
    links = response.content
    return links

# Model
llm= ChatOpenAI()
tools = [get_jobs_linkedin,get_links_from_jobs_extract]
agent = create_agent(model=llm, tools=tools)

# Tavily Client
tavily_search_client = TavilySearch()
tavily_extract_client = TavilyExtract(extract_depth="advanced", include_images=False,)

def main():
    response = agent.invoke({"messages":HumanMessage(content="Give me links of recent jobs posted for Data Scientist role in Netherlands on linkedin")})
    messages = response["messages"]
    final_ai_response = next(
        msg.content
        for msg in reversed(messages)
        if isinstance(msg, AIMessage)
    )
    print(final_ai_response)

if __name__=="__main__":
    main()


