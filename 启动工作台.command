#!/bin/zsh
task_root="${0:A:h}"
cd -- "$task_root" || exit 1
if /usr/bin/curl --fail --silent --max-time 2 'http://127.0.0.1:8765/api/meta' > /dev/null; then
  /usr/bin/open 'http://127.0.0.1:8765'
else
  exec "$task_root/.venv/bin/ashare-bt" ui
fi
