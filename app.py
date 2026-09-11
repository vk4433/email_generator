import streamlit as st

from base.ai_email import generate_and_send_email
from base.constants import STATUS_COLORS, STATUS_LABELS
from base.db import (
    create_application,
    create_user,
    delete_application,
    download_resume,
    get_gmail_password,
    get_user_profile,
    list_applications,
    update_application_status,
    update_gmail_password,
    update_resume_path,
    update_user_password,
    update_user_profile,
    upload_resume,
    verify_user_password,
)
from base.resume_text import ResumeText

st.set_page_config(page_title="Job Application Email Generator", page_icon="📧", layout="wide")

st.markdown("""
<style>
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 2rem; max-width: 900px;}
h1 {font-weight: 700;}
h3 {margin-top: 0;}
div[data-testid="stForm"] {
    border: 1px solid rgba(128, 128, 128, 0.25);
    border-radius: 12px;
    padding: 1.25rem 1.5rem 0.5rem;
}
.stButton>button {border-radius: 8px; font-weight: 600;}
.user-card {
    border: 1px solid rgba(128, 128, 128, 0.25);
    border-radius: 12px;
    padding: 0.9rem 1rem;
    margin-bottom: 0.75rem;
}
.user-card .avatar {
    display: inline-block;
    width: 36px; height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6a5cff, #ff6aa5);
    color: white;
    text-align: center;
    line-height: 36px;
    font-weight: 700;
    margin-right: 0.6rem;
}
</style>
""", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.session_state.user = None
if "last_sent" not in st.session_state:
    st.session_state.last_sent = None


def show_auth():
    st.title("📧 Job Application Email Generator")
    st.caption("Generate personalized job application emails from your resume, and track every application you send.")

    login_tab, signup_tab = st.tabs(["Log in", "Sign up"])

    with login_tab:
        with st.form("login_form"):
            st.subheader("Welcome back")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", use_container_width=True)
        if submitted:
            with st.spinner("Logging in..."):
                user_id = verify_user_password(email, password)
                if user_id:
                    st.session_state.user = get_user_profile(user_id)
            if user_id:
                st.rerun()
            else:
                st.error("Invalid email or password.")

    with signup_tab:
        with st.form("signup_form", clear_on_submit=True):
            st.subheader("Create your account")
            name = st.text_input("Name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            st.markdown("[Generate a Gmail app password](https://myaccount.google.com/apppasswords)")
            gmail_password = st.text_input("Gmail app password", type="password")
            col1, col2 = st.columns(2)
            with col1:
                linkedin_url = st.text_input("LinkedIn URL (optional)")
            with col2:
                github_url = st.text_input("GitHub URL (optional)")
            resume_file = st.file_uploader("Resume (PDF)", type=["pdf"])
            submitted = st.form_submit_button("Create account", use_container_width=True)
        if submitted:
            gmail_password = gmail_password.replace(" ", "")
            if not (name and email and password and gmail_password and resume_file):
                st.error("All fields, including resume, are required.")
            else:
                try:
                    with st.spinner("Creating your account..."):
                        user_id = create_user(
                            name, email, password, gmail_password,
                            linkedin_url=linkedin_url or None,
                            github_url=github_url or None,
                        )
                        resume_path = upload_resume(user_id, resume_file.getvalue(), resume_file.name)
                        update_resume_path(user_id, resume_path)
                    st.success("Account created. Please log in.")
                except Exception as e:
                    st.error(f"Could not create account: {e}")


def show_compose(user):
    st.header("Compose")

    with st.container(border=True):
        st.subheader("Paste the job description")
        job_description = st.text_area("Job description", height=220, label_visibility="collapsed")
        st.caption("The AI drafts the application email and sends it itself — there's no review step before it goes out.")
        generate_clicked = st.button("✨ Generate & send email", type="primary")

    if generate_clicked:
        if not job_description.strip():
            st.error("Paste a job description first.")
        elif not user.get("resume_pdf"):
            st.error("No resume on file for this account.")
        else:
            with st.spinner("Generating and sending email..."):
                resume_bytes = download_resume(user["resume_pdf"])
                resume_text = ResumeText.extract_text(resume_bytes)
                gmail_password = get_gmail_password(user["user_id"])
                sent = generate_and_send_email(
                    job_description,
                    resume_text,
                    my_email=user["email"],
                    my_password=gmail_password,
                    resume_bytes=resume_bytes,
                )

            if not sent:
                st.error("The model didn't send an email. Please try again.")
            else:
                create_application(
                    user["user_id"],
                    sent["company_name"],
                    sent["role"],
                    recruiter_email=", ".join(sent["recipient_emails"]),
                )
                st.session_state.last_sent = sent
                st.toast(f"Email sent to {', '.join(sent['recipient_emails'])}!", icon="✅")

    if st.session_state.last_sent:
        sent = st.session_state.last_sent
        with st.container(border=True):
            st.subheader("Last sent")
            st.caption(f"{sent['company_name']} — {sent['role']}")
            st.write(f"**To:** {', '.join(sent['recipient_emails'])}")
            st.write(f"**Subject:** {sent['subject']}")
            st.text(sent["body"])


def show_details_tab(user):
    with st.form("profile_form"):
        name = st.text_input("Name", value=user.get("name", ""))
        col1, col2 = st.columns(2)
        with col1:
            linkedin_url = st.text_input("LinkedIn URL", value=user.get("linkedin_url") or "")
        with col2:
            github_url = st.text_input("GitHub URL", value=user.get("github_url") or "")
        submitted = st.form_submit_button("Save details")
    if submitted:
        with st.spinner("Saving details..."):
            update_user_profile(user["user_id"], name, linkedin_url=linkedin_url or None, github_url=github_url or None)
            st.session_state.user = get_user_profile(user["user_id"])
        st.toast("Details updated.", icon="✅")
        st.rerun()


def show_security_tab(user):
    with st.form("password_form", clear_on_submit=True):
        st.subheader("Login password")
        new_password = st.text_input("New login password", type="password")
        submitted = st.form_submit_button("Change password")
    if submitted:
        if new_password:
            with st.spinner("Updating password..."):
                update_user_password(user["user_id"], new_password)
            st.toast("Password updated.", icon="✅")
            st.rerun()
        else:
            st.error("Enter a new password.")

    with st.form("gmail_password_form", clear_on_submit=True):
        st.subheader("Gmail app password")
        st.markdown("[Generate a Gmail app password](https://myaccount.google.com/apppasswords)")
        new_gmail_password = st.text_input("New Gmail app password", type="password")
        submitted = st.form_submit_button("Change Gmail app password")
    if submitted:
        new_gmail_password = new_gmail_password.replace(" ", "")
        if new_gmail_password:
            with st.spinner("Updating Gmail app password..."):
                update_gmail_password(user["user_id"], new_gmail_password)
            st.toast("Gmail app password updated.", icon="✅")
            st.rerun()
        else:
            st.error("Enter a new Gmail app password.")


def show_resume_tab(user):
    with st.form("resume_form", clear_on_submit=True):
        resume_file = st.file_uploader("Replace resume (PDF)", type=["pdf"])
        submitted = st.form_submit_button("Upload resume")
    if submitted:
        if resume_file:
            with st.spinner("Uploading resume..."):
                resume_path = upload_resume(user["user_id"], resume_file.getvalue(), resume_file.name)
                update_resume_path(user["user_id"], resume_path)
                st.session_state.user = get_user_profile(user["user_id"])
            st.toast("Resume updated.", icon="✅")
            st.rerun()
        else:
            st.error("Choose a PDF file first.")


def show_applications_tab(user):
    applications = list_applications(user["user_id"])

    total = len(applications)
    got_update = sum(1 for a in applications if a["status"] == 1)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total applications", total)
    col2.metric("Awaiting response", total - got_update)
    col3.metric("Got an update", got_update)

    if not applications:
        st.info("No applications logged yet.")
        return

    search = st.text_input("🔍 Search by company or role")
    if search:
        term = search.lower()
        applications = [
            a for a in applications
            if term in a["company_name"].lower() or term in a["role"].lower()
        ]

    status_options = list(STATUS_LABELS.values())
    label_to_status = {v: k for k, v in STATUS_LABELS.items()}

    for a in applications:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 3, 2])
            col1.markdown(f"**{a['company_name']}**")
            col2.write(a["role"])
            col3.write(str(a["date_of_application"]))
            st.caption(f"Recruiter: {a.get('recruiter_email') or '—'}")

            color = STATUS_COLORS.get(a["status"], "#868e96")
            current_label = STATUS_LABELS.get(a["status"], "Unknown")
            st.markdown(
                f'<span style="background:{color}22;color:{color};padding:2px 12px;'
                f'border-radius:999px;font-size:0.8rem;font-weight:600;">{current_label}</span>',
                unsafe_allow_html=True,
            )

            col4, col5 = st.columns([4, 1])
            with col4:
                new_label = st.selectbox(
                    "Status",
                    options=status_options,
                    index=status_options.index(current_label),
                    key=f"status_{a['application_id']}",
                    label_visibility="collapsed",
                )
                new_status = label_to_status[new_label]
                if new_status != a["status"]:
                    with st.spinner("Updating status..."):
                        update_application_status(a["application_id"], user["user_id"], new_status)
                    st.rerun()
            with col5:
                if st.button("🗑️ Delete", key=f"delete_{a['application_id']}", use_container_width=True):
                    with st.spinner("Deleting..."):
                        delete_application(a["application_id"], user["user_id"])
                    st.rerun()


def show_profile(user):
    st.header("Profile")
    details_tab, security_tab, resume_tab, applications_tab = st.tabs(
        ["Details", "Security", "Resume", "Applications"]
    )
    with details_tab:
        show_details_tab(user)
    with security_tab:
        show_security_tab(user)
    with resume_tab:
        show_resume_tab(user)
    with applications_tab:
        show_applications_tab(user)


if st.session_state.user is None:
    show_auth()
    st.stop()

user = st.session_state.user
initial = (user.get("name") or user["email"])[0].upper()

with st.sidebar:
    st.markdown(
        f"""
        <div class="user-card">
            <span class="avatar">{initial}</span>
            <strong>{user.get("name") or "—"}</strong><br>
            <span style="opacity:0.7; font-size:0.85rem;">{user['email']}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    page = st.radio("Navigate", ["Compose", "Profile"], label_visibility="collapsed")
    st.divider()
    if st.button("Log out", use_container_width=True):
        st.session_state.user = None
        st.session_state.generated = None
        st.rerun()

if page == "Compose":
    show_compose(user)
else:
    show_profile(user)
