"""WebSocket 实时日志服务"""

import logging
from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask_jwt_extended import decode_token
from jwt.exceptions import InvalidTokenError

logger = logging.getLogger(__name__)

# 全局 SocketIO 实例
socketio = None


def init_socketio(app):
    """初始化 SocketIO"""
    global socketio

    socketio = SocketIO(
        app,
        cors_allowed_origins="*",  # 生产环境应限制为具体域名
        async_mode='eventlet',
        logger=False,
        engineio_logger=False,
    )

    # 注册事件处理器
    _register_handlers()

    logger.info("WebSocket 服务已启动")
    return socketio


def _register_handlers():
    """注册 WebSocket 事件处理器"""

    @socketio.on('connect')
    def handle_connect(auth):
        """客户端连接"""
        # 验证 JWT Token
        token = None
        if auth and isinstance(auth, dict):
            token = auth.get('token')

        if not token:
            # 尝试从查询参数获取
            token = request.args.get('token')

        if not token:
            logger.warning(f"WebSocket 连接被拒绝：缺少 token，来自 {request.remote_addr}")
            disconnect()
            return False

        try:
            # 验证 token
            decode_token(token)
            logger.info(f"WebSocket 客户端已连接：{request.sid} 来自 {request.remote_addr}")
            return True
        except InvalidTokenError as e:
            logger.warning(f"WebSocket 连接被拒绝：token 无效，来自 {request.remote_addr}，错误: {e}")
            disconnect()
            return False

    @socketio.on('disconnect')
    def handle_disconnect():
        """客户端断开连接"""
        logger.info(f"WebSocket 客户端已断开：{request.sid}")

    @socketio.on('subscribe_task_log')
    def handle_subscribe_task_log(data):
        """订阅任务日志

        data: {
            'task_id': int  # 任务 ID
        }
        """
        task_id = data.get('task_id')
        if not task_id:
            emit('error', {'message': '缺少 task_id 参数'})
            return

        room = f'task_log_{task_id}'
        join_room(room)
        logger.info(f"客户端 {request.sid} 订阅了任务 {task_id} 的日志")
        emit('subscribed', {'task_id': task_id, 'room': room})

    @socketio.on('unsubscribe_task_log')
    def handle_unsubscribe_task_log(data):
        """取消订阅任务日志

        data: {
            'task_id': int  # 任务 ID
        }
        """
        task_id = data.get('task_id')
        if not task_id:
            emit('error', {'message': '缺少 task_id 参数'})
            return

        room = f'task_log_{task_id}'
        leave_room(room)
        logger.info(f"客户端 {request.sid} 取消订阅了任务 {task_id} 的日志")
        emit('unsubscribed', {'task_id': task_id})

    @socketio.on('subscribe_system_status')
    def handle_subscribe_system_status():
        """订阅系统状态"""
        room = 'system_status'
        join_room(room)
        logger.info(f"客户端 {request.sid} 订阅了系统状态")
        emit('subscribed', {'room': room})

    @socketio.on('unsubscribe_system_status')
    def handle_unsubscribe_system_status():
        """取消订阅系统状态"""
        room = 'system_status'
        leave_room(room)
        logger.info(f"客户端 {request.sid} 取消订阅了系统状态")
        emit('unsubscribed', {'room': room})


def emit_task_log(task_id: int, log_line: str):
    """向订阅了该任务日志的客户端推送日志行

    Args:
        task_id: 任务 ID
        log_line: 日志行内容
    """
    if not socketio:
        return

    room = f'task_log_{task_id}'
    socketio.emit('task_log', {
        'task_id': task_id,
        'log': log_line,
        'timestamp': _get_timestamp(),
    }, room=room)


def emit_task_status(task_id: int, status: str, **kwargs):
    """向订阅了该任务日志的客户端推送任务状态变化

    Args:
        task_id: 任务 ID
        status: 状态（started, completed, failed, stopped）
        **kwargs: 其他状态信息
    """
    if not socketio:
        return

    room = f'task_log_{task_id}'
    data = {
        'task_id': task_id,
        'status': status,
        'timestamp': _get_timestamp(),
    }
    data.update(kwargs)

    socketio.emit('task_status', data, room=room)


def emit_system_status(cpu_percent: float, memory_percent: float, disk_percent: float):
    """向订阅了系统状态的客户端推送系统状态

    Args:
        cpu_percent: CPU 使用率
        memory_percent: 内存使用率
        disk_percent: 磁盘使用率
    """
    if not socketio:
        return

    room = 'system_status'
    socketio.emit('system_status', {
        'cpu': cpu_percent,
        'memory': memory_percent,
        'disk': disk_percent,
        'timestamp': _get_timestamp(),
    }, room=room)


def _get_timestamp():
    """获取当前时间戳（毫秒）"""
    from datetime import datetime
    return int(datetime.utcnow().timestamp() * 1000)
