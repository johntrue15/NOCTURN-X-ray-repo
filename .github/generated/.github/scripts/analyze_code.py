import os
import sys
import subprocess
from typing import List, Tuple

def run_pylint(files: List[str]) -> Tuple[int, str]:
    """Run pylint on the given files."""
    try:
        result = subprocess.run(
            ['pylint'] + files,
            capture_output=True,
            text=True
        )
        return result.returncode, result.stdout
    except Exception as e:
        return 1, str(e)

def run_black_check(files: List[str]) -> Tuple[int, str]:
    """Check code formatting with black."""
    try:
        result = subprocess.run(
            ['black', '--check'] + files,
            capture_output=True,
            text=True
        )
        return result.returncode, result.stdout
    except Exception as e:
        return 1, str(e)

def main():
    # Get Python files in repository
    python_files = []
    for root, _, files in os.walk('.'):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))

    if not python_files:
        print("No Python files found to analyze")
        return 0

    # Run analysis
    pylint_code, pylint_output = run_pylint(python_files)
    black_code, black_output = run_black_check(python_files)

    # Print results
    print("=== Pylint Analysis ===")
    print(pylint_output)
    print("\n=== Black Format Check ===") 
    print(black_output)

    # Exit with error if either check failed
    if pylint_code != 0 or black_code != 0:
        sys.exit(1)

if __name__ == '__main__':
    main()