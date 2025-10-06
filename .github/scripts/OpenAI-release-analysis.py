#!/usr/bin/env python3

import os
import sys
import argparse
import logging
from typing import Optional, Tuple, List, Dict
from datetime import datetime
import re

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
        # Regex to detect record entries
        self.record_pattern = re.compile(r'### ([^\n]+)')

    def parse_release_data(self, content: str) -> List[Dict[str, str]]:
        """Parse the release content into structured records."""
        records = []
        sections = content.split('### ')
        
        for section in sections[1:]:  # Skip first empty section
            try:
                lines = section.strip().split('\n')
                if not lines:
                    continue
                    
                record = {'title': lines[0].strip()}
                current_key = None
                
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                        
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip('- ').strip()
                        value = value.strip()
                        record[key] = value
                
                records.append(record)
                
            except Exception as e:
                logger.warning(f"Error parsing section: {str(e)}")
                continue
                
        return records

    def generate_prompt(self, records: List[Dict[str, str]]) -> str:
        """Generate the analysis prompt with focus on FAIR principles and NSF initiatives."""
        user_content = [
            "This week's MorphoSource data release showcases the following X-ray CT scans:\n"
        ]
        
        for i, rec in enumerate(records, 1):
            user_content.append(f"Record #{i}:")
            user_content.append(f" - Title: {rec.get('title', 'N/A')}")
            
            # Include all available fields
            for key, value in rec.items():
                if key != 'title':  # Skip title as it's already added
                    user_content.append(f" - {key}: {value}")
            
            user_content.append("")  # Blank line separator

        # Add the specialized instruction prompt
        user_content.append(
            "As a science communicator specializing in open science and digital repositories, please create an "
            "engaging weekly blog post about these MorphoSource releases. Your analysis should:\n\n"
            
            "1. Opening Context:\n"
            "- Highlight how this week's releases contribute to open science and FAIR data principles\n"
            "- Emphasize MorphoSource's role in making X-ray CT data Findable, Accessible, Interoperable, and Reusable\n\n"
            
            "2. Scientific Summary:\n"
            "- Provide a clear overview of the specimens scanned this week\n"
            "- Explain the significance of each specimen for comparative anatomy and evolutionary studies\n"
            "- Describe any notable anatomical features captured in the scans\n\n"
            
            "3. Technical Achievements:\n"
            "- Discuss the variety of specimen types and scanning approaches\n"
            "- Highlight any particularly challenging or innovative scanning techniques\n"
            "- Note the quality and completeness of the digital data\n\n"
            
            "4. Broader Impact:\n"
            "- Explain how these scans support NSF's vision for open science infrastructure\n"
            "- Describe potential research, educational, and collaborative opportunities enabled by this data\n"
            "- Emphasize how this data contributes to biodiversity research and documentation\n\n"
            
            "Format the response as an engaging blog post that would interest both researchers and the general public. "
            "Highlight specific examples from this week's releases while connecting them to broader themes of "
            "open science, digital preservation, and collaborative research."
        )
        
        return "\n".join(user_content)

    def analyze_release(self, content: str) -> Optional[Tuple[str, dict]]:
        """Analyze the release content using the o1-mini model."""
        try:
            # Parse records from the content
            records = self.parse_release_data(content)
            
            if not records:
                logger.warning("No records found to analyze")
                return None
                
            prompt = self.generate_prompt(records)
            
            response = self.client.chat.completions.create(
                model="o1-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )
            
            # Extract token usage
            usage_stats = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
            
            return response.choices[0].message.content.strip(), usage_stats
            
        except Exception as e:
            logger.error(f"Error in OpenAI API call: {str(e)}")
            return None

    def format_wiki_page(self, analysis: str, release_title: str, usage_stats: dict) -> str:
        """Format the analysis as a wiki page."""
        current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        
        # Calculate approximate cost (based on current o1-mini pricing)
        input_cost = (usage_stats['prompt_tokens'] / 1_000_000) * 3.00  # $3.00 per 1M input tokens
        output_cost = (usage_stats['completion_tokens'] / 1_000_000) * 12.00  # $12.00 per 1M output tokens
        total_cost = input_cost + output_cost
        
        wiki_content = f"""# OpenAI Weekly Analysis: {release_title}

Generated on: {current_time}

## MorphoSource Weekly Digest: Open Science and X-ray Imaging

{analysis}

---
*This analysis was automatically generated using OpenAI's o1-mini model to support NSF's FAIROS initiatives.*

**Analysis Statistics:**
- Prompt Tokens: {usage_stats['prompt_tokens']:,}
- Completion Tokens: {usage_stats['completion_tokens']:,}
- Total Tokens: {usage_stats['total_tokens']:,}
- Processing Cost: ${total_cost:.4f}
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
        result = analyzer.analyze_release(content)
        
        if not result:
            logger.error("Failed to generate analysis")
            sys.exit(1)
            
        analysis, usage_stats = result
        
        # Format and save wiki page
        wiki_content = analyzer.format_wiki_page(analysis, args.release_title, usage_stats)
        
        with open(args.output_file, 'w', encoding='utf-8') as f:
            f.write(wiki_content)
        
        logger.info(f"Successfully wrote analysis to {args.output_file}")
        logger.info(f"Token usage - Total: {usage_stats['total_tokens']}, "
                   f"Cost: ${(usage_stats['prompt_tokens'] / 1000 * 0.01 + usage_stats['completion_tokens'] / 1000 * 0.03):.4f}")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
