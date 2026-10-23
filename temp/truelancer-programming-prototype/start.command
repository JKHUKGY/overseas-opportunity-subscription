#!/bin/zsh
cd "${0:A:h}"
exec python3 -m http.server 8769 --bind 127.0.0.1
