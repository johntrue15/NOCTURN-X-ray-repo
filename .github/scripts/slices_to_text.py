#!/usr/bin/env python3

import os
import sys

try:
    from openai import OpenAI  # or from o1_mini import OpenAI if using your custom package
except ImportError:
    print("Error: The 'openai' library (or your custom O1-mini package) is missing.")
    sys.exit(1)

# We assume you set OPENAI_API_KEY in your GitHub Actions environment
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
    Calls the 'o1-mini' (or similarly named) model via an OpenAI-like usage
    to generate text descriptions for the screenshot files.
    """
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY is missing."

    # Initialize the client
    client = OpenAI(api_key=OPENAI_API_KEY)

    # If no screenshots found, bail out
    if not screenshot_files:
        return "No screenshot files found."

    # Build a user prompt that references each screenshot filename
    user_content = [
        "Below are the filenames of several CT slice screenshots:\n"
    ]
    for f in screenshot_files:
        user_content.append(f"- {f}")

    # Add instructions for summarizing these slice images
    user_content.append(
        "\nYou are a scientific writer with expertise in imaging and morphological data. "
        "Please compose a multi-paragraph, plain-English description of what these incremental CT slice images might "
        "reveal about the specimen’s anatomy or structure. Focus on identifying notable morphological features and "
        "the significance of viewing slices at different depths. Avoid code or technical implementation details; "
        "keep the discussion to scientific interpretation and possible insights."
    )

    # Convert user_content list into the format your model expects
    prompt_text = "\n".join(user_content)

    try:
        # Using the same chat.completions.create call style
        resp = client.chat.completions.create(
            model="o1-mini",  # or whichever model you're using
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
        return f"Error calling o1-mini model: {e}"

def main():
    """
    1. Reads one argument: <screenshots_folder>
    2. Gathers all .png files in that folder
    3. Calls generate_text_for_screenshots() to produce descriptive text
    4. Prints the final text to stdout
    """
    if len(sys.argv) < 2:
        print("Usage: slices_to_text.py <screenshots_folder>")
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
