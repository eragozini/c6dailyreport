import os, smtplib, glob
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from datetime import date

host  = os.environ["SMTP_HOST"]
port  = int(os.environ["SMTP_PORT"])
user  = os.environ["SMTP_USER"]
pwd   = os.environ["SMTP_PASS"]
to    = os.environ["SMTP_TO"].split(",")

pdf   = sorted(glob.glob("out/*.pdf"))[-1]
today = date.today().strftime("%d/%m/%Y")

msg = MIMEMultipart()
msg["From"]    = user
msg["To"]      = ", ".join(to)
msg["Subject"] = f"Fechamento de Mercado — {today}"
msg.attach(MIMEText("Segue em anexo o fechamento diário de mercado. C6 Invest.", "plain", "utf-8"))

with open(pdf, "rb") as f:
    part = MIMEApplication(f.read(), _subtype="pdf")
    part.add_header("Content-Disposition", "attachment",
                    filename=f"fechamento_{today.replace('/','_')}.pdf")
    msg.attach(part)

with smtplib.SMTP(host, port) as s:
    s.starttls()
    s.login(user, pwd)
    s.sendmail(user, to, msg.as_string())

print(f"Enviado para {len(to)} destinatario(s)")