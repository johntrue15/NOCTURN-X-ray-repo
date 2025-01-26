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
        # Split on section headings but keep the heading
        content_parts = content.split('## Release Details')
        if len(content_parts) < 2:
            logger.warning("Could not find Release Details section")
            return releases
            
        # Get the release details section
        release_section = content_parts[1]
        
        # Split by main release entries (###)
        release_entries = re.split(r'\n(?=### (?![#]))', release_section)
        
        for entry in release_entries:
            if not entry.strip():
                continue
                
            try:
                # Extract main release details using regex
                title_match = re.search(r'### (.*?)(?=\n|$)', entry)
                tag_match = re.search(r'Tag: `?(.*?)`?\n', entry)
                date_match = re.search(r'Released: (.*?) UTC', entry)
                author_match = re.search(r'Author: @?(.*?)(?=\n|$)', entry)
                
                # Match everything between Release Notes and the next main heading or end
                notes_match = re.search(r'Release Notes\n(.*?)(?=(?:\n### (?![#]))|$)', entry, re.DOTALL)
                
                if title_match:  # Only require title as mandatory
                    title = title_match.group(1).strip()
                    # Skip if title appears to be a subsection
                    if title.lower() in ['release notes', 'orientation views', 'structural characteristics', 
                                       'material composition', 'notable features', 'conclusion']:
                        continue
                        
                    try:
                        date = datetime.strptime(date_match.group(1), '%B %d, %Y %H:%M') if date_match else datetime.now()
                    except ValueError as e:
                        logger.warning(f"Error parsing date for {title}: {e}")
                        date = datetime.now()

                    release = Release(
                        title=title,
                        tag=tag_match.group(1).strip() if tag_match else "N/A",
                        date=date,
                        author=author_match.group(1).strip() if author_match else "Unknown",
                        notes=notes_match.group(1).strip() if notes_match else "",
                        type=self._determine_release_type(title)
                    )
                    releases.append(release)
                    logger.info(f"Parsed release: {title}")
            except Exception as e:
                logger.error(f"Error parsing release entry: {str(e)}\nEntry:\n{entry[:200]}...")
                continue
        
        logger.info(f"Found {len(releases)} releases")
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
        elif 'morphosource' in title_lower:
            return 'morphosource'
        elif 'test' in title_lower:
            return 'test'
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
        prompt = f"""Please analyze this week's releases data and provide a comprehensive summary.

Statistical Overview:
- Total Releases: {stats['total_releases']}
- Types of Releases:
{json.dumps(stats['release_types'], indent=2)}
- Time Distribution:
{json.dumps(stats['time_distribution'], indent=2)}
- Contributing Authors:
{json.dumps(stats['authors'], indent=2)}

Key Findings:
"""
        # Add CT analyses
        ct_analyses = [r for r in releases if r.type == 'ct_analysis']
        if ct_analyses:
            prompt += "\nCT Analysis Results:\n"
            for analysis in ct_analyses[:3]:  # Top 3 analyses
                prompt += f"- {analysis.title}\n"
                if analysis.notes:
                    prompt += f"  Summary: {analysis.notes[:200]}...\n"

        # Add any errors or issues
        errors = [r for r in releases if r.type == 'error']
        if errors:
            prompt += "\nIssues Encountered:\n"
            for error in errors[:3]:  # Top 3 errors
                prompt += f"- {error.title}\n"

        prompt += """
Please provide:
1. Executive Summary
   - Weekly overview and key metrics
   - Major achievements and milestones

2. Analysis of CT Scans
   - Notable findings and patterns
   - Quality and completeness of data
   - Technical insights gained

3. Operational Metrics
   - Release timing patterns
   - Process efficiency indicators
   - Team contribution analysis

4. Issues and Recommendations
   - Common error patterns
   - Suggested process improvements
   - Areas needing attention

5. Forward Planning
   - Data collection optimization
   - Quality improvement opportunities
   - Resource allocation suggestions

Format your response in a clear, structured markdown format suitable for a scientific summary.
"""
        return prompt

    def generate_openai_prompt(self, releases: List[Release], stats: Dict) -> str:
        """Generate a prompt for OpenAI's GPT models."""
        prompt = f"""You are a scientific data analyst reviewing weekly CT scan project releases.

Week Overview:
```json
{json.dumps(stats, indent=2)}
```

This Week's Highlights:
"""
        
        # Add significant findings
        ct_analyses = [r for r in releases if r.type == 'ct_analysis']
        if ct_analyses:
            prompt += "\nSignificant CT Analyses:\n"
            for analysis in ct_analyses[:3]:
                prompt += f"- {analysis.title}\n"
                if analysis.notes:
                    prompt += f"  Key Findings: {analysis.notes[:150]}...\n"

        prompt += """
Please provide a detailed analysis including:

1. Executive Summary (2-3 paragraphs)
   - Key achievements
   - Statistical highlights
   - Major findings

2. Technical Analysis
   - CT scan quality metrics
   - Data completeness assessment
   - Processing efficiency

3. Operational Insights
   - Workflow patterns
   - Resource utilization
   - Team performance

4. Recommendations
   - Process improvements
   - Quality enhancements
   - Resource optimization

Format the response in clear, scientific markdown suitable for stakeholder review.
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
