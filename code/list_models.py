"""Check your Gemini key works and print model names you can use with --model."""
from google import genai
for m in genai.Client().models.list():
    if "generateContent" in (getattr(m, "supported_actions", None) or []): print(m.name.replace("models/", ""))
