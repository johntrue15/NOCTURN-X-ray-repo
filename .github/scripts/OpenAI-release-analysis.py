#!/usr/bin/env python3

import os
import sys
import argparse
import logging
from typing import Optional
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    print("Error: The 'openai' library is missing.")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ReleaseAnalyzer:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def generate_prompt(self, content: str) -> str:
        """Generate the prompt for OpenAI analysis."""
        return f"""As a scientific writer and data analyst, please analyze the following release data and create a comprehensive summary in the style of an academic blog post. Focus on:

1. Key findings and patterns in the release
2. Notable technical achievements or milestones
3. Implications for scientific research and data collection
4. Quality and completeness of the documented information
5. Suggestions for future improvements or areas of focus

Format the response as a well-structured academic blog post with clear sections and insights.

Here is the release content to analyze:

{content}
"""

    def analyze_release(self, content: str) -> Optional[str]:
        """
        Analyze the release content using OpenAI API.
        Returns formatted analysis or None if error occurs.
        """
        try:
            prompt = self.generate_prompt(content)
            
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",  # Using latest GPT-4 model
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,  # Balanced between creativity and consistency
                max_tokens=2000   # Allowing for detailed analysis
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error in OpenAI API call: {str(e)}")
            return None

    def format_wiki_page(self, analysis: str, release_title: str) -> str:
        """Format the analysis as a wiki page."""
        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        
        wiki_content = f"""# OpenAI Analysis: {release_title}

Generated on: {current_time}

## Analysis Summary

{analysis}

---
*This analysis was automatically generated using OpenAI's GPT-4 model.*
"""
        return wiki_content

def main():
    parser = argparse.ArgumentParser(description='Analyze release content using OpenAI')
    parser.add_argument('--input-file', required=True, help='Path to the release content file')
    parser.add_argument('--output-file', required=True, help='Path to save the wiki output')
    parser.add_argument('--release-title', required=True, help='Title of the release being analyzed')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Get API key from environment
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable is required")
        sys.exit(1)
    
    try:
        # Read input file
        with open(args.input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Initialize analyzer and process content
        analyzer = ReleaseAnalyzer(api_key)
        analysis = analyzer.analyze_release(content)
        
        if not analysis:
            logger.error("Failed to generate analysis")
            sys.exit(1)
        
        # Format and save wiki page
        wiki_content = analyzer.format_wiki_page(analysis, args.release_title)
        
        with open(args.output_file, 'w', encoding='utf-8') as f:
            f.write(wiki_content)
        
        logger.info(f"Successfully wrote analysis to {args.output_file}")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
