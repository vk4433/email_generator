import re

from google import genai
from google.genai import types
from dotenv import load_dotenv
from datetime import datetime

from base.send_email import send_email


load_dotenv()

def get_current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def resume_attachment_filename(candidate_name):
    safe_name = re.sub(r"[^A-Za-z0-9 _-]", "", candidate_name or "").strip()
    return f"{safe_name} Resume.pdf" if safe_name else "resume.pdf"

client = genai.Client()


def generate_and_send_email(job_description, resume_text, my_email, my_password, candidate_name=None, resume_bytes=None):
    """Drafts a personalized job application email and lets the model send it itself.

    Returns a dict describing what was sent (company_name, role, recipient_emails,
    subject, body) once the model has called the send tool, or None if the model
    never called it.
    """
    sent_result = {}

    def send_application_email(recipient_emails: list[str], company_name: str, role: str, subject: str, body: str) -> str:
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
        attachments = [(resume_attachment_filename(candidate_name), resume_bytes)] if resume_bytes else None
        for recipient in recipient_emails:
            send_email(
                my_email=my_email,
                my_password=my_password,
                recipient_email=recipient,
                subject=subject,
                body=body,
                attachments=attachments,
            )
        sent_result.update({
            "company_name": company_name,
            "role": role,
            "recipient_emails": recipient_emails,
            "subject": subject,
            "body": body,
        })
        return f"Email sent to {', '.join(recipient_emails)}."

    chat = client.chats.create(
        model="gemini-3.5-flash-lite",
        config=types.GenerateContentConfig(tools=[send_application_email]),
    )

    prompt = f"""
    You are a personalized job application email generator and sender.

    You will be provided with a job description and a candidate's resume text.
    Your task is to write a professional, concise, and highly personalized job
    application email tailored specifically to the given role, then send it
    yourself using the send_application_email tool.

    Instructions:
    - Analyze the job description and identify the most relevant skills,
    qualifications, and experiences from the resume.
    - Highlight only skills that are actually present in the resume.
    - Avoid including any information that is not present in the resume and generic statements and unnecessary details of current company , education background.
    - Do not invent or exaggerate any qualifications, experience, or achievements.
    - Dont keep current company name or any other detail of company name in the email body unless requirement ask.
    today date is {get_current_timestamp()} say recruiters i am immediately available.
    - Express genuine enthusiasm for the position and the company.
    - Keep the tone professional, natural, and confident.
    - Include a professional greeting, body, and closing.
    - Keep the email under 200 words.
    - include personal details from the resume to contact the candidate for further discussion.
    - dont keep linkedin or any other social media links in the email.
    - personal details dont mention in the middle of the email body, only at the end for further discussion.
      Best regards
      Name : name from resume
      Email : email from resume
      Mobile : mobile number from resume

    Job Description:
    {job_description}

    Resume Text:
    {resume_text}

    If the company name isn't stated explicitly in the job description, make your
    best guess from context (e.g. a recruiting agency name). Identify every
    recruiter email address present in the job description to use as recipients.

    Once you have finalized the subject and body, call the send_application_email
    tool with the recipient emails, company name, role, subject, and body to send
    it. You must call the tool — do not just describe or print the email.
"""
    chat.send_message(prompt)
    return sent_result or None
