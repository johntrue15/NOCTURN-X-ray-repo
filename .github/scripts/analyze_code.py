import os
import anthropic
from pathlib import Path

def main():
    # Initialize Claude client
    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    
    # Read the generated code
    with open('.github/generated/generated_code.py', 'r') as f:
        generated_code = f.read()
    
    # Create message for Claude
    message = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=4096,
        temperature=0.7,
        system="You are a helpful AI assistant that reviews code and determines next steps. Be specific and actionable in your recommendations.",
        messages=[
            {
                "role": "user",
                "content": f"""Please analyze this generated code and provide:
1. A brief assessment of what the code currently does
2. What appears to be missing or incomplete
3. Specific next steps needed to achieve the full functionality
4. Any potential issues or improvements needed

Here's the code:

{generated_code}

Please format your response in markdown with clear sections."""
            }
        ]
    )
    
    # Save the analysis
    output_dir = Path('.github/generated')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'analysis.md', 'w') as f:
        f.write(message.content[0].text)

if __name__ == "__main__":
    main()
