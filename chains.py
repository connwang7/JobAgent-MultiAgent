from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models.chat_models import BaseChatModel
from members import get_team_members_details
from prompts import get_supervisor_prompt_template, get_finish_step_prompt


def get_supervisor_chain(llm: BaseChatModel):
    """
    简化的 supervisor chain，直接返回文本结果
    """
    team_members = get_team_members_details()

    # 格式化成员信息
    formatted_string = ""
    for i, member in enumerate(team_members):
        formatted_string += f"**{i+1} {member['name']}**\nRole: {member['description']}\n\n"

    formatted_members_string = formatted_string.strip()
    system_prompt = get_supervisor_prompt_template()
    options = [member["name"] for member in team_members]

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
        (
            "system",
            f"""
            Given the conversation above, who should act next?
            Select EXACTLY ONE of: {options}
            
            Rules:
            - For resume analysis: ResumeAnalyzer
            - For job search: JobSearcher  
            - For cover letter: CoverLetterGenerator
            - For web research: WebResearcher
            - For general chat: ChatBot
            - When done: Finish
            
            Respond with ONLY the agent name, nothing else.
            """,
        ),
    ]).partial(options=str(options), members=formatted_members_string)

    return prompt | llm


def get_finish_chain(llm: BaseChatModel):
    """
    完成对话的链
    """
    system_prompt = get_finish_step_prompt()
    prompt = ChatPromptTemplate.from_messages([
        MessagesPlaceholder(variable_name="messages"),
        ("system", system_prompt),
    ])
    return prompt | llm