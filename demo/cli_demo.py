import asyncio
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint
import time

console = Console()
BASE_URL = "https://j8iwpsnxq1.execute-api.us-east-1.amazonaws.com/v1"

async def evaluate_action(client: httpx.AsyncClient, payload: dict) -> dict:
    try:
        response = await client.post(f"{BASE_URL}/evaluate", json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        console.print("[bold red]Error: Could not connect to AutonomyGuard server. Is it running on port 8000?[/bold red]")
        exit(1)
    except Exception as e:
        console.print(f"[bold red]Error during evaluation: {e}[/bold red]")
        exit(1)

async def resolve_approval(client: httpx.AsyncClient, approval_id: str, action: str) -> dict:
    payload = {"action": action, "reviewer_notes": f"Demo script action: {action}"}
    if action == "MODIFY":
        payload["modified_payload"] = "{'modified': true}"
    
    response = await client.post(f"{BASE_URL}/approvals/{approval_id}/action", json=payload)
    response.raise_for_status()
    return response.json()

def display_evaluation(payload: dict, result: dict, title: str):
    console.print(f"\n[bold cyan]=== {title} ===[/bold cyan]")
    
    # Payload Table
    payload_table = Table(title="Agent Action Payload", show_header=True, header_style="bold magenta")
    payload_table.add_column("Field", style="dim")
    payload_table.add_column("Value")
    for k, v in payload.items():
        payload_table.add_row(k, str(v))
    console.print(payload_table)

    # Score Breakdown Table
    breakdown = result.get("score_breakdown", {})
    score_table = Table(title="Risk Score Breakdown", show_header=True, header_style="bold yellow")
    score_table.add_column("Dimension", style="dim")
    score_table.add_column("Score")
    score_table.add_row("Reversibility", f"{breakdown.get('reversibility', 0):.2f}")
    score_table.add_row("Data Scope", f"{breakdown.get('data_scope', 0):.2f}")
    score_table.add_row("Regulatory", f"{breakdown.get('regulatory', 0):.2f}")
    score_table.add_row("Confidence Risk", f"{breakdown.get('confidence_risk', 0):.2f}")
    score_table.add_row("Raw Score", f"{breakdown.get('raw_score', 0):.2f}")
    score_table.add_row("Bias Multiplier", f"{breakdown.get('bias_multiplier', 0):.2f}")
    score_table.add_row("FINAL COMPOSITE SCORE", f"[bold cyan]{breakdown.get('final_score', 0):.3f}[/bold cyan]")
    console.print(score_table)

    # Execution Decision
    tier = result.get("execution_tier")
    color = "green" if tier == "AUTONOMOUS" else "yellow" if tier == "CONFIRM" else "red"
    
    panel = Panel.fit(
        f"Decision: [bold {color}]{tier}[/bold {color}]\nReason: {result.get('decision_reason', '')}",
        title="Routing Decision", border_style=color
    )
    console.print(panel)


async def main():
    console.clear()
    console.print(Panel.fit("[bold blue]AutonomyGuard Graduated Autonomy Engine Demo[/bold blue]", subtitle="Interactive CLI Simulation"))
    
    async with httpx.AsyncClient() as client:
        # ---------------------------------------------------------
        # Scenario 1: Low Risk (Autonomous)
        # ---------------------------------------------------------
        Prompt.ask("\n[bold green]Press Enter[/bold green] to run Scenario 1: Low Risk Query (Autonomous)...")
        payload_1 = {
            "agent_id": "demo_agent",
            "action_type": "query_db",
            "tool_name": "fetch_user_public_profile",
            "reversibility": 0.0,
            "records_affected": 1,
            "regulatory_category": "PUBLIC",
            "llm_confidence": 0.95
        }
        res_1 = await evaluate_action(client, payload_1)
        display_evaluation(payload_1, res_1, "Scenario 1: Read-Only Profile Fetch")
        time.sleep(1)

        # ---------------------------------------------------------
        # Scenario 2: High Risk (Full Review)
        # ---------------------------------------------------------
        Prompt.ask("\n[bold green]Press Enter[/bold green] to run Scenario 2: High Risk Purge (Full Review)...")
        payload_2 = {
            "agent_id": "demo_agent",
            "action_type": "bulk_delete",
            "tool_name": "purge_stale_accounts",
            "reversibility": 1.0,
            "records_affected": 10000,
            "regulatory_category": "PII",
            "llm_confidence": 0.40
        }
        res_2 = await evaluate_action(client, payload_2)
        display_evaluation(payload_2, res_2, "Scenario 2: Bulk Database Purge")
        time.sleep(1)

        # ---------------------------------------------------------
        # Scenario 3: Medium Risk (Confirm & Adaptive Loop)
        # ---------------------------------------------------------
        console.print("\n[bold magenta]=== Scenario 3: Adaptive Threshold Calibration ===[/bold magenta]")
        console.print("We will simulate a single record update. Initially, it requires CONFIRMATION.")
        console.print("You can repeatedly APPROVE it to see the risk score drop, or REJECT it to see it spike.")
        
        iteration = 1
        while True:
            Prompt.ask(f"\n[bold green]Press Enter[/bold green] to run Scenario 3 (Iteration {iteration})...")
            payload_3 = {
                "agent_id": "demo_agent",
                "action_type": "update_billing",
                "tool_name": "update_user_address",
                "reversibility": 0.5,
                "records_affected": 1,
                "regulatory_category": "INTERNAL",
                "llm_confidence": 0.70
            }
            res_3 = await evaluate_action(client, payload_3)
            display_evaluation(payload_3, res_3, f"Scenario 3: Update Billing Address (Iter {iteration})")
            
            tier = res_3.get("execution_tier")
            approval_id = res_3.get("approval_id")

            if tier == "AUTONOMOUS":
                console.print("\n[bold green]🎉 The action has achieved AUTONOMOUS status due to adaptive calibration![/bold green]")
                if not Confirm.ask("Do you want to run another iteration to see if it stays autonomous?"):
                    break
            elif tier == "FULL_REVIEW":
                console.print("\n[bold red]🚨 The action has hit FULL_REVIEW status due to past rejections![/bold red]")
                console.print(f"Approval ID {approval_id} is blocked for admin review.")
                if not Confirm.ask("Do you want to run another iteration?"):
                    break
            else:
                # CONFIRM tier
                action = Prompt.ask(
                    f"\n[bold yellow]Human-in-the-Loop Required for Approval {approval_id}[/bold yellow].\nChoose action",
                    choices=["APPROVE", "REJECT", "MODIFY"],
                    default="APPROVE"
                )
                
                resolve_res = await resolve_approval(client, approval_id, action)
                console.print(f"\n[bold green]Action '{action}' submitted![/bold green]")
                console.print(f"New Bias Multiplier for 'update_billing': [bold cyan]{resolve_res.get('updated_multiplier', 0):.3f}[/bold cyan]")
                
                if not Confirm.ask("\nRun next iteration to see the adapted score?"):
                    break
            
            iteration += 1

    console.print("\n[bold blue]Demo Complete! Thank you.[/bold blue]")

if __name__ == "__main__":
    asyncio.run(main())
