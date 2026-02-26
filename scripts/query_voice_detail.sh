#!/bin/bash
# 查询 noiz.ai 语音详情
# 用法: ./query_voice_detail.sh <YOUR_API_KEY> <VOICE_ID>

API_KEY="${1:?请提供 API Key，用法: $0 <YOUR_API_KEY> <VOICE_ID>}"
VOICE_ID="${2:?请提供 Voice ID，用法: $0 <YOUR_API_KEY> <VOICE_ID>}"

curl -s "https://noiz.ai/v1/voices/${VOICE_ID}" \
  -H "Authorization: ${API_KEY}" \
  -H "Accept: */*" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin), indent=2, ensure_ascii=False))"
