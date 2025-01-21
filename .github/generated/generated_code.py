```python
import os
from github import Github

# Initialize GitHub API
g = Github(os.environ.get('GITHUB_TOKEN'))
repo = g.get_repo('your-repo/your-repo')

# Define reaction counts thresholds
EYES_THRESHOLD = 0
HEART_THRESHOLD = 0
ROCKET_THRESHOLD = 0

def get_reaction_counts(release):
    eyes_count = release.get_reactions('+1').count
    heart_count = release.get_reactions('heart').count
    rocket_count = release.get_reactions('rocket').count
    return eyes_count, heart_count, rocket_count

def process_release(release):
    eyes_count, heart_count, rocket_count = get_reaction_counts(release)

    if eyes_count > EYES_THRESHOLD:
        # Needs major review
        new_prompt = "Researchers indicated that there may be hallucinations or factual issues. Please re-check the following data and ensure it aligns with official records."
        # Queue up new prompt for review

    elif heart_count > eyes_count and rocket_count == 0:
        # Decent, minor errors
        # Incorporate feedback for minor improvements

    elif rocket_count > ROCKET_THRESHOLD and eyes_count == 0:
        # Excellent
        # Store configuration for future reference or minimal adjustments

    # Update release with new status or instructions

# Iterate over releases and process each one
for release in repo.get_releases():
    process_release(release)
```

This code uses the PyGitHub library to interact with the GitHub API. It defines functions to get reaction counts for a release and process the release based on the counts. The `process_release` function checks the reaction counts against the defined thresholds and takes appropriate actions based on the comment instructions.

Note: You'll need to replace `'your-repo/your-repo'` with the actual name of your repository, and set the `GITHUB_TOKEN` environment variable with a valid GitHub personal access token.