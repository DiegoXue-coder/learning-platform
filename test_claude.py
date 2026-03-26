import anthropic
import os
from dotenv import load_dotenv
load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

message = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "你好,请用中文回答:1+1等于几?"}
    ]
)

print(message.content[0].text)