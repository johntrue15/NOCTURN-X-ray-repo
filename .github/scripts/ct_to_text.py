import openai
import os

def generate_text_for_records(records):
    """
    Calls OpenAI's ChatCompletion endpoint with the new library interface.
    """
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("OPENAI_API_KEY not set in environment.")

    # Build your prompt as a sequence of messages
    messages = []
    # Provide a "system" message describing the assistant’s role or style
    messages.append({
        "role": "system",
        "content": "You are a scientific assistant. Provide a short textual description for these X-ray CT records."
    })

    # Build a user message that includes the record data
    user_content_lines = []
    user_content_lines.append("Analyze the following records and provide a concise description:")
    for i, rec in enumerate(records, start=1):
        user_content_lines.append(f"\nRecord {i}:")
        user_content_lines.append(f" Title: {rec.get('title', 'N/A')}")
        user_content_lines.append(f" URL: {rec.get('detail_url', 'N/A')}")
        for key in [
            "Object",
            "Taxonomy",
            "Element or Part",
            "Data Manager",
            "Date Uploaded",
            "Publication Status",
            "Rights Statement",
            "CC License",
        ]:
            if key in rec:
                user_content_lines.append(f" {key}: {rec[key]}")
    user_content_lines.append("\nPlease summarize these CT scans focusing on species name or taxonomy.")

    user_message = "\n".join(user_content_lines)
    messages.append({"role": "user", "content": user_message})

    # Make the ChatCompletion request
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # or 'gpt-4' if you have access
        messages=messages,
        max_tokens=500,
        temperature=0.7,
    )

    # Extract the assistant’s reply
    return response.choices[0].message["content"].strip()
