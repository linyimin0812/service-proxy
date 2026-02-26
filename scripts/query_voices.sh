#!/bin/bash
# 查询 noiz.ai 语音列表
# 用法: ./query_voices.sh <YOUR_API_KEY>

API_KEY="${1:?请提供 API Key，用法: $0 <YOUR_API_KEY>}"

curl -s "https://noiz.ai/v1/voices?voice_type=built-in&skip=0&limit=100" \
  -H "Authorization: ${API_KEY}" \
  -H "Accept: */*" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2, ensure_ascii=False))"
