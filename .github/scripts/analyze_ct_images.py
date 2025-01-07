#!/usr/bin/env python3

import os
import sys

try:
    from openai import OpenAI
except ImportError:
    print("Error: The 'openai' library (or your custom O1-mini package) is missing.")
    sys.exit(1)

# We assume you set OPENAI_API_KEY in your environment
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

def get_image_paths(folder_path):
    """Get specific image file paths from the given folder."""
    valid_suffixes = {"Forward_90_Z-_Up.png", "Default_Yplus_Up.png", "Upside_Down_Y-_Up.png", "Back_90_Zplus_Up.png"}
    return [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if any(f.endswith(suffix) for suffix in valid_suffixes)
    ]

def generate_text_with_images(image_paths):
    """Pass image paths and super prompt to the o1-mini model."""
    if not OPENAI_API_KEY:
        return "Error: OPENAI_API_KEY is missing."

    # Initialize the client
    client = OpenAI(api_key=OPENAI_API_KEY)

    # Build the user prompt
    user_content = [
        "You are an advanced AI model tasked with analyzing 3D X-ray CT scan data from Morphosource.org. "
        "Below, I will describe the provided data and 3D orientation images. Your task is to extract meaningful "
        "details about the structure, material composition, and any observable anomalies or characteristics of the object. "
        "Provide a detailed textual analysis based on the images provided."
    ]

    # List images in the prompt
    user_content.append("The following images are provided:")
    for i, image_path in enumerate(image_paths, 1):
        user_content.append(f"{i}. {image_path}")

    # Add the super prompt details
    user_content.append(
        """
        Input Details:
        1. Orientation Views: The object is presented in multiple perspectives.
        2. Image Details: The 3D scans reflect internal and external structures derived from high-resolution CT imaging.

        Expected Analysis:
        - Interpret structural characteristics (e.g., fractures, voids, density distributions).
        - Highlight material inconsistencies or patterns visible across orientations.
        - Describe potential applications or implications based on observed features.
        - Summarize any limitations of the imagery or areas requiring additional focus.

        Output Format:
        Provide a detailed textual analysis structured as:
        1. General Overview
        2. Observations from each orientation
        3. Synthesis of insights
        4. Potential applications or research directions
        5. Areas for further investigation
        """
    )

    try:
        resp = client.chat.completions.create(
            model="o1-mini",
            messages=[
                {
                    "role": "user",
                    "content": "\n".join(user_content)
                }
            ]
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Error calling o1-mini model: {e}"

def main():
    """
    1. Reads a folder path containing images.
    2. Passes the images and the super prompt to the model.
    3. Prints the output.
    """
    if len(sys.argv) < 2:
        print("Usage: analyze_ct_images.py <image_folder>")
        sys.exit(1)

    folder_path = sys.argv[1]
    if not os.path.isdir(folder_path):
        print(f"Folder '{folder_path}' not found.")
        sys.exit(1)

    # Get specific image paths
    image_paths = get_image_paths(folder_path)
    if not image_paths:
        print("No valid image files found in the folder.")
        sys.exit(1)

    # Generate text with the images
    description = generate_text_with_images(image_paths)
    print(description)

if __name__ == "__main__":
    main()
