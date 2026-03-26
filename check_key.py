import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("ANTHROPIC_API_KEY")

if key:
    bad_chars = [c for c in key if ord(c) > 255]
    print("latin-1 有问题的字符:", bad_chars)
    print("ascii 有问题的字符:", [c for c in key if ord(c) > 127])
    print("key长度:", len(key))
    print("key字节表示:", key.encode('utf-8'))
else:
    print("未找到 API key，请检查 .env 文件")

