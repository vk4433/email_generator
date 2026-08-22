import smtplib
from email.message import EmailMessage

def send_email(my_email, my_password,
        recipient_email,
                subject, body ,attachments=None ):

    msg = EmailMessage()
    msg['From'] = my_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.set_content(body)
    if attachments:
        for file_name, file_data in attachments:
            msg.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=file_name)

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(my_email, my_password)
        server.send_message(msg)
