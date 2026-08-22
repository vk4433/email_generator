from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client()

def generate_email(job_description, resume_text):
    chat = client.chats.create(model="gemini-3.5-flash-lite")
    prompt = f"""
    You are a personalized job application email generator.

    You will be provided with a job description and a candidate's resume text.
    Your task is to write a professional, concise, and highly personalized job
    application email tailored specifically to the given role.

    Instructions:
    - Analyze the job description and identify the most relevant skills,
    qualifications, and experiences from the resume.
    - Highlight only skills and experience that are actually present in the resume.
    - highlight the user 's relevant experience and skills that match the job requirements.
    - Avoid including any information that is not present in the resume.
    - Do not invent or exaggerate any qualifications, experience, or achievements.
    - Clearly connect the candidate's relevant background to the requirements of
    the job.
    - Express genuine enthusiasm for the position and the company.
    - Keep the tone professional, natural, and confident.
    - Include a professional greeting, body, and closing.
    - Keep the email under 200 words.
    - Avoid generic statements and unnecessary details.
    - include personal details from the resume to contanct the candidate for further discussion.
    - dont keep linkdin or any other social media links in the email.

    Job Description:
    {job_description}

    Resume Text:
    {resume_text}
   strictly follow the instructions above and generate a personalized job application email based on the provided information.
   output the email in plain text format without any additional commentary or explanation.
   respond only with valid JSON in this exact format:
   {{
     "recruiter_emails": [],
     "company_name": "",
     "role": "",
     "subject": "",
     "body": ""
   }}
   If the company name isn't stated explicitly in the job description, make your best guess from context (e.g. a recruiting agency name).
   personal details dont mention on middle of the email body, only mention at the end of the email body for further discussion.
   Best regards
   Name : name from resume
   Email : email from resume
   Mobile : mobile number from resume
"""
    response = chat.send_message(prompt)
    return response.text
