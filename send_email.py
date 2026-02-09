import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

EMAIL_USER = os.environ["EMAIL_USER"]
EMAIL_PASS = os.environ["EMAIL_PASS"]
EMAIL_TO_1 = os.environ["EMAIL_TO_1"]
EMAIL_TO_2 = os.environ["EMAIL_TO_2"]

with open("monthly_report.txt", "r", encoding="utf-8") as f:
    report_text = f.read()

msg = MIMEMultipart()
msg["From"] = EMAIL_USER
msg["To"] = f"{EMAIL_TO_1}, {EMAIL_TO_2}"
msg["Subject"] = "SparcLab Monthly Publications Update Code – Auto Generated"

msg.attach(MIMEText(report_text, "plain"))

# Attach updated HTML
with open("publications_updated.html", "rb") as f:
    attachment = MIMEApplication(f.read(), _subtype="html")
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename="publications_updated.html"
    )
    msg.attach(attachment)

server = smtplib.SMTP("smtp.gmail.com", 587)
server.starttls()
server.login(EMAIL_USER, EMAIL_PASS)
server.send_message(msg)
server.quit()
