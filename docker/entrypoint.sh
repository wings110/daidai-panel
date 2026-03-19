#!/bin/sh

DATA_DIR=${DATA_DIR:-/app/Dumb-Panel}

mkdir -p "${DATA_DIR}/scripts" "${DATA_DIR}/logs" "${DATA_DIR}/backups"
mkdir -p "${DATA_DIR}/deps/nodejs" "${DATA_DIR}/deps/python"

export NODE_PATH="${DATA_DIR}/deps/nodejs/node_modules"
export PATH="${DATA_DIR}/deps/nodejs/node_modules/.bin:${DATA_DIR}/deps/python/venv/bin:${PATH}"

if [ ! -d "${DATA_DIR}/deps/python/venv" ]; then
  python3 -m venv "${DATA_DIR}/deps/python/venv" 2>/dev/null || true
fi

if [ -d "${DATA_DIR}/deps/python/venv" ]; then
  export PYTHONPATH="${DATA_DIR}/deps/python/venv/lib/python3.$(python3 -c 'import sys;print(f"{sys.version_info.minor}")')/site-packages"
fi

PANEL_PORT=${PANEL_PORT:-5700}

sed -i "s/listen [0-9]*/listen ${PANEL_PORT}/" /etc/nginx/http.d/default.conf

cat > /app/config.yaml <<YAML
server:
  port: 5701
  mode: release

database:
  path: ${DATA_DIR}/daidai.db

jwt:
  secret: ""
  access_token_expire: 480h
  refresh_token_expire: 1440h

data:
  dir: ${DATA_DIR}
  scripts_dir: ${DATA_DIR}/scripts
  log_dir: ${DATA_DIR}/logs

cors:
  origins:
    - http://localhost:5173
    - http://localhost:${PANEL_PORT}
YAML

nginx

shutdown() {
    kill "$SERVER_PID" 2>/dev/null
    exit 0
}
trap shutdown SIGTERM SIGINT

while true; do
    /app/daidai-server &
    SERVER_PID=$!
    wait $SERVER_PID
    EXIT_CODE=$?
    [ $EXIT_CODE -eq 0 ] && exit 0
    sleep 2
done
