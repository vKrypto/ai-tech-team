import smtplib
from email.message import EmailMessage

from . import formatting
from .base import Channel, as_list


class EmailChannel(Channel):
    type = "email"
    required = ("host", "from", "to")

    def send(self, n: dict) -> None:
        msg = EmailMessage()
        msg["Subject"] = n["title"]
        msg["From"] = self.config["from"]
        msg["To"] = ", ".join(as_list(self.config["to"]))
        msg.set_content(formatting.text(n, with_title=False))
        port = int(self.config.get("port") or 587)
        cls = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        with cls(self.config["host"], port, timeout=20) as smtp:
            if cls is smtplib.SMTP and str(self.config.get("starttls", "true")).lower() == "true":
                smtp.starttls()
            if self.config.get("username"):
                smtp.login(self.config["username"], self.config.get("password") or "")
            smtp.send_message(msg)
