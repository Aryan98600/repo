import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]
EMAIL_TO_1 = os.environ["EMAIL_TO_1"]
EMAIL_TO_2 = os.environ["EMAIL_TO_2"]

report_file = "monthly_report.txt"
if os.path.exists(report_file):
    with open(report_file, "r", encoding="utf-8") as f:
        report_text = f.read()
else:
    report_text = "Monthly update completed. No report file generated."

msg = MIMEMultipart()
msg["From"] = EMAIL_USER
msg["To"] = f"{EMAIL_TO_1}, {EMAIL_TO_2}"
msg["Subject"] = "SparcLab Monthly Publications Update Code – Auto Generated"

msg.attach(MIMEText(report_text, "plain"))

# CHECK IF FILE EXISTS BEFORE ATTACHING
attachment_file = "publications_updated.html"
if os.path.exists(attachment_file):
    with open(attachment_file, "rb") as f:
        attachment = MIMEApplication(f.read(), _subtype="html")
        attachment.add_header("Content-Disposition", "attachment", filename=attachment_file)
        msg.attach(attachment)

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASS)
    server.send_message(msg)
    server.quit()
    print("Email sent successfully.")
except Exception as e:
    print(f"Failed to send email: {e}")
