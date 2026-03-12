"""极验 GeeTest V4 服务端验证工具"""

import hmac
import hashlib
import logging
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)


def validate_geetest(lot_number: str, captcha_output: str, pass_token: str, gen_time: str) -> bool:
    """验证极验 V4 验证码

    参考 RecDemo 中的 GeetestUtil.java 实现。

    Args:
        lot_number: 流水号
        captcha_output: 验证输出
        pass_token: 验证通过标识
        gen_time: 生成时间

    Returns:
        验证是否通过
    """
    from app.models.system_config import SystemConfig

    captcha_id = SystemConfig.get("geetest_captcha_id", "")
    captcha_key = SystemConfig.get("geetest_captcha_key", "")

    if not captcha_id or not captcha_key:
        logger.warning("极验配置不完整，跳过验证")
        return True

    if not all([lot_number, captcha_output, pass_token, gen_time]):
        logger.warning("极验验证参数不完整")
        return False

    try:
        # 生成 HMAC-SHA256 签名
        sign_token = hmac.new(
            captcha_key.encode("utf-8"),
            lot_number.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # 构建请求参数
        params = urllib.parse.urlencode({
            "lot_number": lot_number,
            "captcha_output": captcha_output,
            "pass_token": pass_token,
            "gen_time": gen_time,
            "sign_token": sign_token,
        }).encode("utf-8")

        validate_url = f"http://gcaptcha4.geetest.com/validate?captcha_id={captcha_id}"

        req = urllib.request.Request(
            validate_url,
            data=params,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        with urllib.request.urlopen(req, timeout=5) as resp:
            result = resp.read().decode("utf-8")

        logger.debug("极验验证响应: %s", result)

        if '"result":"success"' in result:
            logger.info("极验验证通过")
            return True
        else:
            logger.warning("极验验证失败: %s", result)
            return False

    except Exception as e:
        logger.error("极验验证异常: %s", e)
        # 验证服务异常时放行，保证用户体验
        return True
