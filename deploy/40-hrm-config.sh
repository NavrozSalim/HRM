#!/bin/sh
set -eu
api="${VITE_API_URL:-/api}"
escaped=$(printf '%s' "$api" | sed 's/\\/\\\\/g; s/"/\\"/g')
printf 'window.__HRM__={apiUrl:"%s"};\n' "$escaped" > /usr/share/nginx/html/config.js
