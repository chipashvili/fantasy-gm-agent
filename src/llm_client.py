import os

def generate_completion(prompt: str) -> str:
    """
    Tries to generate a completion using Gemini (default), Anthropic, or OpenAI.
    Expects prompt to instruct the model to return JSON.
    """
    gemini_key = os.environ.get("GEMINI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if gemini_key:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=gemini_key)
        res = client.models.generate_content(
            model="gemini-3.7-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        return res.text.strip().strip("```json").strip("```").strip()
    
    elif anthropic_key:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}]
        )
        # Claude sometimes returns conversational text, but since we asked for JSON, we extract it.
        text = message.content[0].text
        return text.strip().strip("```json").strip("```").strip()
        
    elif openai_key:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content
        return text.strip().strip("```json").strip("```").strip()
        
    else:
        raise Exception("No API key found for Gemini, Anthropic, or OpenAI.")
