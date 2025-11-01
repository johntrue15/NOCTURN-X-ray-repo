#!/usr/bin/env python3

import os
import sys

try:
    from openai import OpenAI
except ImportError:
    print("Error: The 'openai' library is missing.")
    sys.exit(1)

# We assume OPENAI_API_KEY is set in the GitHub Actions environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

def gather_screenshot_files(folder_path):
    """
    Returns a sorted list of PNG files from the specified folder.
    """
    if not os.path.isdir(folder_path):
        print(f"Error: '{folder_path}' is not a valid directory.")
        return []

    files = [f for f in os.listdir(folder_path) if f.lower().endswith(".png")]
    files.sort()
    return files

def generate_text_for_screenshots(screenshot_files):
    """
    Calls an OpenAI-like model to generate text based on the screenshot file names.
    """
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY is missing. Please set it in your environment."

    # Initialize the client (replace with your custom class if needed)
    client = OpenAI(api_key=OPENAI_API_KEY)

    # If no screenshots found, bail out
    if not screenshot_files:
        return "No screenshot files found."

    # Build a user prompt referencing the screenshot filenames
    user_content = [
        "Here are the filenames of several CT slice screenshots:\n"
    ]
    for f in screenshot_files:
        user_content.append(f"- {f}")

    user_content.append(
        "\nYou are a scientific writer specializing in CT imaging and morphological data. "
        "Please compose a multi-paragraph, plain-English description of what these incremental CT slice images "
        "could reveal about the specimen’s anatomy or structure. Emphasize any notable morphological features and "
        "the potential insights gained from viewing different slices in sequence. Avoid code or technical details; "
        "focus on a scientifically informed, approachable explanation."
    )

    prompt_text = "\n".join(user_content)

    try:
        # Example using a chat completion style call
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_text
                        }
                    ]
                }
            ]
        )
        return resp.choices[0].message.content.strip()

    except Exception as e:
        return f"Error calling the model: {e}"

def main():
    """
    1. Reads one argument: <screenshots_folder>
    2. Gathers the .png files
    3. Calls generate_text_for_screenshots() to get the summary text
    4. Prints the final text to stdout
    """
    if len(sys.argv) < 2:
        print("Usage: automated_slices_to_text.py <screenshots_folder>")
        sys.exit(1)

    screenshots_folder = sys.argv[1]
    if not os.path.isdir(screenshots_folder):
        print(f"Invalid folder: {screenshots_folder}")
        sys.exit(1)

    screenshot_files = gather_screenshot_files(screenshots_folder)
    final_text = generate_text_for_screenshots(screenshot_files)
    print(final_text)

if __name__ == "__main__":
    main()
