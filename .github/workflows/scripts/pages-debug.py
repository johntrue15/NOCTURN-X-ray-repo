#!/usr/bin/env python3
"""
GitHub Pages Debug Utility
--------------------------
This script helps with debugging GitHub Pages deployments by logging
detailed information about the deployment process.
"""

import os
import sys
import json
import glob
import logging
import subprocess
from datetime import datetime
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('github-pages-debug.log')
    ]
)

logger = logging.getLogger('pages-debug')

def setup_arg_parser():
    """Configure the argument parser."""
    parser = argparse.ArgumentParser(description='GitHub Pages Debug Utility')
    parser.add_argument('--data-dir', default='data', help='Directory containing release data')
    parser.add_argument('--output-dir', default='docs', help='Directory for GitHub Pages output')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--check-branches', action='store_true', help='Check GitHub branch information')
    return parser

def log_environment_info():
    """Log information about the execution environment."""
    logger.info("Environment Information:")
    logger.info(f"Python Version: {sys.version}")
    logger.info(f"Current Working Directory: {os.getcwd()}")
    
    # Log GitHub Actions environment variables if present
    github_vars = [var for var in os.environ if var.startswith('GITHUB_')]
    if github_vars:
        logger.info("GitHub Environment Variables:")
        for var in github_vars:
            # Skip potentially sensitive variables
            if var in ['GITHUB_TOKEN', 'MY_GITHUB_TOKEN', 'WORKFLOW_PAT']:
                logger.info(f"  {var}: [REDACTED]")
            else:
                logger.info(f"  {var}: {os.environ.get(var)}")
    
    # Log Git information if available
    try:
        current_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode().strip()
        logger.info(f"Current Git Branch: {current_branch}")
        
        remote_url = subprocess.check_output(["git", "config", "--get", "remote.origin.url"]).decode().strip()
        logger.info(f"Git Remote URL: {remote_url}")
        
        last_commit = subprocess.check_output(["git", "log", "-1", "--oneline"]).decode().strip()
        logger.info(f"Last Commit: {last_commit}")
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("Unable to retrieve Git information")

def check_github_branches():
    """Check GitHub branch information and log it."""
    logger.info("Checking GitHub Branch Information:")
    
    try:
        # List all branches
        branches = subprocess.check_output(["git", "branch", "-a"]).decode().strip()
        logger.info(f"Available Branches:\n{branches}")
        
        # Check if gh-pages branch exists
        try:
            gh_pages_exists = subprocess.call(["git", "show-ref", "--verify", "--quiet", "refs/heads/gh-pages"]) == 0
            logger.info(f"gh-pages Branch Exists Locally: {gh_pages_exists}")
        except subprocess.SubprocessError:
            logger.warning("Unable to check if gh-pages branch exists locally")
        
        # Check remote branches
        try:
            remote_branches = subprocess.check_output(["git", "ls-remote", "--heads", "origin"]).decode().strip()
            logger.info(f"Remote Branches:\n{remote_branches}")
            gh_pages_exists_remote = "refs/heads/gh-pages" in remote_branches
            logger.info(f"gh-pages Branch Exists Remotely: {gh_pages_exists_remote}")
        except subprocess.SubprocessError:
            logger.warning("Unable to check remote branches")
            
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("Unable to retrieve branch information")

def analyze_data_directory(data_dir):
    """Analyze the data directory structure and log information."""
    logger.info(f"Analyzing data directory: {data_dir}")
    
    # Count total number of data directories
    date_dirs = glob.glob(os.path.join(data_dir, '20*-*-*_*-*-*'))
    logger.info(f"Total release directories found: {len(date_dirs)}")
    
    # Check most recent directories
    if date_dirs:
        date_dirs.sort(reverse=True)
        logger.info(f"Most recent release directory: {date_dirs[0]}")
        
        # Check content of most recent directory
        recent_dir = date_dirs[0]
        files = os.listdir(recent_dir)
        logger.info(f"Files in most recent directory: {files}")
        
        # Examine release notes if present
        release_notes_path = os.path.join(recent_dir, 'release_notes.txt')
        if os.path.exists(release_notes_path):
            with open(release_notes_path, 'r') as f:
                notes_content = f.read()
            logger.info(f"Release notes content:\n{notes_content}")
        else:
            logger.warning(f"No release_notes.txt found in {recent_dir}")
    else:
        logger.warning(f"No release directories found in {data_dir}")

def check_github_pages_setup(output_dir):
    """Check GitHub Pages setup and log information."""
    logger.info(f"Checking GitHub Pages setup in: {output_dir}")
    
    # Check if output directory exists
    if not os.path.exists(output_dir):
        logger.warning(f"Output directory {output_dir} does not exist")
        return
    
    # Check for essential GitHub Pages files
    essential_files = ['index.md', '_config.yml']
    for file in essential_files:
        file_path = os.path.join(output_dir, file)
        if os.path.exists(file_path):
            logger.info(f"Found {file} ({os.path.getsize(file_path)} bytes)")
            
            # Log content of small files
            if os.path.getsize(file_path) < 10000:  # Only log if less than 10KB
                with open(file_path, 'r') as f:
                    content = f.read()
                logger.info(f"{file} content:\n{content}")
        else:
            logger.warning(f"Missing essential file: {file}")
    
    # Check for asset directories
    for asset_dir in ['assets', 'assets/css', 'assets/js']:
        dir_path = os.path.join(output_dir, asset_dir)
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            logger.info(f"Found asset directory: {asset_dir}")
            logger.info(f"Files in {asset_dir}: {os.listdir(dir_path)}")
        else:
            logger.warning(f"Missing asset directory: {asset_dir}")
    
    # Check GitHub Pages Configuration
    pages_config_path = os.path.join('.github', 'pages.yml')
    if os.path.exists(pages_config_path):
        logger.info(f"Found GitHub Pages configuration file: {pages_config_path}")
        with open(pages_config_path, 'r') as f:
            content = f.read()
        logger.info(f"GitHub Pages configuration content:\n{content}")
    else:
        logger.warning("No GitHub Pages configuration file found at .github/pages.yml")

def main():
    """Main function to run the GitHub Pages debug utility."""
    parser = setup_arg_parser()
    args = parser.parse_args()
    
    if args.verbose:
        # Set log level to DEBUG for more detailed logging
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    
    # Log start of debug session
    logger.info(f"Starting GitHub Pages debug session at {datetime.now().isoformat()}")
    
    # Log environment information
    log_environment_info()
    
    # Check GitHub branch information if requested
    if args.check_branches:
        check_github_branches()
    
    # Analyze data directory
    analyze_data_directory(args.data_dir)
    
    # Check GitHub Pages setup
    check_github_pages_setup(args.output_dir)
    
    # Log completion
    logger.info(f"GitHub Pages debug session completed at {datetime.now().isoformat()}")
    
    # Return summary
    print("\nDEBUG SUMMARY:")
    print(f"Log file created: github-pages-debug.log")
    print(f"Data directory analyzed: {args.data_dir}")
    print(f"GitHub Pages directory checked: {args.output_dir}")
    print("See log file for complete details.")

if __name__ == "__main__":
    main() 