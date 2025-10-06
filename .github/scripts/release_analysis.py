#!/usr/bin/env python3

import os
import sys
import datetime
from pathlib import Path
from github import Github
import argparse
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ReleaseInfo:
    """Class to store release information"""
    title: str
    tag: str
    created_at: datetime.datetime
    author: str
    body: str

class ReleaseAnalysis:
    def __init__(self, token: str, repository: str, wiki_dir: str):
        """Initialize the release analysis with GitHub credentials and paths."""
        self.github = Github(token)
        self.repository = repository
        self.wiki_dir = Path(wiki_dir)
        self.wiki_dir.mkdir(exist_ok=True)
        self.releases: List[ReleaseInfo] = []
        self.weekly_releases: Dict[datetime.date, List[ReleaseInfo]] = {}

    def fetch_releases(self) -> bool:
        """Fetch all releases from the repository."""
        try:
            repo = self.github.get_repo(self.repository)
            raw_releases = list(repo.get_releases())
            
            for release in raw_releases:
                info = ReleaseInfo(
                    title=release.title,
                    tag=release.tag_name,
                    created_at=release.created_at,
                    author=release.author.login if release.author else "Unknown",
                    body=release.body or ""
                )
                self.releases.append(info)
            
            # Sort releases by creation date
            self.releases.sort(key=lambda x: x.created_at, reverse=True)
            logger.info(f"Successfully fetched {len(self.releases)} releases")
            return True
            
        except Exception as e:
            logger.error(f"Error fetching releases: {str(e)}")
            return False

    def group_by_week(self) -> None:
        """Group releases by week."""
        for release in self.releases:
            # Get the start of the week (Monday)
            week_start = release.created_at.date() - datetime.timedelta(days=release.created_at.weekday())
            
            if week_start not in self.weekly_releases:
                self.weekly_releases[week_start] = []
            
            self.weekly_releases[week_start].append(release)
        
        logger.info(f"Grouped releases into {len(self.weekly_releases)} weeks")

    def generate_weekly_content(self, week_start: datetime.date, releases: List[ReleaseInfo]) -> str:
        """Generate content for a weekly release summary."""
        week_end = week_start + datetime.timedelta(days=6)
        content = f"# Release Summary for Week of {week_start.strftime('%B %d, %Y')}\n\n"
        
        # Overview section
        content += "## Overview\n"
        content += f"- Total releases this week: {len(releases)}\n"
        content += f"- Period: {week_start.strftime('%B %d')} - {week_end.strftime('%B %d, %Y')}\n\n"
        
        # Detailed release information
        content += "## Release Details\n\n"
        for release in releases:
            content += f"### {release.title}\n"
            content += f"- Tag: `{release.tag}`\n"
            content += f"- Released: {release.created_at.strftime('%B %d, %Y %H:%M UTC')}\n"
            content += f"- Author: @{release.author}\n"
            
            if release.body:
                content += "\n#### Release Notes\n"
                content += f"{release.body}\n"
            
            content += "\n"
        
        return content

    def generate_index(self) -> str:
        """Generate index page content."""
        content = "# Release Summaries Index\n\n"
        content += "This page contains links to all weekly release summaries.\n\n"
        
        # Sort weeks in reverse chronological order
        sorted_weeks = sorted(self.weekly_releases.keys(), reverse=True)
        
        for week in sorted_weeks:
            week_str = week.strftime('%Y-%m-%d')
            content += f"- [{week_str}](Releases-{week_str})\n"
        
        return content

    def write_wiki_page(self, filename: str, content: str) -> None:
        """Write content to a wiki page file."""
        try:
            file_path = self.wiki_dir / filename
            file_path.write_text(content, encoding='utf-8')
            logger.info(f"Successfully wrote {filename}")
        except Exception as e:
            logger.error(f"Error writing {filename}: {str(e)}")

    def generate_current_week_summary(self) -> Optional[str]:
        """Generate summary of the current week for AI analysis."""
        if not self.weekly_releases:
            return None
            
        latest_week = max(self.weekly_releases.keys())
        content = self.generate_weekly_content(latest_week, self.weekly_releases[latest_week])
        
        return content

    def run(self) -> bool:
        """Main execution method."""
        try:
            # Fetch and process releases
            if not self.fetch_releases():
                return False

            self.group_by_week()
            
            # Generate and write weekly pages
            for week_start, releases in self.weekly_releases.items():
                page_title = f"Releases-{week_start.strftime('%Y-%m-%d')}.md"
                content = self.generate_weekly_content(week_start, releases)
                self.write_wiki_page(page_title, content)
            
            # Generate and write index page
            index_content = self.generate_index()
            self.write_wiki_page("Release-Summaries.md", index_content)
            
            # Generate current week summary for AI analysis
            current_week = self.generate_current_week_summary()
            if current_week:
                with open('release_summary.txt', 'w', encoding='utf-8') as f:
                    f.write(current_week)
                logger.info("Generated release_summary.txt for AI analysis")
            
            return True
            
        except Exception as e:
            logger.error(f"Error in main execution: {str(e)}")
            return False

def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description='Analyze GitHub releases and generate wiki pages')
    parser.add_argument('--token', required=True, help='GitHub token')
    parser.add_argument('--repository', required=True, help='Repository in format owner/repo')
    parser.add_argument('--wiki-dir', required=True, help='Directory to write wiki files')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    analyzer = ReleaseAnalysis(args.token, args.repository, args.wiki_dir)
    success = analyzer.run()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
