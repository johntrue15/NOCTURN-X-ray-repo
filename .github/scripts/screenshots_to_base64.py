#!/usr/bin/env python3

import os
import sys
import base64

try:
    # If you're using standard openai:
    import openai
    # or if you have a custom "OpenAI" wrapper:
    # from openai import OpenAI as openai
except ImportError:
    print("Error: The 'openai' library (or a compatible library) is missing.")
    sys.exit(1)

# Ensure your OPENAI_API_KEY is set in the environment (e.g. via GitHub Actions secrets or local env)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

def gather_png_files(folder_path: str):
    """
    Returns a sorted list of all .png files in the given folder.
    """
    if not os.path.isdir(folder_path):
        print(f"Error: '{folder_path}' is not a valid directory.")
        return []
    files = [
        f for f in os.listdir(folder_path)
        if f.lower().endswith(".png")
    ]
    files.sort()
    return files

def convert_png_to_base64(filepath: str) -> str:
    """
    Reads a PNG file and returns its contents as a base64-encoded string.
    """
    with open(filepath, "rb") as f:
        file_bytes = f.read()
    return base64.b64encode(file_bytes).decode("utf-8")

def build_prompt_from_images(folder_path: str, png_files: list[str]) -> str:
    """
    Constructs a text prompt that includes each image’s filename and base64 data.
    WARNING: This can get very large if images are big, which might exceed token limits.
    """
    lines = []
    lines.append("Below are base64-encoded screenshots from a CT slice viewing process:\n")

    for filename in png_files:
        full_path = os.path.join(folder_path, filename)
        b64_str = convert_png_to_base64(full_path)

        # We only do short excerpts for demonstration. 
        # If you pass the entire base64 to a text model, it often won’t interpret it as an actual image.
        lines.append(f"Filename: {filename}")
        lines.append("Base64 data (truncated for demonstration):")
        # If you truly want to pass the entire data, skip the [0:300] slice. 
        lines.append(b64_str[:300] + " ... [truncated]" )
        lines.append("")

    # Add user instructions:
    lines.append(
        "You are a specialized model receiving raw base64 text for images. "
        "Please provide a theoretical description of what these images might show in a CT morphological context. "
        "Note: This is purely hypothetical, as text-based models cannot decode base64 images in a real sense."
    )

    return "\n".join(lines)

def call_openai_chat(prompt_text: str) -> str:
    """
    Uses the OpenAI ChatCompletion endpoint to create a response from the provided prompt.
    """
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY is missing from environment."

    # If you're using the standard `openai` package:
    openai.api_key = OPENAI_API_KEY

    try:
        completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # or "o1-mini", or whichever model you prefer
            messages=[
                {
                    "role": "user",
                    "content": prompt_text
                }
            ],
            temperature=0.7
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"Error calling OpenAI ChatCompletion: {e}"

def main():
    """
    1. Reads folder path from argv
    2. Gathers .png files and base64-encodes them
    3. Builds a prompt
    4. Calls OpenAI with that prompt
    5. Prints the response
    """
    if len(sys.argv) < 2:
        print("Usage: python screenshots_to_base64.py <screenshots_folder>")
        sys.exit(1)

    screenshots_folder = sys.argv[1]
    png_files = gather_png_files(screenshots_folder)
    if not png_files:
        print("No .png files found in the specified folder.")
        sys.exit(0)

    # Build the prompt
    prompt_text = build_prompt_from_images(screenshots_folder, png_files)

    # Call OpenAI
    response = call_openai_chat(prompt_text)
    print("---- OpenAI Response ----")
    print(response)

if __name__ == "__main__":
    main()
