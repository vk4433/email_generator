import os

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

RESUME_BUCKET = "resumes"

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_KEY"],
        )
    return _client


def upload_resume(user_id: int, file_bytes: bytes, filename: str) -> str:
    path = f"{user_id}/{filename}"
    client = get_client()
    client.storage.from_(RESUME_BUCKET).upload(
        path,
        file_bytes,
        {"content-type": "application/pdf", "upsert": "true"},
    )
    return path


def get_resume_signed_url(path: str, expires_in: int = 3600) -> str:
    client = get_client()
    result = client.storage.from_(RESUME_BUCKET).create_signed_url(path, expires_in)
    return result["signedURL"]


def download_resume(path: str) -> bytes:
    client = get_client()
    return client.storage.from_(RESUME_BUCKET).download(path)


def update_resume_path(user_id: int, resume_pdf: str) -> None:
    client = get_client()
    client.rpc(
        "update_resume_path",
        {"p_user_id": user_id, "p_resume_pdf": resume_pdf},
    ).execute()


def get_user_profile(user_id: int) -> dict | None:
    client = get_client()
    response = client.rpc("get_user_profile", {"p_user_id": user_id}).execute()
    return response.data[0] if response.data else None


def create_user(
    name: str,
    email: str,
    password: str,
    gmail_password: str,
    resume_pdf: str | None = None,
    linkedin_url: str | None = None,
    github_url: str | None = None,
) -> int:
    client = get_client()
    response = client.rpc(
        "create_user",
        {
            "p_name": name,
            "p_email": email,
            "p_password": password,
            "p_gmail_password": gmail_password,
            "p_resume_pdf": resume_pdf,
            "p_linkedin_url": linkedin_url,
            "p_github_url": github_url,
        },
    ).execute()
    return response.data


def verify_user_password(email: str, password: str) -> int | None:
    client = get_client()
    response = client.rpc(
        "verify_user_password",
        {"p_email": email, "p_password": password},
    ).execute()
    return response.data


def get_gmail_password(user_id: int) -> str:
    client = get_client()
    response = client.rpc(
        "get_gmail_password",
        {"p_user_id": user_id},
    ).execute()
    return response.data


def create_application(
    user_id: int,
    company_name: str,
    role: str,
    recruiter_email: str | None = None,
) -> int:
    client = get_client()
    response = client.rpc(
        "create_application",
        {
            "p_user_id": user_id,
            "p_company_name": company_name,
            "p_role": role,
            "p_recruiter_email": recruiter_email,
        },
    ).execute()
    return response.data


def list_applications(user_id: int) -> list[dict]:
    client = get_client()
    response = client.rpc("list_applications", {"p_user_id": user_id}).execute()
    return response.data


def update_application_status(application_id: int, user_id: int, status: int) -> None:
    client = get_client()
    client.rpc(
        "update_application_status",
        {"p_application_id": application_id, "p_user_id": user_id, "p_status": status},
    ).execute()


def delete_application(application_id: int, user_id: int) -> None:
    client = get_client()
    client.rpc(
        "delete_application",
        {"p_application_id": application_id, "p_user_id": user_id},
    ).execute()


def update_user_profile(
    user_id: int,
    name: str,
    linkedin_url: str | None = None,
    github_url: str | None = None,
    last_working_day: str | None = None,
    current_salary: float | None = None,
    expected_salary: float | None = None,
) -> None:
    client = get_client()
    client.rpc(
        "update_user_profile",
        {
            "p_user_id": user_id,
            "p_name": name,
            "p_linkedin_url": linkedin_url,
            "p_github_url": github_url,
            "p_last_working_day": last_working_day,
            "p_current_salary": current_salary,
            "p_expected_salary": expected_salary,
        },
    ).execute()


def update_user_password(user_id: int, password: str) -> None:
    client = get_client()
    client.rpc(
        "update_user_password",
        {"p_user_id": user_id, "p_password": password},
    ).execute()


def update_gmail_password(user_id: int, gmail_password: str) -> None:
    client = get_client()
    client.rpc(
        "update_gmail_password",
        {"p_user_id": user_id, "p_gmail_password": gmail_password},
    ).execute()


def set_api_key(user_id: int, api_key_hash: str) -> None:
    client = get_client()
    client.rpc(
        "set_api_key",
        {"p_user_id": user_id, "p_api_key_hash": api_key_hash},
    ).execute()


def get_user_id_by_api_key(api_key_hash: str) -> int | None:
    client = get_client()
    response = client.rpc(
        "get_user_id_by_api_key",
        {"p_api_key_hash": api_key_hash},
    ).execute()
    return response.data


def clear_api_key(user_id: int) -> None:
    client = get_client()
    client.rpc("clear_api_key", {"p_user_id": user_id}).execute()
