from fastmcp import FastMCP

from base.agent import DEFAULT_PREFERENCES, _money, clean_recipients
from base.db import create_application, download_resume, get_gmail_password, get_user_profile
from base.resume_text import ResumeText
from base.send_email import send_email

USER_ID = 3

mcp = FastMCP("job-applications")


@mcp.tool()
def get_preferences() -> str:
    """Returns my preferences for writing application emails: tone, length, sign-off,
    subject format and any extra info about me.

    Call this before writing an application email and follow it.
    """
    user = get_user_profile(USER_ID) or {}
    return (user.get("user_prompt") or "").strip() or DEFAULT_PREFERENCES


@mcp.tool()
def get_personal_info() -> str:
    """Returns my personal details and my resume text: name, email, LinkedIn, GitHub,
    current and expected salary, last working day.

    Call this before writing an application email. Use only facts from here; never
    invent anything. Mention salary, LinkedIn, GitHub or last working day only if the
    job post or recruiter asks for them.
    """
    user = get_user_profile(USER_ID)
    if not user:
        return f"User {USER_ID} not found."

    resume_text = ""
    if user.get("resume_pdf"):
        resume_text = ResumeText.extract_text(download_resume(user["resume_pdf"])).strip()

    return f"""Name: {user.get("name") or "not set"}
Email: {user.get("email") or "not set"}
LinkedIn: {user.get("linkedin_url") or "not set"}
GitHub: {user.get("github_url") or "not set"}
Current salary: {_money(user.get("current_salary"))}
Expected salary: {_money(user.get("expected_salary"))}
Last working day: {user.get("last_working_day") or "not set"}

<resume>
{resume_text or "No resume uploaded yet."}
</resume>"""


@mcp.tool()
def send_application_email(
    recipient_emails: list[str],
    company_name: str,
    role: str,
    subject: str,
    body: str,
    resume: bool = True,
) -> str:
    """Sends my job application email from my Gmail right away.

    Call it once per application, as soon as the email is written.

    Args:
        recipient_emails: Recruiter email addresses to send the application to.
        company_name: Name of the hiring company, used for tracking.
        role: Job title being applied for, used for tracking.
        subject: Email subject line.
        body: Plain-text email body, signature included. No markdown.
        resume: Attach my saved resume PDF. Defaults to true.
    """
    user = get_user_profile(USER_ID)
    if not user:
        return f"Not sent: user {USER_ID} not found."

    recipient_emails = clean_recipients(recipient_emails, user["email"])
    if not recipient_emails:
        return "Not sent: there's no valid recruiter email address. Ask me for one."

    attachments = None
    if resume:
        if not user.get("resume_pdf"):
            return "Not sent: no resume is saved. Upload one in the app, or send with resume=false."
        filename = user["resume_pdf"].split("/")[-1]
        attachments = [(filename, download_resume(user["resume_pdf"]))]

    password = get_gmail_password(USER_ID)
    for recipient in recipient_emails:
        send_email(
            my_email=user["email"],
            my_password=password,
            recipient_email=recipient,
            subject=subject,
            body=body,
            attachments=attachments,
        )

    create_application(USER_ID, company_name, role, recruiter_email=", ".join(recipient_emails))

    attached = " with my resume attached" if attachments else ""
    return f"Sent to {', '.join(recipient_emails)}{attached}."


if __name__ == "__main__":
    # Serves at http://localhost:8000/mcp
    mcp.run(transport="http", host="0.0.0.0", port=8000)
