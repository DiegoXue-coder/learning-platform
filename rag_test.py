import anthropic
import PyPDF2
import os

# 读取 PDF 内容
def read_pdf(filepath):
    with open(filepath, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
    return text

# 找到文件夹里第一个 PDF
pdf_file = None
for f in os.listdir("."):
    if f.endswith(".pdf"):
        pdf_file = f
        break

print(f"读取文件: {pdf_file}")
pdf_content = read_pdf(pdf_file)

# 用 Claude 回答问题
client = anthropic.Anthropic(api_key="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")

message = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": f"以下是一份文件的内容：\n\n{pdf_content}\n\n请问：What is this document about?"
        }
    ]
)

print(message.content[0].text)
