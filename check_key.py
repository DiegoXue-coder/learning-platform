key = "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"
bad_chars = [c for c in key if ord(c) > 255]
print("latin-1 有问题的字符:", bad_chars)
print("ascii 有问题的字符:", [c for c in key if ord(c) > 127])
print("key长度:", len(key))
print("key字节表示:", key.encode('utf-8'))