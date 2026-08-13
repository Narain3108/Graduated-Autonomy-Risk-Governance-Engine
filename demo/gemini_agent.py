import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
import google.generativeai as genai
from rich.console import Console

from autonomy_guard.sdk.decorator import AutonomyGuardClient, governed_tool

console = Console()

# We point the governance client to our local (or AWS) AutonomyGuard server.
governance_client = AutonomyGuardClient(base_url="http://localhost:8000")

@governed_tool(
    client=governance_client,
    agent_id="gemini_db_admin",
    action_type="delete_user",
    reversibility=1.0,               # Extremely irreversible
    regulatory_category="PII",       # PII data makes it very sensitive
)
async def delete_user(user_id: str) -> str:
    """Deletes a user from the database."""
    console.print(f"[bold red]Executing actual database deletion for user: {user_id}[/bold red]")
    return f"Success: Deleted user {user_id}"


async def run_agent():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]Please set GEMINI_API_KEY in your environment![/bold red]")
        return
        
    genai.configure(api_key=api_key)
    
    console.print("[bold cyan]Agent initialized. Awaiting commands...[/bold cyan]")
    
    prompt = "Please delete the user with ID 'user_992' from the system."
    console.print(f"\n[bold yellow]User Prompt:[/bold yellow] {prompt}")
    
    console.print("[dim]Sending prompt to Gemini-1.5-Flash to decide actions...[/dim]")
    
    try:
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content(
            f"You are a database admin. The user said: '{prompt}'. Should you call the delete_user tool? Answer YES or NO."
        )
        console.print(f"\n[bold green]Gemini Thought Process:[/bold green] {response.text.strip()}")
        
        if "YES" in response.text.upper():
            console.print("\n[bold magenta]Gemini Agent is attempting to execute `delete_user('user_992')`...[/bold magenta]")
            result = await delete_user("user_992")
            console.print(result)
            
    except Exception as e:
        console.print(f"\n[bold red]AutonomyGuard Intercepted the Agent![/bold red]")
        console.print(f"[bold white]{str(e)}[/bold white]")
        console.print("\n[dim]The agent is not allowed to perform this action autonomously. It requires human review in the AutonomyGuard dashboard.[/dim]")

if __name__ == "__main__":
    asyncio.run(run_agent())
