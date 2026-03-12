"""通知服务 - 支持多种推送渠道"""

import hashlib
import hmac
import json
import logging
import smtplib
import time
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.request import Request, urlopen, ProxyHandler, build_opener
from urllib.error import URLError
from urllib.parse import quote_plus

from app.models.notification import NotifyChannel
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)


def _get_proxy_handler():
    """获取代理处理器（如果配置了代理）"""
    proxy_url = SystemConfig.get("proxy_url", "").strip()
    if not proxy_url:
        return None

    # 支持 HTTP 和 SOCKS5 代理
    # 格式: http://127.0.0.1:7890 或 socks5://127.0.0.1:1080
    proxy_handler = ProxyHandler({
        "http": proxy_url,
        "https": proxy_url,
    })
    return proxy_handler


def _urlopen_with_proxy(req, timeout=10):
    """使用代理打开 URL（如果配置了代理）"""
    proxy_handler = _get_proxy_handler()
    if proxy_handler:
        opener = build_opener(proxy_handler)
        return opener.open(req, timeout=timeout)
    else:
        return urlopen(req, timeout=timeout)


def send_notification(channel: NotifyChannel, title: str, content: str) -> tuple[bool, str]:
    """发送通知，返回 (是否成功, 消息)"""
    try:
        config = json.loads(channel.config) if isinstance(channel.config, str) else channel.config
    except (json.JSONDecodeError, TypeError):
        return False, "通知渠道配置解析失败"

    handlers = {
        "webhook": _send_webhook,
        "email": _send_email,
        "telegram": _send_telegram,
        "dingtalk": _send_dingtalk,
        "wecom": _send_wecom,
        "bark": _send_bark,
        "pushplus": _send_pushplus,
        "serverchan": _send_serverchan,
        "feishu": _send_feishu,
        # 新增通知渠道（参考青龙）
        "gotify": _send_gotify,
        "pushdeer": _send_pushdeer,
        "chanify": _send_chanify,
        "igot": _send_igot,
        "pushover": _send_pushover,
        "discord": _send_discord,
        "slack": _send_slack,
        "ntfy": _send_ntfy,
    }

    handler = handlers.get(channel.type)
    if not handler:
        return False, f"不支持的通知类型: {channel.type}"

    try:
        return handler(config, title, content)
    except Exception as e:
        logger.error(f"通知发送失败 [{channel.type}]: {e}")
        return False, str(e)


def send_task_failure_notification(task_name: str, error_msg: str) -> None:
    """任务失败时向所有已启用的渠道发送通知"""
    from app.models.notification import NotifyChannel as NC
    channels = NC.query.filter_by(enabled=True).all()

    title = f"任务执行失败: {task_name}"
    content = f"任务 [{task_name}] 执行失败。\n\n错误信息:\n{error_msg[:1000]}"

    for ch in channels:
        success, msg = send_notification(ch, title, content)
        if not success:
            logger.warning(f"通知渠道 [{ch.name}] 发送失败: {msg}")


def broadcast_notification(title: str, content: str) -> None:
    """向所有已启用的通知渠道广播消息"""
    from app.models.notification import NotifyChannel as NC
    channels = NC.query.filter_by(enabled=True).all()

    for ch in channels:
        success, msg = send_notification(ch, title, content)
        if not success:
            logger.warning(f"通知渠道 [{ch.name}] 发送失败: {msg}")


# ==================== 通用 WebHook ====================

def _send_webhook(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送自定义 WebHook 通知"""
    url = config.get("url", "")
    method = config.get("method", "POST").upper()
    headers = config.get("headers", {})

    payload = json.dumps({
        "title": title,
        "content": content,
        "timestamp": time.time(),
    }, ensure_ascii=False).encode("utf-8")

    headers.setdefault("Content-Type", "application/json")

    req = Request(url, data=payload, headers=headers, method=method)
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            if resp.status < 400:
                return True, "发送成功"
            return False, f"HTTP {resp.status}"
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== 邮件 ====================

def _send_email(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送邮件通知"""
    smtp_host = config["smtp_host"]
    smtp_port = int(config.get("smtp_port", 465))
    username = config["username"]
    password = config["password"]
    to_addr = config["to"]

    msg = MIMEMultipart()
    msg["From"] = username
    msg["To"] = to_addr
    msg["Subject"] = title
    msg.attach(MIMEText(content, "plain", "utf-8"))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()

        server.login(username, password)
        server.sendmail(username, to_addr.split(","), msg.as_string())
        server.quit()
        return True, "发送成功"
    except smtplib.SMTPException as e:
        return False, f"SMTP 错误: {e}"


# ==================== Telegram ====================

def _send_telegram(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 Telegram 通知"""
    bot_token = config["bot_token"]
    chat_id = config["chat_id"]
    api_host = config.get("api_host", "api.telegram.org")

    text = f"*{title}*\n\n{content}"
    url = f"https://{api_host}/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            body = json.loads(resp.read())
            if body.get("ok"):
                return True, "发送成功"
            return False, body.get("description", "未知错误")
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== 钉钉机器人 ====================

def _send_dingtalk(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送钉钉机器人通知"""
    token = config["token"]
    secret = config.get("secret", "")

    url = f"https://oapi.dingtalk.com/robot/send?access_token={token}"

    # 加签
    if secret:
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = quote_plus(base64.b64encode(hmac_code))
        url += f"&timestamp={timestamp}&sign={sign}"

    payload = json.dumps({
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"### {title}\n\n{content}",
        },
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            body = json.loads(resp.read())
            if body.get("errcode") == 0:
                return True, "发送成功"
            return False, body.get("errmsg", "未知错误")
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== 企业微信机器人 ====================

def _send_wecom(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送企业微信机器人通知"""
    key = config["key"]
    url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={key}"

    payload = json.dumps({
        "msgtype": "markdown",
        "markdown": {
            "content": f"### {title}\n\n{content}",
        },
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            body = json.loads(resp.read())
            if body.get("errcode") == 0:
                return True, "发送成功"
            return False, body.get("errmsg", "未知错误")
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== Bark (iOS) ====================

def _send_bark(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 Bark 通知 (iOS)"""
    server = config.get("server", "https://api.day.app")
    device_key = config["device_key"]
    sound = config.get("sound", "")
    group = config.get("group", "呆呆面板")

    url = f"{server.rstrip('/')}/{device_key}"
    payload = json.dumps({
        "title": title,
        "body": content,
        "group": group,
        **({"sound": sound} if sound else {}),
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            body = json.loads(resp.read())
            if body.get("code") == 200:
                return True, "发送成功"
            return False, body.get("message", "未知错误")
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== PushPlus ====================

def _send_pushplus(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 PushPlus 通知"""
    token = config["token"]
    topic = config.get("topic", "")
    template = config.get("template", "html")
    channel = config.get("channel", "wechat")

    url = "https://www.pushplus.plus/send"
    payload = json.dumps({
        "token": token,
        "title": title,
        "content": content.replace("\n", "<br>") if template == "html" else content,
        "template": template,
        "channel": channel,
        **({"topic": topic} if topic else {}),
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            body = json.loads(resp.read())
            if body.get("code") == 200:
                return True, "发送成功"
            return False, body.get("msg", "未知错误")
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== Server 酱 ====================

def _send_serverchan(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 Server 酱通知"""
    send_key = config["send_key"]
    url = f"https://sctapi.ftqq.com/{send_key}.send"

    payload = json.dumps({
        "title": title,
        "desp": content,
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            body = json.loads(resp.read())
            if body.get("code") == 0:
                return True, "发送成功"
            return False, body.get("message", "未知错误")
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== 飞书机器人 ====================

def _send_feishu(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送飞书机器人通知"""
    webhook = config["webhook"]
    secret = config.get("secret", "")

    url = webhook

    # 飞书签名
    headers = {"Content-Type": "application/json"}
    body: dict = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "red",
            },
            "elements": [
                {"tag": "markdown", "content": content},
            ],
        },
    }

    if secret:
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), b"",
            digestmod=hashlib.sha256,
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        body["timestamp"] = timestamp
        body["sign"] = sign

    payload = json.dumps(body).encode("utf-8")

    req = Request(url, data=payload, headers=headers, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            resp_body = json.loads(resp.read())
            if resp_body.get("code") == 0 or resp_body.get("StatusCode") == 0:
                return True, "发送成功"
            return False, resp_body.get("msg", "未知错误")
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== Gotify ====================

def _send_gotify(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 Gotify 通知（参考青龙）"""
    server = config["server"].rstrip("/")
    token = config["token"]
    priority = config.get("priority", 5)

    url = f"{server}/message?token={token}"
    payload = json.dumps({
        "title": title,
        "message": content,
        "priority": priority,
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            if resp.status == 200:
                return True, "发送成功"
            return False, f"HTTP {resp.status}"
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== PushDeer ====================

def _send_pushdeer(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 PushDeer 通知（参考青龙）"""
    server = config.get("server", "https://api2.pushdeer.com")
    push_key = config["push_key"]

    url = f"{server.rstrip('/')}/message/push"
    payload = json.dumps({
        "pushkey": push_key,
        "text": title,
        "desp": content,
        "type": "markdown",
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            body = json.loads(resp.read())
            if body.get("code") == 0:
                return True, "发送成功"
            return False, body.get("error", "未知错误")
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== Chanify ====================

def _send_chanify(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 Chanify 通知（参考青龙）"""
    server = config.get("server", "https://api.chanify.net")
    token = config["token"]
    sound = config.get("sound", "")
    priority = config.get("priority", "10")

    url = f"{server.rstrip('/')}/v1/sender/{token}"
    payload = json.dumps({
        "title": title,
        "text": content,
        "sound": sound,
        "priority": priority,
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            if resp.status == 200:
                return True, "发送成功"
            return False, f"HTTP {resp.status}"
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== iGot ====================

def _send_igot(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 iGot 通知（参考青龙）"""
    push_key = config["push_key"]
    url = f"https://push.hellyw.com/{push_key}"

    payload = json.dumps({
        "title": title,
        "content": content,
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            body = json.loads(resp.read())
            if body.get("ret") == 0:
                return True, "发送成功"
            return False, body.get("errMsg", "未知错误")
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== Pushover ====================

def _send_pushover(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 Pushover 通知（参考青龙）"""
    user_key = config["user_key"]
    api_token = config["api_token"]
    priority = config.get("priority", "0")
    sound = config.get("sound", "")

    url = "https://api.pushover.net/1/messages.json"
    payload = json.dumps({
        "token": api_token,
        "user": user_key,
        "title": title,
        "message": content,
        "priority": priority,
        **({"sound": sound} if sound else {}),
    }).encode("utf-8")

    req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            body = json.loads(resp.read())
            if body.get("status") == 1:
                return True, "发送成功"
            return False, ", ".join(body.get("errors", ["未知错误"]))
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== Discord ====================

def _send_discord(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 Discord Webhook 通知（参考青龙）"""
    webhook_url = config["webhook_url"]
    username = config.get("username", "呆呆面板")
    avatar_url = config.get("avatar_url", "")

    payload = json.dumps({
        "username": username,
        "avatar_url": avatar_url,
        "embeds": [{
            "title": title,
            "description": content,
            "color": 15158332,  # 红色
        }],
    }).encode("utf-8")

    req = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            if resp.status == 204:
                return True, "发送成功"
            return False, f"HTTP {resp.status}"
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== Slack ====================

def _send_slack(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 Slack Webhook 通知（参考青龙）"""
    webhook_url = config["webhook_url"]
    channel = config.get("channel", "")
    username = config.get("username", "呆呆面板")

    payload = json.dumps({
        "username": username,
        **({"channel": channel} if channel else {}),
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": content,
                },
            },
        ],
    }).encode("utf-8")

    req = Request(webhook_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            if resp.status == 200:
                return True, "发送成功"
            return False, f"HTTP {resp.status}"
    except URLError as e:
        return False, f"请求失败: {e.reason}"


# ==================== Ntfy ====================

def _send_ntfy(config: dict, title: str, content: str) -> tuple[bool, str]:
    """发送 Ntfy 通知（参考青龙）"""
    server = config.get("server", "https://ntfy.sh")
    topic = config["topic"]
    priority = config.get("priority", "default")
    tags = config.get("tags", "")

    url = f"{server.rstrip('/')}/{topic}"
    headers = {
        "Title": title,
        "Priority": priority,
    }
    if tags:
        headers["Tags"] = tags

    req = Request(url, data=content.encode("utf-8"), headers=headers, method="POST")
    try:
        with _urlopen_with_proxy(req, timeout=10) as resp:
            if resp.status == 200:
                return True, "发送成功"
            return False, f"HTTP {resp.status}"
    except URLError as e:
        return False, f"请求失败: {e.reason}"

