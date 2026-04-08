import aiohttp
import os
import asyncio
import requests
from typing import List, Literal, Union, Optional
from bs4 import BeautifulSoup
from utils import SerperClient

employment_type_mapping = {
    "full-time": "F",
    "contract": "C",
    "part-time": "P",
    "temporary": "T",
    "internship": "I",
    "volunteer": "V",
    "other": "O",
}

experience_type_mapping = {
    "internship": "1",
    "entry-level": "2",
    "associate": "3",
    "mid-senior-level": "4",
    "director": "5",
    "executive": "6",
}

job_type_mapping = {
    "onsite": "1",
    "remote": "2",
    "hybrid": "3",
}




def search_jobs_with_serper(keywords: str, location_name: str = None, limit: int = 10):
    """
    使用Serper API搜索职位信息
    """
    try:
        # 构造搜索查询
        query = f"job {keywords}"
        if location_name:
            query += f" in {location_name}"
            
        # 使用SerperClient进行搜索
        client = SerperClient()
        response = client.search(query, num_results=limit)
        
        # 解析搜索结果
        jobs = []
        items = response.get("items", [])
        
        for item in items:
            # 尝试从搜索结果中提取职位相关信息
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            
            # 简单的职位信息提取逻辑
            job_info = {
                "job_title": title,
                "company_name": "",  # 需要从snippet或其他地方提取
                "job_location": location_name or "",
                "job_desc_text": snippet,
                "apply_link": link,
                "time_posted": "",  # 搜索结果中可能没有此信息
                "num_applicants": "",  # 搜索结果中可能没有此信息
            }
            
            # 尝试从标题或片段中提取公司名称
            if " at " in title:
                # 假设标题格式为 "Job Title at Company Name"
                parts = title.split(" at ")
                if len(parts) >= 2:
                    job_info["company_name"] = parts[-1]
                    
            jobs.append(job_info)
            
        return jobs
    except Exception as e:
        print(f"使用Serper搜索职位时出错: {e}")
        return []

def get_job_ids(
    keywords: str,
    location_name: str,
    employment_type: Optional[
        List[
            Literal[
                "full-time",
                "contract",
                "part-time",
                "temporary",
                "internship",
                "volunteer",
                "other",
            ]
        ]
    ] = None,
    limit: Optional[int] = 10,
    job_type: Optional[List[Literal["onsite", "remote", "hybrid"]]] = None,
    experience: Optional[
        List[
            Literal[
                "internship",
                "entry level",
                "associate",
                "mid-senior level",
                "director",
                "executive",
            ]
        ]
    ] = None,
    listed_at: Optional[Union[int, str]] = 86400,
    distance=None,
):
    # 直接使用Serper API进行职位搜索
    try:
        jobs = search_jobs_with_serper(keywords, location_name, limit)
        # 为兼容现有代码，返回空列表作为job_ids（因为Serper直接返回详细信息）
        return []
    except Exception as e:
        print(f"搜索职位时出错: {e}")
        return []


async def fetch_job_details(session, job_id):
    # Construct the URL for each job using the job ID
    job_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

    # Send a GET request to the job URL
    async with session.get(job_url) as response:
        job_soup = BeautifulSoup(await response.text(), "html.parser")

        # Create a dictionary to store job details
        job_post = {}

        # Try to extract and store the job title
        try:
            job_post["job_title"] = job_soup.find(
                "h2",
                {
                    "class": "top-card-layout__title font-sans text-lg papabear:text-xl font-bold leading-open text-color-text mb-0 topcard__title"
                },
            ).text.strip()
        except Exception as exc:
            job_post["job_title"] = ""

        try:
            job_post["job_location"] = job_soup.find(
                "span",
                {"class": "topcard__flavor topcard__flavor--bullet"},
            ).text.strip()
        except Exception as exc:
            job_post["job_location"] = ""

        # Try to extract and store the company name
        try:
            job_post["company_name"] = job_soup.find(
                "a", {"class": "topcard__org-name-link topcard__flavor--black-link"}
            ).text.strip()
        except Exception as exc:
            job_post["company_name"] = ""

        # Try to extract and store the time posted
        try:
            job_post["time_posted"] = job_soup.find(
                "span", {"class": "posted-time-ago__text topcard__flavor--metadata"}
            ).text.strip()
        except Exception as exc:
            job_post["time_posted"] = ""

        # Try to extract and store the number of applicants
        try:
            job_post["num_applicants"] = job_soup.find(
                "span",
                {
                    "class": "num-applicants__caption topcard__flavor--metadata topcard__flavor--bullet"
                },
            ).text.strip()
        except Exception as exc:
            job_post["num_applicants"] = ""

        # Try to extract and store the job description
        try:
            job_description = job_soup.find(
                "div", {"class": "decorated-job-posting__details"}
            ).text.strip()
            job_post["job_desc_text"] = job_description
        except Exception as exc:
            job_post["job_desc_text"] = ""

        try:
            # Try to extract and store the apply link
            apply_link_tag = job_soup.find("a", class_="topcard__link")
            if apply_link_tag:
                apply_link = apply_link_tag.get("href")
                job_post["apply_link"] = apply_link
        except Exception as exc:
            job_post["apply_link"] = ""

        return job_post


async def get_job_details_from_linkedin_api(job_id):
    try:
        api = Linkedin(os.getenv("LINKEDIN_EMAIL"), os.getenv("LINKEDIN_PASS"))
        job_data = await sync_to_async(api.get_job)(
            job_id
        )  # Assuming this function is async and fetches job data

        # Construct the job data dictionary with defaults
        job_data_dict = {
            "company_name": job_data.get("companyDetails", {})
            .get(
                "com.linkedin.voyager.deco.jobs.web.shared.WebCompactJobPostingCompany",
                {},
            )
            .get("companyResolutionResult", {})
            .get("name", ""),
            "company_url": job_data.get("companyDetails", {})
            .get(
                "com.linkedin.voyager.deco.jobs.web.shared.WebCompactJobPostingCompany",
                {},
            )
            .get("companyResolutionResult", {})
            .get("url", ""),
            "job_desc_text": job_data.get("description", {}).get("text", ""),
            "work_remote_allowed": job_data.get("workRemoteAllowed", ""),
            "job_title": job_data.get("title", ""),
            "company_apply_url": job_data.get("applyMethod", {})
            .get("com.linkedin.voyager.jobs.OffsiteApply", {})
            .get("companyApplyUrl", ""),
            "job_location": job_data.get("formattedLocation", ""),
        }
    except Exception as e:
        # Handle exceptions or errors in fetching or parsing the job data
        job_data_dict = {
            "company_name": "",
            "company_url": "",
            "job_desc_text": "",
            "work_remote_allowed": "",
            "job_title": "",
            "apply_link": "",
            "job_location": "",
        }

    return job_data_dict


async def fetch_all_jobs(job_ids, batch_size=5):
    # 由于我们直接使用Serper获取职位详情，这里直接返回空列表
    # 实际的职位信息将在工具调用中直接返回
    return []
