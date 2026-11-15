import hashlib
import html
import secrets
import uuid
from datetime import date, datetime

import streamlit as st
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage
from langgraph.types import Command

from base.agent import DEFAULT_PREFERENCES, root_agent
from base.constants import STATUS_LABELS
from base.db import (
    EmailAlreadyExistsError,
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
    update_user_prompt,
    upload_resume,
    verify_user_password,
)
from base.resume_text import ResumeText

st.set_page_config(page_title="ApplyBuddy · AI job application assistant", page_icon="✉️", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
#MainMenu, footer, [data-testid="stToolbar"] {visibility: hidden;}
header[data-testid="stHeader"] {background: transparent;}
[data-testid="stSidebar"] {border-right: 1px solid rgba(128, 128, 128, 0.2);}
[data-testid="stSidebar"] .stButton>button {justify-content: flex-start; text-align: left;}
[data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] {visibility: visible !important;}
.block-container {padding-top: 3.5rem; max-width: 880px;}
h1, h2, h3 {letter-spacing: -0.02em;}
.stButton>button, .stDownloadButton>button {border-radius: 10px; font-weight: 600;}
div[data-testid="stForm"] {
    border: 1px solid rgba(128, 128, 128, 0.22);
    border-radius: 16px;
    padding: 1.4rem 1.6rem 0.8rem;
}
div[data-testid="stChatMessage"] {
    background: transparent; padding: 0.4rem 0; margin-bottom: 0.4rem;
}
/* My messages: right-aligned bubble, like a messaging app. */
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    flex-direction: row-reverse;
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
    background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.22);
    border-radius: 18px 18px 4px 18px; padding: 0.6rem 1rem; margin-left: auto;
    max-width: 85%; flex: 0 1 auto;
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] p {
    white-space: pre-wrap;
}
[class*="st-key-sent_"] {
    border: 1px solid rgba(99, 102, 241, 0.35) !important;
    background: rgba(99, 102, 241, 0.04);
    box-shadow: 0 6px 24px rgba(30, 30, 80, 0.06);
}
.mail-head {display: flex; align-items: center; gap: 0.5rem; font-weight: 600; margin-bottom: 0.2rem;}
.mail-head .dot {width: 8px; height: 8px; border-radius: 50%; background: #2f9e44;}
.mail-meta {font-size: 0.85rem; opacity: 0.7; margin-bottom: 0.6rem;}
.mail-body {white-space: pre-wrap; font-size: 0.93rem; line-height: 1.55;}
.brand {font-weight: 800; font-size: 1.25rem; letter-spacing: -0.02em; margin-bottom: 0.9rem;}
.brand span {
    background: linear-gradient(135deg, #6a5cff, #ff6aa5);
    -webkit-background-clip: text; background-clip: text; color: transparent;
}
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
.empty-chat {text-align: center; padding: 3rem 0 1.4rem;}
.empty-chat .icon {
    width: 64px; height: 64px; margin: 0 auto 0.8rem; border-radius: 18px;
    background: linear-gradient(135deg, #6a5cff, #ff6aa5); color: #fff;
    font-size: 2rem; line-height: 64px;
}
.empty-chat h2 {margin-bottom: 0.3rem;}
.empty-chat p {opacity: 0.65; margin: 0 auto; max-width: 520px;}
.steps {display: flex; gap: 0.6rem; justify-content: center; flex-wrap: wrap; margin: 1.4rem 0 0.4rem;}
.step {
    border: 1px solid rgba(128,128,128,0.22); border-radius: 12px; padding: 0.55rem 0.85rem;
    font-size: 0.85rem; display: flex; gap: 0.45rem; align-items: center;
}
.step b {
    width: 20px; height: 20px; border-radius: 50%; font-size: 0.72rem; line-height: 20px;
    background: rgba(99, 102, 241, 0.15); color: #6366f1; text-align: center;
}
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
        """<style>
        [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display: none;}
        .auth-hero {text-align: center; padding: 1.5rem 0 1rem;}
        .auth-hero .logo {font-size: 2.6rem;}
        .auth-hero h1 {margin: 0.2rem 0 0.3rem; font-size: 2rem;}
        .auth-hero p {opacity: 0.7; margin: 0;}
        </style>""",
        unsafe_allow_html=True,
    )
    _, center, _ = st.columns([1, 3, 1])
    center.markdown(
        '<div class="auth-hero"><div class="logo">✉️</div><h1>ApplyBuddy</h1>'
        "<p>Paste a job description. Your AI assistant writes a personal email and sends it for you.</p></div>",
        unsafe_allow_html=True,
    )
    login_tab, signup_tab = center.tabs(["Log in", "Create account"])

    with login_tab:
        with st.form("login_form"):
            st.subheader("Welcome back")
            email = st.text_input("Email")
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
            name = st.text_input("Full name")
            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input("Email", key="signup_email")
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
                linkedin_url = st.text_input("LinkedIn (optional)")
            with col4:
                github_url = st.text_input("GitHub (optional)")
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
                except EmailAlreadyExistsError:
                    st.error("An account with this email already exists. Please log in instead.")
                except Exception as e:
                    st.error(f"Could not create account: {e}")


# ---------------------------------------------------------------- chat

ASSISTANT_AVATAR = ":material/edit_note:"


def reset_chat():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.chat_display = []
    st.session_state.pending = None
    st.session_state.resume_cache = None
    st.session_state.uploader_key = 0


def ensure_chat_state():
    if "thread_id" not in st.session_state:
        reset_chat()
    st.session_state.setdefault("uploader_key", 0)
    st.session_state.setdefault("pending", None)


def get_resume(user):
    if st.session_state.resume_cache is None:
        resume_bytes = download_resume(user["resume_pdf"]) if user.get("resume_pdf") else None
        resume_text = ResumeText.extract_text(resume_bytes) if resume_bytes else ""
        st.session_state.resume_cache = (resume_bytes, resume_text)
    return st.session_state.resume_cache


def repair_thread(config):
    """Gives every tool call in the history a result, so the model accepts the history again."""
    state = root_agent.get_state(config)
    if any(task.interrupts for task in state.tasks):
        return  # waiting for a resume upload; that is a valid state
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


def run_agent(user, agent_input, placeholder=None):
    """Runs the agent on this chat's thread.

    Returns (reply, sent_email, pending): pending is the interrupt payload when the agent
    paused for a resume upload, else None. If a Streamlit
    placeholder is given, the model's reply is streamed into it token by token.
    """
    resume_bytes, resume_text = get_resume(user)
    config = {"configurable": {
        "thread_id": st.session_state.thread_id,
        "user_id": user["user_id"],
        "my_name": user.get("name"),
        "my_email": user["email"],
        "my_password": get_gmail_password(user["user_id"]),
        "resume_filename": (user.get("resume_pdf") or "resume.pdf").split("/")[-1],
        "resume_bytes": resume_bytes,
        "resume_text": resume_text,
    }}

    if isinstance(agent_input, str):
        repair_thread(config)
        agent_input = {"messages": [{"role": "user", "content": agent_input}]}
    existing = root_agent.get_state(config).values.get("messages", [])

    streamed, current_id = "", None
    for chunk, meta in root_agent.stream(agent_input, config=config, stream_mode="messages"):
        if placeholder is None or not isinstance(chunk, AIMessageChunk) or meta.get("langgraph_node") != "model":
            continue
        if chunk.id != current_id:  # a new model turn started; drop text from the previous one
            streamed, current_id = "", chunk.id
        if isinstance(chunk.content, str) and chunk.content:
            streamed += chunk.content
            placeholder.markdown(streamed + "▌")

    state = root_agent.get_state(config)
    new_messages = state.values["messages"][len(existing):]
    pending = next(
        (i.value for task in state.tasks for i in task.interrupts if isinstance(i.value, dict)),
        None,
    )

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
        st.toast(f"Email sent to {', '.join(sent['recipient_emails'])}", icon=":material/send:")
    if any(isinstance(m, ToolMessage) and m.name == "update_candidate_details" for m in new_messages):
        refresh_user(user["user_id"])

    last_ai = next((m for m in reversed(new_messages) if isinstance(m, AIMessage)), None)
    text = (last_ai.content if last_ai and isinstance(last_ai.content, str) else "").strip()
    if pending and pending.get("type") == "resume_upload":
        reply = "Sure, drop your new resume below and I'll switch to it."
    else:
        reply = text or "Done."
    return reply, sent, pending


def after_run(reply, sent, pending):
    """Records the agent's turn in the chat and shows any card it paused on."""
    if reply:
        st.session_state.chat_display.append({"role": "assistant", "content": reply})
    if sent:
        st.session_state.chat_display.append({"role": "assistant", "email": sent})
    st.session_state.pending = pending


def error_message(e: Exception) -> str:
    """A readable chat message for a failed agent run."""
    status = getattr(e, "status_code", None)
    if status and status >= 500:
        return "The AI service is having a hiccup right now. Please send your message again in a moment."
    if status == 429:
        return "The AI service is busy (rate limit). Please wait a few seconds and try again."
    if status in (401, 403):
        return "The AI service rejected the API key. Check DEEPSEEK_API_KEY in your .env."
    return f"Something went wrong: {e}"


def handle_prompt(user, prompt):
    st.session_state.chat_display.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        placeholder = st.empty()
        placeholder.markdown(":gray[_Writing…_]")
        try:
            reply, sent, pending = run_agent(user, prompt, placeholder)
        except Exception as e:
            reply, sent, pending = error_message(e), None, None
        placeholder.markdown(reply)
    after_run(reply, sent, pending)
    st.rerun()


def resume_agent(user, answer, spinner_text):
    """Continues the paused agent with the answer from a card, then redraws the chat."""
    try:
        with st.spinner(spinner_text):
            result = run_agent(user, Command(resume=answer))
    except Exception as e:
        result = (error_message(e), None, None)
    after_run(*result)
    st.rerun()


def resume_upload_prompt(user):
    """Drag-and-drop box shown when the agent pauses to ask for a new resume."""
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        with st.container(border=True):
            st.markdown("**:material/upload_file: Upload your new resume**")
            file = st.file_uploader(
                "Drag and drop your new resume (PDF)",
                type=["pdf"],
                key=f"chat_resume_{st.session_state.uploader_key}",
                label_visibility="collapsed",
            )
            cancel = st.button("Keep my current resume", key="cancel_resume_upload")

    if file is None and not cancel:
        return

    st.session_state.uploader_key += 1
    if cancel:
        resume_agent(user, {"status": "cancelled"}, "One moment…")

    with st.spinner("Updating your resume…"):
        file_bytes = file.getvalue()
        path = upload_resume(user["user_id"], file_bytes, file.name)
        update_resume_path(user["user_id"], path)
        refresh_user(user["user_id"])
        st.session_state.resume_cache = (file_bytes, ResumeText.extract_text(file_bytes))
    resume_agent(st.session_state.user, {"status": "updated", "filename": file.name}, "Reading your new resume…")


def sent_email_card(email, index):
    with st.container(border=True, key=f"sent_{index}"):
        where = " at ".join(x for x in (email.get("role"), email.get("company_name")) if x)
        st.markdown(
            f'<div class="mail-head"><span class="dot"></span>Sent{" · " + html.escape(where) if where else ""}</div>'
            f'<div class="mail-meta">To {html.escape(", ".join(email["recipient_emails"]))}'
            f' · {html.escape(email["subject"])}</div>'
            f'<div class="mail-body">{html.escape(email["body"])}</div>',
            unsafe_allow_html=True,
        )


def show_chat(user):
    ensure_chat_state()
    pending = st.session_state.pending
    if not user.get("resume_pdf"):
        st.warning("No resume on file yet. Say “update my resume” or add one in Profile → Resume.",
                   icon=":material/description:")

    if not st.session_state.chat_display and not pending:
        first = (user.get("name") or "").strip().split(" ")[0].capitalize()
        st.markdown(
            f'<div class="empty-chat"><div class="icon">✉</div>'
            f'<h2>Hi{" " + html.escape(first) if first else ""}, where are we applying today?</h2>'
            "<p>Paste a job description. I'll write the email the way you would "
            "and send it from your Gmail with your resume attached.</p>"
            '<div class="steps">'
            '<div class="step"><b>1</b>Paste the job post</div>'
            '<div class="step"><b>2</b>I write it as you</div>'
            '<div class="step"><b>3</b>Sent to the recruiter</div></div></div>',
            unsafe_allow_html=True,
        )

    for i, msg in enumerate(st.session_state.chat_display):
        if msg["role"] == "assistant":
            with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
                if "email" in msg:
                    sent_email_card(msg["email"], i)
                else:
                    st.markdown(msg["content"])
        else:
            with st.chat_message("user"):
                st.markdown(msg["content"])

    if pending and pending.get("type") == "resume_upload":
        resume_upload_prompt(user)

    waiting_for_upload = bool(pending and pending.get("type") == "resume_upload")
    prompt = st.chat_input("Paste a job description, or ask me anything…", disabled=waiting_for_upload)
    if prompt:
        if not user.get("resume_pdf") and "resume" not in prompt.lower():
            st.error("Add a resume first. Say “update my resume” to upload one.")
        else:
            handle_prompt(user, prompt)


# ---------------------------------------------------------------- applications

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
            with top_right:
                st.badge(STATUS_LABELS.get(a["status"], "Unknown"),
                         color="green" if a["status"] == 1 else "orange")
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
            linkedin_url = st.text_input("LinkedIn", value=user.get("linkedin_url") or "")
        with col2:
            github_url = st.text_input("GitHub", value=user.get("github_url") or "")
        st.caption("Job details: the assistant shares these only when a job asks for them.")
        col3, col4, col5 = st.columns(3)
        with col3:
            current_salary = st.number_input("Current salary", value=_to_float(user.get("current_salary")),
                                             min_value=0.0, step=10000.0)
        with col4:
            expected_salary = st.number_input("Expected salary", value=_to_float(user.get("expected_salary")),
                                              min_value=0.0, step=10000.0)
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


def show_preferences_tab(user):
    st.caption("Your preferences and any extra info about you that isn't in your resume. "
               "The assistant uses this only when writing applications. Leave empty to use the defaults.")
    with st.expander("See the defaults"):
        st.code(DEFAULT_PREFERENCES, language=None, wrap_lines=True)
    with st.form("preferences_form"):
        user_prompt = st.text_area(
            "Preferences and extra info", value=user.get("user_prompt") or "", height=220, max_chars=4000,
            placeholder="e.g. I'm available to join immediately. Open to remote or Hyderabad only. "
                        "I hold an AWS Solutions Architect certification. Keep emails under 80 words "
                        "and end with 'Thanks,' instead of 'Best regards,'.",
        )
        col1, col2 = st.columns([1, 1])
        saved = col1.form_submit_button("Save preferences", type="primary")
        reset = col2.form_submit_button("Reset to default")
    if saved or reset:
        with st.spinner("Saving..."):
            update_user_prompt(user["user_id"], None if reset else (user_prompt.strip() or None))
            refresh_user(user["user_id"])
        st.toast("Preferences saved" if saved else "Reset to defaults", icon="✅")
        st.rerun()


def show_profile(user):
    st.header("Profile")
    details_tab, preferences_tab, resume_tab, security_tab = st.tabs(["Details", "Preferences", "Resume", "Security"])
    with details_tab:
        show_details_tab(user)
    with preferences_tab:
        show_preferences_tab(user)
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

with st.sidebar:
    st.markdown('<div class="brand">✉️ <span>ApplyBuddy</span></div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="user-card">
            <div class="avatar">{display_name[0].upper()}</div>
            <div class="meta"><strong>{display_name}</strong><span>{user['email']}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("New application", key="nav_new_chat", icon=":material/add:", type="primary", width="stretch"):
        reset_chat()
        st.session_state.page = "chat"
        st.rerun()
    for key, label, icon in (("chat", "Chat", ":material/chat:"),
                             ("applications", "Applications", ":material/work_history:"),
                             ("profile", "Profile", ":material/person:")):
        if st.button(label, key=f"nav_{key}", icon=icon, width="stretch",
                     type="tertiary" if st.session_state.page != key else "secondary"):
            st.session_state.page = key
            st.rerun()
    st.space("medium")
    if st.button("Log out", key="nav_logout", icon=":material/logout:", type="tertiary", width="stretch"):
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
