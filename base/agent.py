import re
from datetime import datetime

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, create_react_agent
from langgraph.types import interrupt
import os
from dotenv import load_dotenv

from langchain_deepseek import ChatDeepSeek

from base.db import get_user_profile, update_user_profile
from base.send_email import send_email

load_dotenv()


def get_date():
    return datetime.now().strftime("%d-%m-%Y")


def get_deepseek_model():
    """Get the DeepSeek model."""
    return ChatDeepSeek(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        model_name="deepseek-flash",
    )


@tool
def get_candidate_details(config: RunnableConfig) -> dict:
    """Gets the candidate's contact and job details: name, email, GitHub, LinkedIn,
    current salary, expected salary and last working day (LWD).

    Takes no arguments. Call it when you need these details for the email; a value
    of null means the candidate hasn't provided it, so leave it out.
    """
    user_id = config.get("configurable", {}).get("user_id")
    profile = get_user_profile(user_id) if user_id else None
    if not profile:
        return {"error": "Candidate details not found."}
    lwd = profile.get("last_working_day")
    return {
        "name": profile.get("name"),
        "email": profile.get("email"),
        "github_url": profile.get("github_url"),
        "linkedin_url": profile.get("linkedin_url"),
        "current_salary": profile.get("current_salary"),
        "expected_salary": profile.get("expected_salary"),
        "last_working_day": datetime.strptime(lwd, "%Y-%m-%d").strftime("%d-%m-%Y") if lwd else None,
    }


@tool
def update_candidate_details(
    config: RunnableConfig,
    github_url: str | None = None,
    linkedin_url: str | None = None,
    current_salary: float | None = None,
    expected_salary: float | None = None,
    last_working_day: str | None = None,
) -> str:
    """Updates the candidate's saved details. Only pass the fields the candidate
    asked to change; omitted fields keep their current value.

    Args:
        github_url: New GitHub profile URL.
        linkedin_url: New LinkedIn profile URL.
        current_salary: New current salary as a number.
        expected_salary: New expected salary as a number.
        last_working_day: New last working day (LWD) as a date in DD-MM-YYYY format.
    """
    user_id = config.get("configurable", {}).get("user_id")
    profile = get_user_profile(user_id) if user_id else None
    if not profile:
        return "Candidate details not found."

    changes = {
        "github_url": github_url,
        "linkedin_url": linkedin_url,
        "current_salary": current_salary,
        "expected_salary": expected_salary,
        "last_working_day": last_working_day,
    }
    changes = {k: v for k, v in changes.items() if v is not None}
    if not changes:
        return "No changes provided."
    if "last_working_day" in changes:
        try:
            changes["last_working_day"] = (
                datetime.strptime(changes["last_working_day"], "%d-%m-%Y").date().isoformat()
            )
        except ValueError:
            return "last_working_day must be in DD-MM-YYYY format."

    merged = {
        "github_url": profile.get("github_url"),
        "linkedin_url": profile.get("linkedin_url"),
        "current_salary": profile.get("current_salary"),
        "expected_salary": profile.get("expected_salary"),
        "last_working_day": profile.get("last_working_day"),
        **changes,
    }
    update_user_profile(user_id, profile["name"], **merged)
    return f"Updated: {', '.join(changes)}."


@tool
def get_resume_text(config: RunnableConfig) -> str:
    """Gets the candidate's resume as plain text.

    Call this only when you actually need the resume, e.g. before writing a job
    application email. Don't call it for normal questions. Takes no arguments.
    """
    return config.get("configurable", {}).get("resume_text") or "No resume on file."


@tool
def request_resume_update() -> str:
    """Asks the candidate to upload a new resume PDF and replaces the saved one.

    Call this when the candidate wants to update, replace or change their resume.
    It pauses the chat and shows an upload box; it returns once they've uploaded
    a file or cancelled. Takes no arguments.
    """
    answer = interrupt({"type": "resume_upload"})
    if not answer or answer.get("status") != "updated":
        return "The candidate cancelled; the resume was not changed."
    return f"Resume updated to '{answer['filename']}'. get_resume_text now returns the new resume."


@tool(response_format="content_and_artifact")
def send_application_email(
    recipient_emails: list[str],
    company_name: str,
    role: str,
    subject: str,
    body: str,
    config: RunnableConfig,
):
    """Sends the finalized job application email to the given recruiter addresses.

    Call this exactly once, only after you are fully satisfied with the draft.
    Calling it actually delivers the email over SMTP right away.

    Args:
        recipient_emails: Recruiter email addresses to send the application to.
        company_name: Name of the hiring company, used only for tracking.
        role: Job title being applied for, used only for tracking.
        subject: Final email subject line.
        body: Final plain-text email body.
    """
    cfg = config.get("configurable", {})
    own_email = (cfg.get("my_email") or "").strip().lower()
    recipient_emails = [
        r.strip() for r in recipient_emails
        if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", r.strip()) and r.strip().lower() != own_email
    ]
    if not recipient_emails:
        return "Not sent: no valid recruiter email address was provided. Ask the candidate for one.", None

    resume_bytes = cfg.get("resume_bytes")
    attachments = (
        [(cfg.get("resume_filename") or "resume.pdf", resume_bytes)]
        if resume_bytes
        else None
    )
    for recipient in recipient_emails:
        send_email(
            my_email=cfg["my_email"],
            my_password=cfg["my_password"],
            recipient_email=recipient,
            subject=subject,
            body=body,
            attachments=attachments,
        )
    sent = {
        "company_name": company_name,
        "role": role,
        "recipient_emails": recipient_emails,
        "subject": subject,
        "body": body,
    }
    return f"Email sent to {', '.join(recipient_emails)}.", sent


def build_prompt(state):
    system_prompt = f"""
    You are the candidate writing the email yourself.
    Write in first person only.
    Use "I", "my", and "me" throughout.
    Do not mention that you are an AI, assistant, or agent.
    Do not refer to "the candidate" or "the user".

    Your job is to write a short, natural job application email from the candidate's point of view.
    The email should feel personal, genuine, and written by the person applying for the role.

    Writing style:
    - Warm, direct, and concise
    - Short sentences and natural wording
    - No robotic phrases
    - No cover-letter style or generic buzzwords
    - Keep it under 150 words
    - Sound like a real person emailing a recruiter

    What to include:
    - Greeting
    - Mention the role I am applying for
    - Briefly explain why my experience matches the role
    - Only mention real skills and experience from the resume
    - Never invent or exaggerate
    - Say I am immediately available
    - End with:
      Best regards,
      Name
      Email
      Mobile

    Important restrictions:
    - Do not mention my current company name, current employer, or education unless the job description specifically asks for it.
    - Do not mention company names in the email body unless the hiring company is being referred to in the job description and it is necessary.
    - Do not add extra details that were not asked for.
    - Do not pull any personal detail unless they ask and last working day also keep immidiate available if they ask fot lwd then only mention lwd .
    - Keep the email focused on the role and my fit for it.
    - The company name is only used for tracking and should not appear in the body unless required.
    - Subject should be short and natural, for example: "Application for <role>"

    Today is {get_date()}.
    """
    return [{"role": "system", "content": system_prompt}] + state["messages"]


root_agent = create_react_agent(
    tools=ToolNode(
        [get_candidate_details, update_candidate_details, get_resume_text, request_resume_update, send_application_email],
        handle_tool_errors=True,
    ),
    model=get_deepseek_model(),
    prompt=build_prompt,
    checkpointer=MemorySaver(),
)

