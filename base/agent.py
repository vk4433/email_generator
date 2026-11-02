import os
import re
from datetime import datetime

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, create_react_agent
from langgraph.types import interrupt

from base.db import get_user_profile, update_user_profile
from base.send_email import send_email

load_dotenv()


def get_date() -> str:
    return datetime.now().strftime("%d-%m-%Y")


def get_deepseek_model():
    """Get the DeepSeek model."""
    return ChatDeepSeek(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        model_name=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    )


def _format_lwd_from_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
    except (TypeError, ValueError):
        return None


def _format_lwd_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d-%m-%Y").date().isoformat()
    except (TypeError, ValueError):
        return None


def _is_valid_email(email: str | None) -> bool:
    if not email:
        return False
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))


@tool
def get_candidate_details(config: RunnableConfig) -> dict:
    """Gets the candidate's contact and job details: name, email, GitHub, LinkedIn,
    current salary, expected salary and last working day (LWD).

    Call it when you need these details for the email. A value of null means the
    candidate hasn't provided it, so leave it out.
    """
    user_id = config.get("configurable", {}).get("user_id")
    profile = get_user_profile(user_id) if user_id else None
    if not profile:
        return {"error": "Candidate details not found."}

    return {
        "name": profile.get("name"),
        "email": profile.get("email"),
        "github_url": profile.get("github_url"),
        "linkedin_url": profile.get("linkedin_url"),
        "current_salary": profile.get("current_salary"),
        "expected_salary": profile.get("expected_salary"),
        "last_working_day": _format_lwd_from_iso(profile.get("last_working_day")),
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

    changes: dict[str, object] = {}

    if github_url is not None:
        changes["github_url"] = github_url.strip() or None
    if linkedin_url is not None:
        changes["linkedin_url"] = linkedin_url.strip() or None
    if current_salary is not None:
        changes["current_salary"] = current_salary
    if expected_salary is not None:
        changes["expected_salary"] = expected_salary
    if last_working_day is not None:
        iso_lwd = _format_lwd_to_iso(last_working_day)
        if iso_lwd is None:
            return "last_working_day must be in DD-MM-YYYY format."
        changes["last_working_day"] = iso_lwd

    if not changes:
        return "No changes provided."

    merged = {
        "github_url": profile.get("github_url"),
        "linkedin_url": profile.get("linkedin_url"),
        "current_salary": profile.get("current_salary"),
        "expected_salary": profile.get("expected_salary"),
        "last_working_day": profile.get("last_working_day"),
        **changes,
    }

    update_user_profile(user_id, profile["name"], **merged)
    return f"Updated: {', '.join(changes.keys())}."


@tool
def get_resume_text(config: RunnableConfig) -> str:
    """Gets the candidate's resume as plain text.

    Call this only when you actually need the resume, e.g. before writing a job
    application email. Don't call it for normal questions.
    """
    return config.get("configurable", {}).get("resume_text") or "No resume on file."


@tool
def request_resume_update() -> str:
    """Asks the candidate to upload a new resume PDF and replaces the saved one.

    Call this when the candidate wants to update, replace or change their resume.
    It pauses the chat and shows an upload box; it returns once they've uploaded
    a file or cancelled.
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
    my_email = (cfg.get("my_email") or "").strip().lower()
    my_password = cfg.get("my_password")

    if not my_email or not my_password:
        return "Not sent: sender email or password is missing from config.", None

    cleaned_recipients = []
    for recipient in recipient_emails or []:
        email = recipient.strip()
        if _is_valid_email(email) and email.lower() != my_email:
            cleaned_recipients.append(email)

    if not cleaned_recipients:
        return "Not sent: no valid recruiter email address was provided. Ask the candidate for one.", None

    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject or not body:
        return "Not sent: subject and body are required.", None

    resume_bytes = cfg.get("resume_bytes")
    attachments = None
    if resume_bytes:
        filename = (cfg.get("resume_filename") or "resume.pdf").strip() or "resume.pdf"
        attachments = [(filename, resume_bytes)]

    for recipient in cleaned_recipients:
        send_email(
            my_email=my_email,
            my_password=my_password,
            recipient_email=recipient,
            subject=subject,
            body=body,
            attachments=attachments,
        )

    sent = {
        "company_name": company_name,
        "role": role,
        "recipient_emails": cleaned_recipients,
        "subject": subject,
        "body": body,
    }
    return f"Email sent to {', '.join(cleaned_recipients)}.", sent


def build_prompt(state):
    system_prompt = f"""
    You are a job-application assistant helping a candidate write and send recruiter emails.

    Rules:
    - Do not fetch or include candidate details unless the job description or the candidate
      explicitly asks for them.
    - If the user asks for profile updates, use update_candidate_details.
    - If they want to update or replace their resume, call request_resume_update.
    - Use get_resume_text only when needed to write an actual application email.
    - Only send an email after a real job description is provided.
    - Only send to recruiter email addresses found in the job description. Never send to the
      candidate's own address.
    - Send the final email with send_application_email exactly once when the draft is ready.

    Email writing rules:
    - Keep the email under 150 words.
    - Use a warm, direct, natural tone.
    - Mention only accurate experience from the resume.
    - Do not invent skills or exaggerate.
    - Say the candidate is immediately available.
    - End with:
      Best regards,
      Name
      Email
      Mobile
    - Subject should be short and natural, for example: "Application for <role>".

    Candidate details:
    - Use get_candidate_details only when the job description or candidate asks for GitHub,
      LinkedIn, notice period, salary, or last working day.
    - Include only fields that were explicitly requested and are not null.

    Today is {get_date()}.
    """
    return [{"role": "system", "content": system_prompt}] + state["messages"]


root_agent = create_react_agent(
    tools=ToolNode(
        [
            get_candidate_details,
            update_candidate_details,
            get_resume_text,
            request_resume_update,
            send_application_email,
        ],
        handle_tool_errors=True,
    ),
    model=get_deepseek_model(),
    prompt=build_prompt,
    checkpointer=MemorySaver(),
)

