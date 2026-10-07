import hashlib
import secrets
import uuid
from datetime import date, datetime

import streamlit as st
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from base.agent import root_agent
from base.constants import STATUS_COLORS, STATUS_LABELS
from base.db import (
    clear_api_key,
    create_application,
    create_user,
    delete_application,
    download_resume,
    get_gmail_password,
    get_user_id_by_api_key,
    get_user_profile,
    list_applications,
    set_api_key,
    update_application_status,
    update_gmail_password,
    update_resume_path,
    update_user_password,
    update_user_profile,
    upload_resume,
    verify_user_password,
)
from base.resume_text import ResumeText

st.set_page_config(page_title="Applyly · AI job application assistant", page_icon="✉️", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
#MainMenu, footer, [data-testid="stToolbar"] {visibility: hidden;}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display: none;}
header[data-testid="stHeader"] {background: transparent; height: 0;}
.block-container {padding-top: 3.5rem; max-width: 880px;}
h1, h2, h3 {letter-spacing: -0.02em;}
.stButton>button, .stDownloadButton>button {border-radius: 10px; font-weight: 600;}
div[data-testid="stForm"] {
    border: 1px solid rgba(128, 128, 128, 0.22);
    border-radius: 16px;
    padding: 1.4rem 1.6rem 0.8rem;
}
div[data-testid="stChatMessage"] {border-radius: 14px;}
.hero {padding: 1.2rem 0 1.6rem;}
.hero h1 {font-size: 2.4rem; margin-bottom: 0.3rem;}
.hero p {opacity: 0.7; font-size: 1.05rem; margin: 0;}
.brand {font-weight: 800; font-size: 1.25rem; letter-spacing: -0.02em; margin-bottom: 0.9rem;}
.user-card {
    border: 1px solid rgba(128, 128, 128, 0.22);
    border-radius: 14px;
    padding: 0.8rem 0.9rem;
    margin-bottom: 1rem;
    display: flex; align-items: center; gap: 0.7rem;
}
.user-card .avatar {
    flex: none; width: 38px; height: 38px; border-radius: 50%;
    background: linear-gradient(135deg, #6a5cff, #ff6aa5);
    color: #fff; text-align: center; line-height: 38px; font-weight: 700;
}
.user-card .meta {min-width: 0; line-height: 1.25;}
.user-card .meta span {display: block; opacity: 0.65; font-size: 0.8rem; overflow: hidden; text-overflow: ellipsis;}
.empty-chat {text-align: center; padding: 2.5rem 0 1.2rem;}
.empty-chat h2 {margin-bottom: 0.3rem;}
.empty-chat p {opacity: 0.65; margin: 0;}
.pill {padding: 2px 12px; border-radius: 999px; font-size: 0.78rem; font-weight: 600;}
</style>
""", unsafe_allow_html=True)

SESSION_PARAM = "s"

if "user" not in st.session_state:
    st.session_state.user = None


# ---------------------------------------------------------------- session

def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def log_in(user_id: int):
    # A fresh API key on every login; only its hash is stored in the database.
    api_key = secrets.token_urlsafe(32)
    set_api_key(user_id, hash_api_key(api_key))
    st.session_state.user = get_user_profile(user_id)
    st.query_params[SESSION_PARAM] = api_key


def restore_session():
    api_key = st.query_params.get(SESSION_PARAM)
    if api_key:
        user_id = get_user_id_by_api_key(hash_api_key(api_key))
        if user_id:
            st.session_state.user = get_user_profile(user_id)
        else:
            del st.query_params[SESSION_PARAM]


def refresh_user(user_id: int):
    st.session_state.user = get_user_profile(user_id)


# ---------------------------------------------------------------- auth

def show_auth():
    st.markdown(
        '<div class="hero"><h1>✉️ Applyly</h1>'
        "<p>Paste a job description. Your AI assistant writes a personal email and sends it for you.</p></div>",
        unsafe_allow_html=True,
    )

    login_tab, signup_tab = st.tabs(["Log in", "Create account"])

    with login_tab:
        with st.form("login_form"):
            st.subheader("Welcome back")
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password", placeholder="Your password")
            submitted = st.form_submit_button("Log in", type="primary", width="stretch")
        if submitted:
            if not (email and password):
                st.error("Enter your email and password.")
            else:
                with st.spinner("Logging in..."):
                    user_id = verify_user_password(email, password)
                    if user_id:
                        log_in(user_id)
                if user_id:
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

    with signup_tab:
        with st.form("signup_form", clear_on_submit=True):
            st.subheader("Create your account")
            name = st.text_input("Full name", placeholder="Vinod Kumar")
            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input("Email", key="signup_email", placeholder="you@gmail.com")
            with col2:
                password = st.text_input("Password", type="password", key="signup_password",
                                         placeholder="Choose a password")
            gmail_password = st.text_input(
                "Gmail app password", type="password", placeholder="16-character app password",
                help="Emails are sent from your Gmail account using an app password, not your real password.",
            )
            st.markdown("[Create a Gmail app password ↗](https://myaccount.google.com/apppasswords)")
            col3, col4 = st.columns(2)
            with col3:
                linkedin_url = st.text_input("LinkedIn (optional)", placeholder="https://linkedin.com/in/your-name")
            with col4:
                github_url = st.text_input("GitHub (optional)", placeholder="https://github.com/your-name")
            resume_file = st.file_uploader("Resume (PDF)", type=["pdf"],
                                           help="Drag and drop your resume here.")
            submitted = st.form_submit_button("Create account", type="primary", width="stretch")
        if submitted:
            gmail_password = gmail_password.replace(" ", "")
            if not (name and email and password and gmail_password and resume_file):
                st.error("Name, email, password, Gmail app password and resume are required.")
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
                    st.success("Account created. Switch to the Log in tab to continue.")
                except Exception as e:
                    st.error(f"Could not create account: {e}")


# ---------------------------------------------------------------- chat

def reset_chat():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.chat_display = []
    st.session_state.pending_upload = False
    st.session_state.resume_cache = None
    st.session_state.uploader_key = 0


def ensure_chat_state():
    if "thread_id" not in st.session_state:
        reset_chat()
    st.session_state.setdefault("uploader_key", 0)


def get_resume(user):
    if st.session_state.resume_cache is None:
        resume_bytes = download_resume(user["resume_pdf"])
        st.session_state.resume_cache = (resume_bytes, ResumeText.extract_text(resume_bytes))
    return st.session_state.resume_cache


def repair_thread(config):
    """Gives every tool call in the history a result, so the model accepts the history again."""
    state = root_agent.get_state(config)
    if any(task.interrupts for task in state.tasks):
        return  # waiting for the resume upload; that is a valid state
    messages = state.values.get("messages", [])
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    missing = [
        ToolMessage(content="This step didn't finish.", tool_call_id=call["id"], name=call["name"])
        for m in messages if isinstance(m, AIMessage)
        for call in m.tool_calls
        if call["id"] not in answered
    ]
    if missing:
        root_agent.update_state(config, {"messages": missing}, as_node="tools")


def run_agent(user, agent_input):
    """Runs the agent on this chat's thread. Returns (reply, sent_email, interrupted)."""
    resume_bytes, resume_text = get_resume(user)
    config = {"configurable": {
        "thread_id": st.session_state.thread_id,
        "user_id": user["user_id"],
        "my_email": user["email"],
        "my_password": get_gmail_password(user["user_id"]),
        "resume_filename": user["resume_pdf"].split("/")[-1],
        "resume_bytes": resume_bytes,
        "resume_text": resume_text,
    }}

    if isinstance(agent_input, str):
        repair_thread(config)
    existing = root_agent.get_state(config).values.get("messages", [])
    if isinstance(agent_input, str):
        agent_input = {"messages": [{"role": "user", "content": agent_input}]}

    root_agent.invoke(agent_input, config=config)
    state = root_agent.get_state(config)
    new_messages = state.values["messages"][len(existing):]
    interrupted = any(task.interrupts for task in state.tasks)

    sent = next(
        (m.artifact for m in new_messages
         if isinstance(m, ToolMessage) and m.name == "send_application_email" and m.artifact),
        None,
    )
    if sent:
        create_application(
            user["user_id"], sent["company_name"], sent["role"],
            recruiter_email=", ".join(sent["recipient_emails"]),
        )
        st.toast(f"Email sent to {', '.join(sent['recipient_emails'])}", icon="✅")
    if any(isinstance(m, ToolMessage) and m.name == "update_candidate_details" for m in new_messages):
        refresh_user(user["user_id"])

    if interrupted:
        reply = "Sure, drop your new resume below and I'll switch to it."
    else:
        reply = state.values["messages"][-1].content
        if sent:
            reply += (
                f"\n\n---\n**To:** {', '.join(sent['recipient_emails'])}  \n"
                f"**Subject:** {sent['subject']}\n\n{sent['body']}"
            )
    return reply, interrupted


def handle_prompt(user, prompt):
    st.session_state.chat_display.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Working on it..."):
                reply, interrupted = run_agent(user, prompt)
        except Exception as e:
            reply, interrupted = f"Something went wrong: {e}", False
        st.markdown(reply)
    st.session_state.chat_display.append({"role": "assistant", "content": reply})
    st.session_state.pending_upload = interrupted
    if interrupted:
        st.rerun()


def resume_upload_prompt(user):
    """Drag-and-drop box shown when the agent pauses to ask for a new resume."""
    with st.chat_message("assistant"):
        st.markdown("**Upload your new resume**")
        file = st.file_uploader(
            "Drag and drop your new resume (PDF)",
            type=["pdf"],
            key=f"chat_resume_{st.session_state.uploader_key}",
            label_visibility="collapsed",
        )
        cancel = st.button("Cancel", key="cancel_resume_upload")

    if file is None and not cancel:
        return

    if cancel:
        answer = {"status": "cancelled"}
        note = "No problem, your resume stays as it is."
    else:
        with st.spinner("Updating your resume..."):
            file_bytes = file.getvalue()
            path = upload_resume(user["user_id"], file_bytes, file.name)
            update_resume_path(user["user_id"], path)
            refresh_user(user["user_id"])
            resume_text = ResumeText.extract_text(file_bytes)
            st.session_state.resume_cache = (file_bytes, resume_text)
        answer = {"status": "updated", "filename": file.name}
        note = None

    new_user = st.session_state.user
    try:
        with st.spinner("Continuing..."):
            reply, _ = run_agent(new_user, Command(resume=answer))
    except Exception as e:
        reply = f"Something went wrong: {e}"
    st.session_state.chat_display.append({"role": "assistant", "content": note or reply})
    st.session_state.pending_upload = False
    st.session_state.uploader_key += 1
    st.rerun()


def show_chat(user):
    ensure_chat_state()
    if not user.get("resume_pdf"):
        st.warning("No resume on file yet. Ask the assistant to update your resume or add one in Profile → Resume.")

    if not st.session_state.chat_display and not st.session_state.pending_upload:
        st.markdown(
            '<div class="empty-chat"><h2>Who are we applying to today?</h2>'
            "<p>Paste a job description and I'll write the email and send it to the recruiter.</p></div>",
            unsafe_allow_html=True,
        )

    for msg in st.session_state.chat_display:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state.pending_upload:
        resume_upload_prompt(user)

    prompt = st.chat_input(
        "Paste a job description, or ask me anything…",
        disabled=st.session_state.pending_upload,
    )
    if prompt:
        if not user.get("resume_pdf") and "resume" not in prompt.lower():
            st.error("Add a resume first. Say “update my resume” to upload one.")
        else:
            handle_prompt(user, prompt)


# ---------------------------------------------------------------- applications

def status_pill(status: int) -> str:
    color = STATUS_COLORS.get(status, "#868e96")
    label = STATUS_LABELS.get(status, "Unknown")
    return f'<span class="pill" style="background:{color}22;color:{color};">{label}</span>'


def show_applications(user):
    st.header("Applications")
    applications = list_applications(user["user_id"])

    total = len(applications)
    got_update = sum(1 for a in applications if a["status"] == 1)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total sent", total)
    col2.metric("Awaiting response", total - got_update)
    col3.metric("Got an update", got_update)

    if not applications:
        st.info("Nothing here yet. Applications show up automatically after the assistant sends an email.")
        return

    search = st.text_input("Search", placeholder="Search by company or role…", label_visibility="collapsed")
    if search:
        term = search.lower()
        applications = [
            a for a in applications
            if term in a["company_name"].lower() or term in a["role"].lower()
        ]
        if not applications:
            st.caption("No applications match that search.")

    status_options = list(STATUS_LABELS.values())
    label_to_status = {v: k for k, v in STATUS_LABELS.items()}

    for a in applications:
        with st.container(border=True):
            top_left, top_right = st.columns([4, 1])
            top_left.markdown(f"**{a['company_name']}** · {a['role']}")
            top_right.markdown(status_pill(a["status"]), unsafe_allow_html=True)
            st.caption(f"{a['date_of_application']} · Recruiter: {a.get('recruiter_email') or '—'}")

            col4, col5 = st.columns([4, 1])
            current_label = STATUS_LABELS.get(a["status"], "Unknown")
            with col4:
                new_label = st.selectbox(
                    "Status",
                    options=status_options,
                    index=status_options.index(current_label) if current_label in status_options else 0,
                    key=f"status_{a['application_id']}",
                    label_visibility="collapsed",
                )
                new_status = label_to_status[new_label]
                if new_status != a["status"]:
                    with st.spinner("Updating status..."):
                        update_application_status(a["application_id"], user["user_id"], new_status)
                    st.rerun()
            with col5:
                if st.button("Delete", key=f"delete_{a['application_id']}", width="stretch"):
                    with st.spinner("Deleting..."):
                        delete_application(a["application_id"], user["user_id"])
                    st.rerun()


# ---------------------------------------------------------------- profile

def _to_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _to_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def show_details_tab(user):
    with st.form("profile_form"):
        name = st.text_input("Full name", value=user.get("name", ""), placeholder="Your name")
        col1, col2 = st.columns(2)
        with col1:
            linkedin_url = st.text_input("LinkedIn", value=user.get("linkedin_url") or "",
                                         placeholder="https://linkedin.com/in/your-name")
        with col2:
            github_url = st.text_input("GitHub", value=user.get("github_url") or "",
                                       placeholder="https://github.com/your-name")
        st.caption("Job details: the assistant shares these only when a job asks for them.")
        col3, col4, col5 = st.columns(3)
        with col3:
            current_salary = st.number_input("Current salary", value=_to_float(user.get("current_salary")),
                                             min_value=0.0, step=10000.0, placeholder="e.g. 1200000")
        with col4:
            expected_salary = st.number_input("Expected salary", value=_to_float(user.get("expected_salary")),
                                              min_value=0.0, step=10000.0, placeholder="e.g. 1800000")
        with col5:
            last_working_day = st.date_input("Last working day", value=_to_date(user.get("last_working_day")),
                                             format="DD-MM-YYYY")
        submitted = st.form_submit_button("Save details", type="primary")
    if submitted:
        if not name.strip():
            st.error("Name can't be empty.")
            return
        with st.spinner("Saving details..."):
            update_user_profile(
                user["user_id"], name.strip(),
                linkedin_url=linkedin_url.strip() or None,
                github_url=github_url.strip() or None,
                last_working_day=last_working_day.isoformat() if last_working_day else None,
                current_salary=current_salary,
                expected_salary=expected_salary,
            )
            refresh_user(user["user_id"])
        st.toast("Details saved", icon="✅")
        st.rerun()


def show_security_tab(user):
    with st.form("password_form", clear_on_submit=True):
        st.subheader("Login password")
        new_password = st.text_input("New password", type="password", placeholder="Choose a new password")
        submitted = st.form_submit_button("Change password")
    if submitted:
        if new_password:
            with st.spinner("Updating password..."):
                update_user_password(user["user_id"], new_password)
            st.toast("Password updated", icon="✅")
            st.rerun()
        else:
            st.error("Enter a new password.")

    with st.form("gmail_password_form", clear_on_submit=True):
        st.subheader("Gmail app password")
        st.markdown("[Create a Gmail app password ↗](https://myaccount.google.com/apppasswords)")
        new_gmail_password = st.text_input("New Gmail app password", type="password",
                                           placeholder="16-character app password")
        submitted = st.form_submit_button("Change Gmail app password")
    if submitted:
        new_gmail_password = new_gmail_password.replace(" ", "")
        if new_gmail_password:
            with st.spinner("Updating Gmail app password..."):
                update_gmail_password(user["user_id"], new_gmail_password)
            st.toast("Gmail app password updated", icon="✅")
            st.rerun()
        else:
            st.error("Enter a new Gmail app password.")


def show_resume_tab(user):
    current = (user.get("resume_pdf") or "").split("/")[-1]
    st.caption(f"Current resume: **{current}**" if current else "No resume uploaded yet.")
    st.info("Tip: you can also just tell the assistant in chat, “update my resume”.")
    with st.form("resume_form", clear_on_submit=True):
        resume_file = st.file_uploader("Replace resume (PDF)", type=["pdf"],
                                       help="Drag and drop a PDF here.")
        submitted = st.form_submit_button("Upload resume", type="primary")
    if submitted:
        if resume_file:
            with st.spinner("Uploading resume..."):
                resume_path = upload_resume(user["user_id"], resume_file.getvalue(), resume_file.name)
                update_resume_path(user["user_id"], resume_path)
                refresh_user(user["user_id"])
                st.session_state.resume_cache = None
            st.toast("Resume updated", icon="✅")
            st.rerun()
        else:
            st.error("Choose a PDF file first.")


def show_profile(user):
    st.header("Profile")
    details_tab, resume_tab, security_tab = st.tabs(["Details", "Resume", "Security"])
    with details_tab:
        show_details_tab(user)
    with resume_tab:
        show_resume_tab(user)
    with security_tab:
        show_security_tab(user)


# ---------------------------------------------------------------- app

if st.session_state.user is None:
    restore_session()
if st.session_state.user is None:
    show_auth()
    st.stop()

user = st.session_state.user
display_name = user.get("name") or user["email"]
st.session_state.setdefault("page", "chat")

brand_col, menu_col = st.columns([5, 1], vertical_alignment="center")
brand_col.markdown('<div class="brand">✉️ Applyly</div>', unsafe_allow_html=True)
with menu_col.popover("☰", width="stretch"):
    st.markdown(
        f"""
        <div class="user-card">
            <div class="avatar">{display_name[0].upper()}</div>
            <div class="meta"><strong>{display_name}</strong><span>{user['email']}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for key, label in (("chat", "💬 Chat"), ("applications", "📋 Applications"), ("profile", "👤 Profile")):
        if st.button(label, key=f"nav_{key}", width="stretch",
                     type="primary" if st.session_state.page == key else "secondary"):
            st.session_state.page = key
            st.rerun()
    if st.button("➕ New chat", key="nav_new_chat", width="stretch"):
        reset_chat()
        st.session_state.page = "chat"
        st.rerun()
    st.divider()
    if st.button("Log out", key="nav_logout", width="stretch"):
        clear_api_key(user["user_id"])
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()

page = st.session_state.page
if page == "applications":
    show_applications(user)
elif page == "profile":
    show_profile(user)
else:
    show_chat(user)
