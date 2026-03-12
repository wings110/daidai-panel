"""WSGI 入口"""

import os
from app import create_app
from app.services.scheduler import init_scheduler

app = create_app()

# 启动调度器（迁移时可能因新列不存在而失败，容错处理）
# 注意：只在主进程中初始化，避免 Flask reloader 导致重复初始化
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true' or not app.debug:
    try:
        init_scheduler(app)
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning(f"调度器初始化跳过: {_e}")

if __name__ == "__main__":
    # 使用 SocketIO 运行（支持 WebSocket）
    port = int(os.getenv("PORT", 7100))
    socketio = getattr(app, 'socketio', None)
    if socketio:
        socketio.run(app, host="0.0.0.0", port=port, debug=False)
    else:
        app.run(host="0.0.0.0", port=port, debug=False)
