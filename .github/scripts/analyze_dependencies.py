import os
import yaml
import re
from pathlib import Path
from datetime import datetime

def parse_schedule(schedule):
    """Parse cron schedule to human readable format"""
    if not schedule:
        return None
    
    # Basic cron interpretation - can be expanded
    cron_parts = schedule[0].split()
    if len(cron_parts) != 5:
        return schedule[0]
        
    minute, hour, day_month, month, day_week = cron_parts
    
    if minute == '*/5':  # Every 5 minutes
        return "Every 5 minutes"
    elif minute == '0' and hour == '0':  # Daily at midnight
        if day_month == '*':
            return "Daily at midnight"
    elif day_month == '1':  # First day of month
        return f"Monthly on day 1 at {hour}:{minute}"
    
    # Return raw cron if no pattern matched
    return f"Cron: {schedule[0]}"

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

def analyze_workflow_triggers(workflow_content):
    """Analyze workflow triggers and dependencies"""
    triggers = {
        'schedule': None,
        'workflow_dependencies': [],
        'manual': False,
        'workflow_run_triggers': []  # Add this to track what workflows this one triggers
    }
    
    if not isinstance(workflow_content, dict) or 'on' not in workflow_content:
        return triggers
        
    on = workflow_content['on']
    
    # Check schedule - handle both commented and uncommented
    if isinstance(on, dict):
        if 'schedule' in on:
            schedule_data = on['schedule']
            if isinstance(schedule_data, list):
                for item in schedule_data:
                    if isinstance(item, dict) and 'cron' in item:
                        cron = item['cron']
                        if not cron.strip().startswith('#'):  # Check if not commented
                            triggers['schedule'] = parse_schedule([cron])
        
        # Check workflow_run triggers
        if 'workflow_run' in on:
            workflow_run = on['workflow_run']
            if isinstance(workflow_run, dict):
                workflows = workflow_run.get('workflows', [])
                if isinstance(workflows, str):
                    triggers['workflow_dependencies'].append(workflows)
                elif isinstance(workflows, list):
                    triggers['workflow_dependencies'].extend(workflows)
    
    # Check manual trigger
    if isinstance(on, dict) and 'workflow_dispatch' in on:
        triggers['manual'] = True
    elif isinstance(on, list) and 'workflow_dispatch' in on:
        triggers['manual'] = True
        
    return triggers

def analyze_workflows():
    """Analyze all workflows and their script dependencies"""
    workflows_dir = Path('.github/workflows')
    
    workflow_info = {}
    
    # Analyze each workflow file
    for workflow_file in workflows_dir.glob('*.yml'):
        with open(workflow_file, 'r') as f:
            try:
                workflow_content = yaml.safe_load(f)
                name = workflow_content.get('name', workflow_file.name)
                scripts = find_python_scripts(workflow_content)
                triggers = analyze_workflow_triggers(workflow_content)
                
                workflow_info[workflow_file.name] = {
                    'name': name,
                    'scripts': scripts,
                    'schedule': triggers['schedule'],
                    'workflow_dependencies': triggers['workflow_dependencies'],
                    'manual': triggers['manual']
                }
                
            except yaml.YAMLError as e:
                print(f"Error parsing {workflow_file}: {e}")
                
    return workflow_info

def generate_markdown(workflow_info):
    """Generate markdown documentation of dependencies"""
    lines = [
        "# Workflow Dependencies",
        "",
        "This document shows the relationships between GitHub Actions workflows and their associated Python scripts.",
        "",
        "## Scheduled Workflows",
        ""
    ]
    
    # First list scheduled workflows with their dependencies
    scheduled_workflows = {name: info for name, info in workflow_info.items() if info['schedule']}
    sorted_scheduled = sorted(scheduled_workflows.items(), 
                            key=lambda x: (x[1]['schedule'] or "", x[0]))
    
    for workflow_name, info in sorted_scheduled:
        lines.append(f"### {info['name']} (`{workflow_name}`)")
        lines.append(f"**Schedule:** {info['schedule']}")
        if info['scripts']:
            lines.append("**Required Scripts:**")
            for script in info['scripts']:
                lines.append(f"- `.github/scripts/{script}`")
        
        # Add dependent workflows as a tree
        dependent_workflows = [name for name, w_info in workflow_info.items() 
                             if workflow_name in w_info['workflow_dependencies']]
        if dependent_workflows:
            lines.append("**Triggers Workflows:**")
            for dep in sorted(dependent_workflows):
                lines.append(f"- `{dep}`")
                # Add second-level dependencies
                second_level = [name for name, w_info in workflow_info.items() 
                              if dep in w_info['workflow_dependencies']]
                for sub_dep in sorted(second_level):
                    lines.append(f"  - `{sub_dep}`")
        lines.append("")
    
    # Then list other workflows
    lines.extend([
        "## Other Workflows",
        ""
    ])
    
    other_workflows = {name: info for name, info in workflow_info.items() 
                      if not info['schedule']}
    
    for workflow_name, info in sorted(other_workflows.items()):
        lines.append(f"### {info['name']} (`{workflow_name}`)")
        if info['workflow_dependencies']:
            lines.append("**Triggered by:**")
            for dep in sorted(info['workflow_dependencies']):
                lines.append(f"- `{dep}`")
        if info['manual']:
            lines.append("**Manual trigger available**")
        if info['scripts']:
            lines.append("**Required Scripts:**")
            for script in info['scripts']:
                lines.append(f"- `.github/scripts/{script}`")
        lines.append("")
    
    # Add script to workflow mapping
    script_to_workflows = {}
    for workflow_name, info in workflow_info.items():
        for script in info['scripts']:
            if script not in script_to_workflows:
                script_to_workflows[script] = []
            script_to_workflows[script].append(workflow_name)
    
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
    workflow_info = analyze_workflows()
    
    # Generate and save markdown
    markdown = generate_markdown(workflow_info)
    with open('docs/dependencies.md', 'w') as f:
        f.write(markdown)
        
if __name__ == "__main__":
    main() 