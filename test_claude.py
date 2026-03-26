import anthropic

client = anthropic.Anthropic(api_key="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")

message = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "你好，请用中文回答：1+1等于几？"}
    ]
)

print(message.content[0].text)