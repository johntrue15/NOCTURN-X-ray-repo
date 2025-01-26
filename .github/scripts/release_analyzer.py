#!/usr/bin/env python3

# Create this as a patch file to update parts of your release_analyzer.py
def parse_release_content(self, content: str) -> List[Release]:
    """Parse raw content into Release objects."""
    releases = []
    # Split content by release entries - looking for ### as section marker
    release_sections = re.split(r'\n(?=### )', content)
    
    for section in release_sections:
        if not section.strip() or not section.startswith('###'):
            continue
            
        try:
            # Extract release details using more tolerant regex patterns
            title_match = re.search(r'### (.*?)(?=\n|$)', section)
            tag_match = re.search(r'Tag: `?(.*?)`?\n', section)
            date_match = re.search(r'Released: (.*?) UTC', section)
            author_match = re.search(r'Author: @?(.*?)(?=\n|$)', section)
            notes_match = re.search(r'Release Notes\n(.*?)(?=(?:\n### )|$)', section, re.DOTALL)
            
            if title_match:  # Only require title as mandatory
                release_type = self._determine_release_type(title_match.group(1))
                
                release = Release(
                    title=title_match.group(1).strip(),
                    tag=tag_match.group(1).strip() if tag_match else "N/A",
                    date=datetime.strptime(date_match.group(1), '%B %d, %Y %H:%M') if date_match else datetime.now(),
                    author=author_match.group(1).strip() if author_match else "Unknown",
                    notes=notes_match.group(1).strip() if notes_match else "",
                    type=release_type
                )
                releases.append(release)
                self.logger.info(f"Parsed release: {release.title}")
        except Exception as e:
            self.logger.error(f"Error parsing release section: {str(e)}\nSection content:\n{section[:200]}...")
            continue
    
    self.logger.info(f"Found {len(releases)} releases in content")
    return releases
