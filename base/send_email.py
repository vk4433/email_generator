import smtplib
from email.message import EmailMessage


def send_email(my_email, my_password, recipient_email, subject, body, attachments=None):
    if not my_email or not my_password or not recipient_email:
        raise ValueError("my_email, my_password, and recipient_email are required.")

    msg = EmailMessage()
    msg["From"] = my_email
    msg["To"] = recipient_email
    msg["Subject"] = (subject or "").strip() or "No Subject"
    msg.set_content((body or "").strip())

    if attachments:
        for file_name, file_data in attachments:
            if file_name and file_data is not None:
                msg.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="octet-stream",
                    filename=file_name,
                )

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.starttls()
        server.login(my_email, my_password)
        server.send_message(msg)

