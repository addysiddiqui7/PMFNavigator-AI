import os
import sys
import argparse
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from pipeline import PMFResearchPipeline

# Reconfigure stdout to use UTF-8 encoding on Windows to prevent UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

console = Console()



def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Product Market Fit (PMF) Research System")
    parser.add_argument(
        "--query", 
        type=str, 
        default="Evaluate the wireless earbuds market and next-gen earbuds innovation opportunities",
        help="The product category or research topic to analyze."
    )
    parser.add_argument(
        "--data", 
        type=str, 
        default=None,
        help="Optional path to a file or folder of documents/datasets (CSV, XLSX, PDF, DOCX)."
    )
    parser.add_argument(
        "--csv", 
        type=str, 
        default=None,
        help="Legacy alias for --data (kept for backward compatibility)."
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["fast", "deep"],
        default="fast",
        help="Research mode: 'fast' runs a single comprehensive web search; 'deep' runs three sequential targeted/detailed searches."
    )
    args = parser.parse_args()

    # Resolve data path from --data or --csv (legacy)
    data_path = args.data if args.data is not None else args.csv
    
    # Handle explicit 'none' values
    if data_path and data_path.lower() == 'none':
        data_path = None


    # Validate data path existence
    if data_path:
        if not os.path.exists(data_path):
            console.print(f"[bold yellow]Warning: Data path '{data_path}' not found. Defaulting to Search Grounding only.[/bold yellow]\n")
            data_path = None

    # Run the multi-agent pipeline
    pipeline = PMFResearchPipeline()
    report, topic_slug = pipeline.run(args.query, data_path, mode=args.mode)
    # Ensure the reports folder exists
    reports_dir = "reports"
    os.makedirs(reports_dir, exist_ok=True)

    # Save the final report to a local Markdown file named dynamically with date and time to prevent overwriting
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_filename = os.path.join(reports_dir, f"{topic_slug}_market_research_report_{timestamp}.md")

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(report)
        
    console.print(Panel.fit(
        f"[bold green]Success![/bold green] Report saved to: [underline]{output_filename}[/underline]",
        border_style="green"
    ))

    # Print the report output cleanly in the terminal using Rich Markdown
    console.print("\n" + "="*80)
    console.print("FINAL BUSINESS REPORT OUTLINE")
    console.print("="*80 + "\n")
    console.print(Markdown(report))

if __name__ == "__main__":
    main()
