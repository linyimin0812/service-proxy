#!/bin/bash
# noiz.ai 文本转语音
# 用法: ./text_to_speech.sh <YOUR_API_KEY> <VOICE_ID> <TEXT> [EMO_JSON]
# 示例: ./text_to_speech.sh your_key abc123 "Hello, how are you?" '{"Joy":0.8}'

API_KEY="${1:?请提供 API Key，用法: $0 <API_KEY> <VOICE_ID> <TEXT> [EMO_JSON]}"
VOICE_ID="${2:?请提供 Voice ID，用法: $0 <API_KEY> <VOICE_ID> <TEXT> [EMO_JSON]}"
TEXT="${3:?请提供文本内容，用法: $0 <API_KEY> <VOICE_ID> <TEXT> [EMO_JSON]}"
EMO="${4:-}"

CMD=(curl -s
  "https://noiz.ai/v1/text-to-speech"
  -H "Authorization: ${API_KEY}"
  -F "text=${TEXT}"
  -F "voice_id=${VOICE_ID}")

if [ -n "${EMO}" ]; then
  CMD+=(-F "emo=${EMO}")
fi

"${CMD[@]}"
