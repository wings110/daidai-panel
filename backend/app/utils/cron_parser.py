"""Cron 表达式解析器 - 支持 5 位和 6 位表达式"""

import re
from typing import Optional, Tuple


class CronParser:
    """Cron 表达式解析器

    支持格式：
    - 5 位：分 时 日 月 周（标准 Cron）
    - 6 位：秒 分 时 日 月 周（扩展 Cron，参考青龙）
    """

    # 字段范围
    RANGES = {
        'second': (0, 59),
        'minute': (0, 59),
        'hour': (0, 23),
        'day': (1, 31),
        'month': (1, 12),
        'weekday': (0, 6),  # 0=周日, 6=周六
    }

    # 月份名称映射
    MONTH_NAMES = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    }

    # 星期名称映射
    WEEKDAY_NAMES = {
        'sun': 0, 'mon': 1, 'tue': 2, 'wed': 3,
        'thu': 4, 'fri': 5, 'sat': 6,
    }

    @classmethod
    def parse(cls, expression: str) -> Tuple[bool, str, dict]:
        """解析 Cron 表达式

        返回: (是否成功, 错误信息, 解析结果)
        解析结果格式: {
            'has_second': bool,  # 是否包含秒字段
            'second': str,
            'minute': str,
            'hour': str,
            'day': str,
            'month': str,
            'weekday': str,
        }
        """
        expression = expression.strip()
        if not expression:
            return False, "Cron 表达式不能为空", {}

        # 分割字段
        fields = expression.split()

        # 判断是 5 位还是 6 位
        if len(fields) == 5:
            # 5 位：分 时 日 月 周
            has_second = False
            minute, hour, day, month, weekday = fields
            second = '0'  # 默认在 0 秒执行
        elif len(fields) == 6:
            # 6 位：秒 分 时 日 月 周
            has_second = True
            second, minute, hour, day, month, weekday = fields
        else:
            return False, f"Cron 表达式字段数量错误，应为 5 或 6 个字段，实际为 {len(fields)} 个", {}

        # 验证每个字段
        field_names = ['second', 'minute', 'hour', 'day', 'month', 'weekday']
        field_values = [second, minute, hour, day, month, weekday]

        for i, (name, value) in enumerate(zip(field_names, field_values)):
            # 跳过秒字段验证（如果是 5 位表达式）
            if not has_second and name == 'second':
                continue

            valid, error = cls._validate_field(name, value)
            if not valid:
                return False, f"{name} 字段错误: {error}", {}

        return True, "", {
            'has_second': has_second,
            'second': second,
            'minute': minute,
            'hour': hour,
            'day': day,
            'month': month,
            'weekday': weekday,
        }

    @classmethod
    def _validate_field(cls, field_name: str, value: str) -> Tuple[bool, str]:
        """验证单个字段"""
        if not value:
            return False, "字段值不能为空"

        # 特殊字符：* ? L W #
        if value in ('*', '?'):
            return True, ""

        # L（最后一天/最后一个星期几）
        if 'L' in value:
            if field_name not in ('day', 'weekday'):
                return False, "L 只能用于日期或星期字段"
            return True, ""

        # W（最近的工作日）
        if 'W' in value:
            if field_name != 'day':
                return False, "W 只能用于日期字段"
            return True, ""

        # #（第几个星期几）
        if '#' in value:
            if field_name != 'weekday':
                return False, "# 只能用于星期字段"
            return True, ""

        # 范围检查
        min_val, max_val = cls.RANGES[field_name]

        # 处理逗号分隔的多个值
        if ',' in value:
            for part in value.split(','):
                valid, error = cls._validate_single_value(field_name, part, min_val, max_val)
                if not valid:
                    return False, error
            return True, ""

        # 处理单个值
        return cls._validate_single_value(field_name, value, min_val, max_val)

    @classmethod
    def _validate_single_value(cls, field_name: str, value: str, min_val: int, max_val: int) -> Tuple[bool, str]:
        """验证单个值（可能包含范围或步长）"""
        # 步长：*/5 或 1-10/2
        if '/' in value:
            parts = value.split('/')
            if len(parts) != 2:
                return False, "步长格式错误"

            range_part, step_part = parts

            # 验证步长值
            try:
                step = int(step_part)
                if step <= 0:
                    return False, "步长必须大于 0"
            except ValueError:
                return False, "步长必须是数字"

            # 验证范围部分
            if range_part == '*':
                return True, ""

            # 验证范围
            if '-' in range_part:
                return cls._validate_range(field_name, range_part, min_val, max_val)

            # 验证单个数字
            return cls._validate_number(field_name, range_part, min_val, max_val)

        # 范围：1-10
        if '-' in value:
            return cls._validate_range(field_name, value, min_val, max_val)

        # 单个数字
        return cls._validate_number(field_name, value, min_val, max_val)

    @classmethod
    def _validate_range(cls, field_name: str, value: str, min_val: int, max_val: int) -> Tuple[bool, str]:
        """验证范围"""
        parts = value.split('-')
        if len(parts) != 2:
            return False, "范围格式错误"

        start_str, end_str = parts

        # 验证起始值
        valid, error, start = cls._parse_number(field_name, start_str, min_val, max_val)
        if not valid:
            return False, f"范围起始值错误: {error}"

        # 验证结束值
        valid, error, end = cls._parse_number(field_name, end_str, min_val, max_val)
        if not valid:
            return False, f"范围结束值错误: {error}"

        # 检查范围顺序
        if start > end:
            return False, f"范围起始值 {start} 不能大于结束值 {end}"

        return True, ""

    @classmethod
    def _validate_number(cls, field_name: str, value: str, min_val: int, max_val: int) -> Tuple[bool, str]:
        """验证单个数字"""
        valid, error, _ = cls._parse_number(field_name, value, min_val, max_val)
        return valid, error

    @classmethod
    def _parse_number(cls, field_name: str, value: str, min_val: int, max_val: int) -> Tuple[bool, str, Optional[int]]:
        """解析数字（支持名称映射）

        返回: (是否成功, 错误信息, 数字值)
        """
        value = value.strip().lower()

        # 尝试名称映射
        if field_name == 'month' and value in cls.MONTH_NAMES:
            num = cls.MONTH_NAMES[value]
            return True, "", num

        if field_name == 'weekday' and value in cls.WEEKDAY_NAMES:
            num = cls.WEEKDAY_NAMES[value]
            return True, "", num

        # 尝试解析数字
        try:
            num = int(value)
        except ValueError:
            return False, f"无效的数字: {value}", None

        # 检查范围
        if num < min_val or num > max_val:
            return False, f"数字 {num} 超出范围 [{min_val}, {max_val}]", None

        return True, "", num

    @classmethod
    def to_apscheduler_trigger(cls, expression: str) -> Optional[dict]:
        """转换为 APScheduler CronTrigger 参数

        返回: CronTrigger 参数字典，如果解析失败返回 None
        """
        valid, error, result = cls.parse(expression)
        if not valid:
            return None

        trigger_kwargs = {
            'minute': result['minute'],
            'hour': result['hour'],
            'day': result['day'],
            'month': result['month'],
            'day_of_week': result['weekday'],
        }

        # 如果有秒字段，添加秒参数
        if result['has_second']:
            trigger_kwargs['second'] = result['second']

        return trigger_kwargs

    @classmethod
    def get_description(cls, expression: str) -> str:
        """获取 Cron 表达式的人类可读描述"""
        valid, error, result = cls.parse(expression)
        if not valid:
            return f"无效的表达式: {error}"

        parts = []

        # 秒
        if result['has_second']:
            parts.append(cls._describe_field('秒', result['second']))

        # 分
        parts.append(cls._describe_field('分', result['minute']))

        # 时
        parts.append(cls._describe_field('时', result['hour']))

        # 日
        parts.append(cls._describe_field('日', result['day']))

        # 月
        parts.append(cls._describe_field('月', result['month']))

        # 周
        parts.append(cls._describe_field('周', result['weekday']))

        return '，'.join(parts)

    @classmethod
    def _describe_field(cls, name: str, value: str) -> str:
        """描述单个字段"""
        if value == '*':
            return f"每{name}"
        if value == '?':
            return f"{name}不限"
        if '/' in value:
            parts = value.split('/')
            if parts[0] == '*':
                return f"每 {parts[1]} {name}"
            return f"{parts[0]} 开始每 {parts[1]} {name}"
        if '-' in value:
            parts = value.split('-')
            return f"{name} {parts[0]}-{parts[1]}"
        if ',' in value:
            return f"{name} {value}"
        return f"{name} {value}"


def validate_cron_expression(expression: str) -> Tuple[bool, str]:
    """验证 Cron 表达式（供 API 使用）

    返回: (是否有效, 错误信息)
    """
    valid, error, _ = CronParser.parse(expression)
    return valid, error
