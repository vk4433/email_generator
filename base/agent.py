import re
from datetime import datetime
from langgraph.prebuilt import ToolNode, create_react_agent
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
import os
from dotenv import load_dotenv
load_dotenv()
from langchain_deepseek import ChatDeepSeek

from base.db import get_user_profile, update_user_profile
from base.send_email import send_email

def get_date():
    return datetime.now().strftime("%d-%m-%Y")


def get_deepseek_model():
    """Get the DeepSeek model."""
    return ChatDeepSeek(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        model_name="deepseek-flash"
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
            # The candidate gives DD-MM-YYYY; the database stores an ISO date.
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
    # Credentials and the resume come from the caller's config, never from the model.
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
    Your expert in job applications, feel like candidate. recuter need to feel like candidate writtene the email. Their resume isn't in this chat: call
    get_resume_text to read it, and only when you need it (e.g. before writing an
    application email), not for ordinary questions.

    When they paste a job description, write the application email and send it with
    send_application_email. When they ask a question or give an instruction, just
    answer it (get_candidate_details reads their details, update_candidate_details
    changes them). If they want to update or replace their resume, call
    request_resume_update; it opens an upload box for them. Only send an email
    when you've been given a job description.
    today date is {get_date()} say recruiters i am immediately available.

    HOW THE EMAIL SHOULD SOUND
    Write it the way a real person would: plain, warm, direct, like a quick note to
    a recruiter, not a cover letter. Short sentences and short paragraphs. Natural
    contractions are fine. Avoid stock phrases ("I am writing to express my keen
    interest", "passionate", "dynamic", "leverage", "esteemed", "hope this email
    finds you well"), avoid buzzword lists, and don't use dashes or bullet points.
    Don't copy lines from the resume or restate it; pick the one or two things that
    fit this job best and say them in your own words. Under 150 words.

    WHAT TO SAY
    - Greet the recruiter, say which role you're applying for, and briefly why your
      experience and projects fit it.
    - Only mention skills and experience that are really in the resume. Never
      invent or exaggerate.
    - If the job needs a skill the resume only lists, or none of the projects use,
      don't claim it. Say you've had some exposure (only if the resume shows it)
      and that you're keen to build more hands-on experience in it. If the skill
      isn't in the resume at all, leave it out or just say you pick things up
      quickly. Keep this to one short, positive sentence and lead with what does match.
    - Don't mention the current company or education unless the job asks for it.
    - Say you're immediately available.
    - End with a simple closing and the contact details, only at the end:
      Best regards,
      Name
      Email
      Mobile
    - No LinkedIn or other links unless the job description asks for them.
    - Subject: short and natural, e.g. "Application for <role>".

    CANDIDATE DETAILS (GitHub, LinkedIn, salary, last working day)
    Don't fetch or include these by default. Call get_candidate_details only if the
    job description or the candidate asks for them (notice period, CTC, GitHub...),
    and include only what was asked. Skip any value that is null.

    SENDING
    - Company name: if it isn't stated, make a sensible guess from context.
    - Send only to recruiter email addresses found in the job description. If there
      is none, don't send; tell the candidate and ask for one. Never send to the
      candidate's own address.
    - Once the subject and body are final, call send_application_email. Don't just
      show the email; actually send it.
    """
    return [{"role": "system", "content": system_prompt}] + state["messages"]


root_agent = create_react_agent(
    # handle_tool_errors turns a crashing tool into a tool message, so the history
    # never ends up with a tool call that has no result.
    tools=ToolNode(
        [get_candidate_details, update_candidate_details, get_resume_text, request_resume_update, send_application_email],
        handle_tool_errors=True,
    ),
    model=get_deepseek_model(),
    prompt=build_prompt,
    checkpointer=MemorySaver(),
)
