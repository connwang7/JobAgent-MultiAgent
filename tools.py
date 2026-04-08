# define tools
import os
import asyncio
from dotenv import load_dotenv
from pydantic import Field
from langchain.tools import BaseTool, tool
from data_loader import load_resume, write_cover_letter_to_doc
from schemas import JobSearchInput
from utils import SerperClient,FireCrawlClient
import json

load_dotenv()


# Job search tools

@tool
def job_search(
    keywords: str,
    location_name: str = None,
    job_type: str = None,
    limit: int = 5,
    employment_type: str = None,
    listed_at=None,
    experience=None,
    distance=None,
) -> dict:  # type: ignore
    """
    Search for job postings based on specified criteria using Serper API. Returns detailed job listings.
    """
    try:
        # 构造搜索查询
        query = f"job {keywords}"
        if location_name:
            query += f" in {location_name}"
        if job_type:
            query += f" {job_type}"
        if employment_type:
            query += f" {employment_type}"
        if experience:
            query += f" {experience} experience"
            
        # 使用SerperClient进行搜索
        client = SerperClient()
        response = client.search(query, num_results=limit)
        
        # 解析搜索结果
        jobs = []
        items = response.get("items", [])
        
        for item in items:
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            
            # 提取公司名称（如果可能）
            company_name = ""
            if " at " in title:
                parts = title.split(" at ")
                if len(parts) >= 2:
                    company_name = parts[-1]
            
            job_info = {
                "job_title": title,
                "company_name": company_name,
                "job_location": location_name or "Not specified",
                "job_desc_text": snippet,
                "apply_link": link,
                "time_posted": item.get("date", "Not specified"),
            }
            
            jobs.append(job_info)
            
        return jobs
    except Exception as e:
        print(f"搜索职位时出错: {e}")
        return {"error": f"搜索职位时出错: {str(e)}"}


class ResumeExtractorTool(BaseTool):
    name: str = "resume_extractor"
    description: str = "提取已上传的简历内容进行分析。不需要输入参数。"
    
    def _run(self, query: str = "") -> str:
        """提取简历内容"""
        try:
            resume_path = "temp/resume.pdf"
            
            if os.path.exists(resume_path):
                file_size = os.path.getsize(resume_path)
                if file_size == 0:
                    return "❌ 简历文件为空"
                resume_content = load_resume(resume_path)
                if resume_content and len(resume_content.strip()) > 10:
                    return resume_content
                else:
                    return "❌ 简历文件内容为空或读取失败"
            else:
                return "❌ 未找到简历文件"
                    
        except Exception as e:
            return f"❌ 读取简历时出错: {str(e)}"
    
    async def _arun(self, query: str = "") -> str:
        return self._run(query)

# Cover Letter Generation Tool
@tool
def generate_letter_for_specific_job(resume_details: str, job_details: str) -> dict:
    """
    Generate a tailored cover letter using the provided CV and job details. This function constructs the letter as plain text.
    returns: A dictionary containing the job and resume details for generating the cover letter.
    """
    return {"job_details": job_details, "resume_details": resume_details}


@tool
def save_cover_letter_for_specific_job(
    cover_letter_content: str, company_name: str
) -> str:
    """
    Returns a download link for the generated cover letter.
    Params:
    cover_letter_content: The combine information of resume and job details to tailor the cover letter.
    """
    filename = f"temp/{company_name}_cover_letter.docx"
    file = write_cover_letter_to_doc(cover_letter_content, filename)
    abs_path = os.path.abspath(file)
    return f"Here is the download link: {abs_path}"


# Web Search Tools
@tool("google_search")
def get_google_search_results(
    query: str = Field(..., description="Search query for web")
) -> str:
    """
    search the web for the given query and return the search results.
    """
    response = SerperClient().search(query)
    items = response.get("items")
    string = []
    for result in items:
        try:
            string.append(
                "\n".join(
                    [
                        f"Title: {result['title']}",
                        f"Link: {result['link']}",
                        f"Snippet: {result['snippet']}",
                        "---",
                    ]
                )
            )
        except KeyError:
            continue

    content = "\n".join(string)
    return content


@tool("scrape_website")
def scrape_website(url: str = Field(..., description="Url to be scraped")) -> str:
    """
    Scrape the content of a website and return the text.
    """
    try:
        content = FireCrawlClient().scrape(url)
    except Exception as exc:
        return f"Failed to scrape {url}"
    return content