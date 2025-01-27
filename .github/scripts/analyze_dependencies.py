import os
import yaml
import re
from pathlib import Path
from datetime import datetime

class WorkflowLoader(yaml.SafeLoader):
    """Custom YAML loader that preserves the 'on' key"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Override the implicit resolver for 'on'
        self.yaml_implicit_resolvers = {
            k: [(tag, regexp) 
                for tag, regexp in resolvers 
                if not (tag == 'tag:yaml.org,2002:bool' and regexp.match('on'))]
            for k, resolvers in self.yaml_implicit_resolvers.items()
        }

def parse_schedule(schedule):
    """Parse cron schedule to human readable format"""
    if not schedule:
        print("No schedule to parse")
        return None
    
    print(f"Parsing schedule: {schedule}")
    cron_parts = schedule[0].split()
    print(f"Cron parts: {cron_parts}")
    
    if len(cron_parts) != 5:
        print(f"Invalid cron parts length: {len(cron_parts)}")
        return schedule[0]
        
    minute, hour, day_month, month, day_week = cron_parts
    print(f"Parsed parts: minute={minute}, hour={hour}, day_month={day_month}, month={month}, day_week={day_week}")
    
    if minute == '*/5':  # Every 5 minutes
        return "Every 5 minutes"
    elif minute == '0' and hour == '0':  # Daily at midnight
        if day_month == '*':
            print("Detected: Daily at midnight")
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
        'workflow_run_triggers': []
    }
    
    # Find the 'on' key, accounting for YAML parsing quirk
    on_key = None
    for key in workflow_content.keys():
        if str(key).lower() == 'on':
            on_key = key
            break
            
    if not on_key:
        print(f"No 'on' field found in workflow")
        return triggers
        
    on = workflow_content[on_key]
    print(f"\nAnalyzing triggers for: {workflow_content.get('name', 'unnamed')}")
    print(f"'on' content type: {type(on)}")
    print(f"'on' content: {on}")
    
    # Check schedule - handle different formats
    if isinstance(on, dict):
        if 'schedule' in on:
            schedule_data = on['schedule']
            print(f"Found schedule data type: {type(schedule_data)}")
            print(f"Found schedule data: {schedule_data}")
            # Handle list of schedules
            if isinstance(schedule_data, list):
                for item in schedule_data:
                    print(f"Checking schedule item type: {type(item)}")
                    print(f"Checking schedule item: {item}")
                    # Handle direct cron string
                    if isinstance(item, dict) and 'cron' in item:
                        cron = item['cron'].strip('"\'')  # Remove quotes
                        print(f"Found cron: {cron}")
                        if not cron.startswith('#'):  # Not commented
                            schedule = parse_schedule([cron])
                            print(f"Parsed schedule: {schedule}")
                            triggers['schedule'] = schedule
                            break
    
        # Check workflow_run triggers
        if 'workflow_run' in on:
            workflow_run = on['workflow_run']
            if isinstance(workflow_run, dict):
                workflows = workflow_run.get('workflows', [])
                if isinstance(workflows, str):
                    triggers['workflow_dependencies'].append(workflows)
                elif isinstance(workflows, list):
                    triggers['workflow_dependencies'].extend(workflows)
                print(f"Found workflow dependencies: {triggers['workflow_dependencies']}")
    
    # Check manual trigger
    if 'workflow_dispatch' in on:
        triggers['manual'] = True
        
    return triggers

def analyze_workflows():
    """Analyze all workflows and their script dependencies"""
    workflows_dir = Path('.github/workflows')
    print(f"\nLooking for workflows in: {workflows_dir.absolute()}")
    
    workflow_info = {}
    
    # Analyze each workflow file
    for workflow_file in workflows_dir.glob('*.yml'):
        print(f"\nAnalyzing workflow file: {workflow_file}")
        try:
            with open(workflow_file, 'r') as f:
                content = f.read()
                print(f"File contents:\n{content[:200]}...")
                
                # Use custom loader to handle 'on' key properly
                workflow_content = yaml.load(content, Loader=WorkflowLoader)
                if workflow_content is None:
                    print(f"Warning: Empty workflow file: {workflow_file}")
                    continue
                    
                print(f"Parsed YAML type: {type(workflow_content)}")
                print(f"Parsed YAML keys: {sorted(str(k) for k in workflow_content.keys())}")
                
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
                
        except Exception as e:
            print(f"Error processing {workflow_file}: {e}")
                
    return workflow_info

def parse_cron_frequency(cron):
    """Parse cron string to determine frequency in minutes"""
    parts = cron.strip().split()
    if len(parts) != 5:
        return float('inf')  # Invalid cron returns lowest priority
        
    minute, hour, day_month, month, day_week = parts
    
    # Calculate frequency in minutes
    if minute.startswith('*/'):
        # Every X minutes
        try:
            return int(minute[2:])  # */5 -> 5 minutes
        except ValueError:
            return float('inf')
            
    elif minute == '0':
        if hour == '*':
            return 60  # Every hour
        elif hour == '0':
            if day_month == '*':
                return 1440  # Daily
            elif day_month == '1':
                return 43200  # Monthly (approx 30 days)
            
    # Handle special cases
    if day_week == '0' and minute == '0' and hour == '0':
        return 10080  # Weekly
        
    # Default to low priority for complex patterns
    return float('inf')

def get_schedule_priority(schedule):
    """Return a priority number for sorting schedules (lower = more frequent)"""
    if not schedule:
        return (float('inf'), '')
    
    # Extract cron pattern from schedule string
    if "Cron: " in schedule:
        cron = schedule.split("Cron: ")[1]
    else:
        # Handle human-readable formats
        if "Every 5 minutes" in schedule:
            cron = "*/5 * * * *"
        elif "Daily at midnight" in schedule:
            cron = "0 0 * * *"
        elif "Monthly" in schedule and "day 1" in schedule:
            cron = "0 0 1 * *"
        else:
            return (float('inf'), schedule)
    
    frequency = parse_cron_frequency(cron)
    return (frequency, schedule)

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
                            key=lambda x: get_schedule_priority(x[1]['schedule']))
    
    for workflow_name, info in sorted_scheduled:
        # Workflow name and schedule on separate lines
        lines.append(f"### {info['name']} (`{workflow_name}`)")
        lines.append("")
        lines.append(f"**Schedule:** {info['schedule']}")
        lines.append("")
        
        # Add direct scripts with proper spacing
        if info['scripts']:
            lines.append("**Required Scripts:**")
            for script in info['scripts']:
                lines.append(f"- `.github/scripts/{script}`")
            lines.append("")
        
        # Find workflows triggered by this one
        triggered_workflows = []
        for other_name, other_info in workflow_info.items():
            if info['name'] in other_info['workflow_dependencies']:
                triggered_workflows.append((other_name, other_info))
        
        if triggered_workflows:
            lines.append("**Triggers Workflows:**")
            for dep_name, dep_info in sorted(triggered_workflows):
                lines.append("")
                lines.append(f"- `{dep_name}`")
                if dep_info['scripts']:
                    lines.append("  Scripts:")
                    for script in dep_info['scripts']:
                        lines.append(f"  - `.github/scripts/{script}`")
                
                # Check for second-level triggers
                second_level = []
                for other_name, other_info in workflow_info.items():
                    if dep_info['name'] in other_info['workflow_dependencies']:
                        second_level.append((other_name, other_info))
                if second_level:
                    lines.append("  Triggers:")
                    for sub_name, sub_info in sorted(second_level):
                        lines.append(f"  - `{sub_name}`")
                        if sub_info['scripts']:
                            lines.append("    Scripts:")
                            for script in sub_info['scripts']:
                                lines.append(f"    - `.github/scripts/{script}`")
        lines.append("")
        lines.append("---")
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