#!/usr/bin/env python3

import os
import sys
import datetime
from pathlib import Path
from github import Github
import argparse
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ReleaseAnalyzer:
    def __init__(self, token, repository, wiki_dir):
        self.github = Github(token)
        self.repository = repository
        self.wiki_dir = Path(wiki_dir)
        self.wiki_dir.mkdir(exist_ok=True)

    def get_releases(self):
        """Fetch all releases from the repository."""
        try:
            repo = self.github.get_repo(self.repository)
            releases = list(repo.get_releases())
            releases.sort(key=lambda x: x.created_at, reverse=True)
            return releases
        except Exception as e:
            logger.error(f"Error fetching releases: {str(e)}")
            return []

    def group_releases_by_week(self, releases):
        """Group releases by their week."""
        weekly_releases = {}
        for release in releases:
            week_start = release.created_at.date() - datetime.timedelta(days=release.created_at.weekday())
            if week_start not in weekly_releases:
                weekly_releases[week_start] = []
            weekly_releases[week_start].append(release)
        return weekly_releases

    def generate_release_content(self, week_start, releases):
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
            content += f"- Tag: `{release.tag_name}`\n"
            content += f"- Released: {release.created_at.strftime('%B %d, %Y %H:%M UTC')}\n"
            if hasattr(release.author, 'login'):
                content += f"- Author: @{release.author.login}\n"
            
            if release.body:
                content += "\n#### Release Notes\n"
                content += f"{release.body}\n"
            
            content += "\n"
        
        return content

    def generate_index_page(self, weekly_releases):
        """Generate index page with links to all weekly summaries."""
        content = "# Release Summaries Index\n\n"
        content += "This page contains links to all weekly release summaries.\n\n"
        
        sorted_weeks = sorted(weekly_releases.keys(), reverse=True)
        for week in sorted_weeks:
            week_str = week.strftime('%Y-%m-%d')
            content += f"- [{week_str}](Releases-{week_str})\n"
        
        return content

    def write_wiki_page(self, filename, content):
        """Write content to a wiki page file."""
        try:
            file_path = self.wiki_dir / filename
            file_path.write_text(content, encoding='utf-8')
            logger.info(f"Successfully wrote {filename}")
        except Exception as e:
            logger.error(f"Error writing {filename}: {str(e)}")

    def run(self):
        """Main execution method."""
        # Fetch and group releases
        releases = self.get_releases()
        if not releases:
            logger.warning("No releases found")
            return False

        weekly_releases = self.group_releases_by_week(releases)
        
        # Generate and write weekly pages
        for week_start, week_releases in weekly_releases.items():
            page_title = f"Releases-{week_start.strftime('%Y-%m-%d')}.md"
            content = self.generate_release_content(week_start, week_releases)
            self.write_wiki_page(page_title, content)
        
        # Generate and write index page
        index_content = self.generate_index_page(weekly_releases)
        self.write_wiki_page("Release-Summaries.md", index_content)
        
        return True

def main():
    parser = argparse.ArgumentParser(description='Analyze GitHub releases and generate wiki pages')
    parser.add_argument('--token', required=True, help='GitHub token')
    parser.add_argument('--repository', required=True, help='Repository in format owner/repo')
    parser.add_argument('--wiki-dir', required=True, help='Directory to write wiki files')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    analyzer = ReleaseAnalyzer(args.token, args.repository, args.wiki_dir)
    success = analyzer.run()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
