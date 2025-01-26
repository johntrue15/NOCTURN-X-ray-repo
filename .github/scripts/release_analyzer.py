#!/usr/bin/env python3

import os
import json
import sys
from datetime import datetime
from typing import List, Dict, Optional
import re
from dataclasses import dataclass
import logging
import argparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Release:
    title: str
    tag: str
    date: datetime
    author: str
    notes: str
    type: str  # e.g., 'daily_check', 'ct_analysis', etc.

class ReleaseAnalyzer:
    def __init__(self, openai_key: Optional[str] = None, anthropic_key: Optional[str] = None):
        self.openai_key = openai_key
        self.anthropic_key = anthropic_key
        self.logger = logger

    def parse_release_content(self, content: str) -> List[Release]:
        """Parse raw content into Release objects."""
        releases = []
        # First, split content into sections based on Release Details
        sections = content.split("### ")[1:]  # Skip the header section
        
        for section in sections:
            try:
                # Extract release details using regex
                title_match = re.match(r'(.*?)(?=\n|$)', section)
                tag_match = re.search(r'Tag: `?(.*?)`?\n', section)
                date_match = re.search(r'Released: (.*?) UTC', section)
                author_match = re.search(r'Author: @?(.*?)(?=\n|$)', section)
                notes_match = re.search(r'Release Notes\n(.*?)(?=(?:\n###)|$)', section, re.DOTALL)

                if title_match:  # Only require title as mandatory
                    title = title_match.group(1).strip()
                    release_type = self._determine_release_type(title)
                    
                    try:
                        date = datetime.strptime(date_match.group(1), '%B %d, %Y %H:%M') if date_match else datetime.now()
                    except ValueError as e:
                        self.logger.warning(f"Error parsing date for {title}: {e}")
                        date = datetime.now()

                    release = Release(
                        title=title,
                        tag=tag_match.group(1).strip() if tag_match else "N/A",
                        date=date,
                        author=author_match.group(1).strip() if author_match else "Unknown",
                        notes=notes_match.group(1).strip() if notes_match else "",
                        type=release_type
                    )
                    releases.append(release)
                    self.logger.info(f"Parsed release: {title}")
            except Exception as e:
                self.logger.error(f"Error parsing section: {str(e)}\nSection:\n{section[:200]}...")
                continue

        self.logger.info(f"Found {len(releases)} releases")
        return releases

    def _determine_release_type(self, title: str) -> str:
        """Determine the type of release based on its title."""
        title_lower = title.lower()
        if 'daily check' in title_lower:
            return 'daily_check'
        elif 'ct' in title_lower and ('analysis' in title_lower or 'image' in title_lower):
            return 'ct_analysis'
        elif 'error' in title_lower:
            return 'error'
        elif 'monthly' in title_lower:
            return 'monthly'
        return 'other'

    def generate_statistical_summary(self, releases: List[Release]) -> Dict:
        """Generate statistical summary of releases."""
        stats = {
            'total_releases': len(releases),
            'release_types': {},
            'authors': {},
            'time_distribution': {
                'morning': 0,    # 6-12
                'afternoon': 0,  # 12-18
                'evening': 0,    # 18-24
                'night': 0       # 0-6
            }
        }
        
        for release in releases:
            # Count release types
            stats['release_types'][release.type] = stats['release_types'].get(release.type, 0) + 1
            
            # Count authors
            stats['authors'][release.author] = stats['authors'].get(release.author, 0) + 1
            
            # Analyze time distribution
            hour = release.date.hour
            if 6 <= hour < 12:
                stats['time_distribution']['morning'] += 1
            elif 12 <= hour < 18:
                stats['time_distribution']['afternoon'] += 1
            elif 18 <= hour < 24:
                stats['time_distribution']['evening'] += 1
            else:
                stats['time_distribution']['night'] += 1
        
        return stats

    def generate_claude_prompt(self, releases: List[Release], stats: Dict) -> str:
        """Generate a prompt for Claude to analyze the releases."""
        prompt = f"""
        Analyze the following release data and generate a comprehensive weekly summary. 
        Focus on key trends, significant findings, and potential areas of interest.

        Statistical Overview:
        - Total Releases: {stats['total_releases']}
        - Release Types: {json.dumps(stats['release_types'], indent=2)}
        - Time Distribution: {json.dumps(stats['time_distribution'], indent=2)}
        - Contributing Authors: {json.dumps(stats['authors'], indent=2)}

        Key Releases to highlight:
        """
        
        # Add significant releases (e.g., non-error releases with substantial notes)
        significant_releases = [r for r in releases if r.type != 'error' and len(r.notes) > 100]
        for release in significant_releases[:5]:  # Limit to top 5
            prompt += f"\n{release.title} ({release.date.strftime('%Y-%m-%d %H:%M')})"
            prompt += f"\nKey findings: {release.notes[:200]}...\n"
        
        prompt += """
        Please analyze this data and provide:
        1. A high-level summary of the week's activities
        2. Notable trends or patterns in the data
        3. Significant findings from CT analyses and daily checks
        4. Recommendations for areas needing attention
        5. Suggestions for process improvements based on error patterns
        """
        
        return prompt

    def generate_openai_prompt(self, releases: List[Release], stats: Dict) -> str:
        """Generate a prompt for OpenAI's GPT models."""
        prompt = f"""
        You are a scientific research assistant analyzing weekly release data from a CT scanning project.
        Please analyze the following data and provide a concise but informative summary.

        Weekly Statistics:
        ```json
        {json.dumps(stats, indent=2)}
        ```

        Recent Notable Findings:
        """
        
        # Include recent significant findings
        ct_analyses = [r for r in releases if r.type == 'ct_analysis']
        for analysis in ct_analyses[:3]:
            prompt += f"\n- {analysis.title}\n  {analysis.notes[:150]}...\n"
        
        prompt += """
        Please provide:
        1. Executive summary (2-3 sentences)
        2. Key discoveries and findings
        3. Technical challenges encountered
        4. Success metrics and achievements
        5. Areas for optimization
        
        Format the response in markdown with appropriate headers and sections.
        """
        
        return prompt

def main():
    parser = argparse.ArgumentParser(description='Analyze GitHub releases and generate AI summaries')
    parser.add_argument('--openai-key', help='OpenAI API key')
    parser.add_argument('--anthropic-key', help='Anthropic API key')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    try:
        # Read input file
        with open('release_summary.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Initialize analyzer
        analyzer = ReleaseAnalyzer(
            openai_key=args.openai_key or os.getenv('OPENAI_API_KEY'),
            anthropic_key=args.anthropic_key or os.getenv('ANTHROPIC_API_KEY')
        )
        
        # Parse releases
        releases = analyzer.parse_release_content(content)
        if not releases:
            logger.warning("No releases found to analyze")
            sys.exit(1)
        
        # Generate statistics
        stats = analyzer.generate_statistical_summary(releases)
        
        # Generate prompts
        claude_prompt = analyzer.generate_claude_prompt(releases, stats)
        openai_prompt = analyzer.generate_openai_prompt(releases, stats)
        
        # Save prompts to files
        with open('claude_prompt.txt', 'w', encoding='utf-8') as f:
            f.write(claude_prompt)
        
        with open('openai_prompt.txt', 'w', encoding='utf-8') as f:
            f.write(openai_prompt)
        
        logger.info(f"Processed {len(releases)} releases")
        logger.info("Generated AI prompts in claude_prompt.txt and openai_prompt.txt")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
