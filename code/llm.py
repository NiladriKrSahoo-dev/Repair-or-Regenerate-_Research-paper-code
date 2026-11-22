"""Model backends. Every call returns (text, input_tokens, output_tokens) using provider-reported usage."""
import os, re, random, time

def with_retry(fn, tries=6):
    """Exponential backoff for rate limits / transient API errors (free-tier Gemini hits 429 often)."""
    for i in range(tries):
        try: return fn()
        except Exception as e:
            code = getattr(e, "status_code", None) or getattr(e, "code", None)
            if code in (400, 401, 403, 404, 422): raise   # permanent errors: do not retry
            if i == tries - 1: raise
            time.sleep(min(60, 2 ** i * 2))

class AnthropicBackend:
    def __init__(self, model, temperature=1.0, max_output=1500):
        import anthropic
        self.client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.model, self.temperature, self.max_output = model, temperature, max_output
    def call(self, prompt):
        r = with_retry(lambda: self.client.messages.create(model=self.model, max_tokens=self.max_output,
            temperature=self.temperature, messages=[{"role": "user", "content": prompt}]))
        text = "".join(b.text for b in r.content if b.type == "text")
        return text, r.usage.input_tokens, r.usage.output_tokens

class GeminiBackend:
    """Google Gemini via the google-genai SDK. Reads GEMINI_API_KEY (or GOOGLE_API_KEY).
    Token accounting: input = prompt_token_count; output = candidates_token_count + thoughts_token_count,
    so hidden reasoning tokens are charged to the budget. thinking_budget=0 turns thinking off where the
    model allows it (not on 2.5 Pro); leave None to use the model default."""
    def __init__(self, model, temperature=1.0, max_output=1500, thinking_budget=None):
        from google import genai
        from google.genai import types
        self.types, self.client = types, genai.Client()
        self.model, self.temperature, self.max_output = model, temperature, max_output
        kw = dict(temperature=temperature, max_output_tokens=max_output)
        if thinking_budget is not None: kw["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)
        self.config = types.GenerateContentConfig(**kw)
    def call(self, prompt):
        r = with_retry(lambda: self.client.models.generate_content(model=self.model, contents=prompt, config=self.config))
        u = r.usage_metadata
        ti = (u.prompt_token_count or 0) if u else len(prompt) // 3
        to = ((u.candidates_token_count or 0) + (getattr(u, "thoughts_token_count", 0) or 0)) if u else 0
        try: text = r.text or ""
        except Exception: text = ""
        return text, ti, to

class OpenAICompatBackend:
    """Any OpenAI-compatible chat API (NVIDIA NIM, Groq, Mistral, OpenRouter, Ollama, ...)."""
    def __init__(self, model, base_url, api_key_env, temperature=1.0, max_output=1500, extra_body=None, system=None):
        from openai import OpenAI
        key = os.environ.get(api_key_env)
        if not key: raise SystemExit(f"Set the {api_key_env} environment variable first.")
        self.client = OpenAI(base_url=base_url, api_key=key)
        self.model, self.temperature, self.max_output = model, temperature, max_output
        self.extra_body, self.system = extra_body, system
    def call(self, prompt):
        msgs = ([{"role": "system", "content": self.system}] if self.system else []) + [{"role": "user", "content": prompt}]
        kw = {"extra_body": self.extra_body} if self.extra_body else {}
        r = with_retry(lambda: self.client.chat.completions.create(model=self.model, temperature=self.temperature,
            max_tokens=self.max_output, messages=msgs, **kw))
        u = r.usage
        ti = u.prompt_tokens if u else len(prompt) // 3
        to = u.completion_tokens if u else 0
        text = (r.choices[0].message.content or "") if r.choices else ""
        return text, ti, to

class MockBackend:
    """Smoke-test only. Produces plausible-looking tests, sometimes broken. NOT for real results."""
    def __init__(self, seed=0, max_output=1500):
        self.rng, self.max_output = random.Random(seed), max_output
    def call(self, prompt):
        fn = re.search(r"function `(\w+)`", prompt).group(1)
        broken = self.rng.random() < 0.5 and "Previous test" not in prompt
        body = f"from target import {fn}\n\ndef test_a():\n    assert {fn}(2, 3) == {'999' if broken else fn + '(2, 3)'}\n\ndef test_b():\n    assert {fn}(0, 0) == {fn}(0, 0)\n"
        return f"```python\n{body}```", len(prompt) // 4, len(body) // 4
