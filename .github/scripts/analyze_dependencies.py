import os
import yaml
import re
from pathlib import Path

def find_python_scripts(workflow_content):
    """Extract Python script references from workflow content"""
    scripts = set()
    
    # Convert workflow to string for regex search if it's not already
    if isinstance(workflow_content, dict):
        workflow_str = yaml.dump(workflow_content)
    else:
        workflow_str = workflow_content
        
    # Look for python script patterns
    patterns = [
        r'python\s+\.github/scripts/([^\s]+\.py)',
        r'\.github/scripts/([^\s]+\.py)',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, workflow_str)
        for match in matches:
            scripts.add(match.group(1))
            
    return sorted(list(scripts))

def analyze_workflows():
    """Analyze all workflows and their script dependencies"""
    workflows_dir = Path('.github/workflows')
    scripts_dir = Path('.github/scripts')
    
    dependencies = {}
    
    # Analyze each workflow file
    for workflow_file in workflows_dir.glob('*.yml'):
        with open(workflow_file, 'r') as f:
            try:
                workflow_content = yaml.safe_load(f)
                scripts = find_python_scripts(workflow_content)
                
                if scripts:  # Only include workflows that use Python scripts
                    dependencies[workflow_file.name] = scripts
            except yaml.YAMLError as e:
                print(f"Error parsing {workflow_file}: {e}")
                
    return dependencies

def generate_markdown(dependencies):
    """Generate markdown documentation of dependencies"""
    lines = [
        "# Workflow Dependencies",
        "",
        "This document shows the relationships between GitHub Actions workflows and their associated Python scripts.",
        "",
        "## Workflows and Their Scripts",
        ""
    ]
    
    for workflow, scripts in dependencies.items():
        lines.append(f"### {workflow}")
        lines.append("**Required Scripts:**")
        for script in scripts:
            lines.append(f"- `.github/scripts/{script}`")
        lines.append("")
        
    # Add reverse lookup - scripts to workflows
    script_to_workflows = {}
    for workflow, scripts in dependencies.items():
        for script in scripts:
            if script not in script_to_workflows:
                script_to_workflows[script] = []
            script_to_workflows[script].append(workflow)
            
    lines.extend([
        "## Scripts and Their Workflows",
        "",
        "This section shows which workflows use each script:",
        ""
    ])
    
    for script in sorted(script_to_workflows.keys()):
        lines.append(f"### {script}")
        lines.append("**Used in Workflows:**")
        for workflow in sorted(script_to_workflows[script]):
            lines.append(f"- `{workflow}`")
        lines.append("")
        
    return "\n".join(lines)

def main():
    # Create docs directory if it doesn't exist
    os.makedirs('docs', exist_ok=True)
    
    # Analyze workflows
    dependencies = analyze_workflows()
    
    # Generate and save markdown
    markdown = generate_markdown(dependencies)
    with open('docs/dependencies.md', 'w') as f:
        f.write(markdown)
        
if __name__ == "__main__":
    main() 