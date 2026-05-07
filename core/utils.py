import google.generativeai as genai
from django.conf import settings

def get_gemini_recommendations(stats_text: str) -> str:
    try:
        # Step 1: Ensure API Key is pulled correctly from your .env via settings.py
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return "Configuration Error: API Key missing."

        genai.configure(api_key=api_key)
        
        # Step 2: Use the CURRENT 2026 stable model name
        # 'gemini-1.5-flash' is deprecated. Use 'gemini-3.1-flash-lite' for best results.
        model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

        prompt = f"""
You are an AI Sustainability Consultant for EcoTrack, a Corporate Carbon Footprint Management platform.

Analyze the following organization emission data carefully:

{stats_text}

Your task:
Provide professional, data-driven sustainability insights for the organization.

Response Format:

1. Executive Summary
- Briefly explain the organization's current carbon performance.

2. Key Insights
- Identify the highest emission source.
- Mention important emission trends.
- Highlight departments or activities contributing most to emissions.

3. Actionable Recommendations
Provide 3 practical and realistic recommendations to reduce emissions.
Recommendations must be specific to the provided data.

4. Risk Alerts
- Mention any unusual increase, overconsumption, or sustainability concern.

5. Sustainability Score
- Give a score out of 100 with a one-line justification.

Rules:
- Keep the response concise and professional.
- Use clean business language.
- Avoid generic advice.
- Do not invent data that is not provided.
- Format output using short paragraphs or bullet points.
- Maximum 300 words total.
"""
        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as exc:
        # Check if the model name itself is the issue
        if "404" in str(exc):
            return "AI Error: Model version mismatch. Please use 'gemini-3-flash' or 'gemini-3.1-flash-lite'."
        return f"AI analysis temporarily unavailable. (Error: {exc})"