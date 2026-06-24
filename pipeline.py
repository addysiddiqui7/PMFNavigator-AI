import sys
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from agents import (
    BriefingAgent,
    ResearchAgent,
    CustomerVoiceAgent,
    SentimentAgent,
    MarketGapAgent,
    PMFEvaluationAgent,
    StrategyAgent,
    SWOTAnalysisAgent,
    ReportAgent
)

# Reconfigure stdout to use UTF-8 encoding on Windows to prevent UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

console = Console()

class PMFResearchPipeline:
    """
    Coordinates and drives the sequential execution of the 9-agent PMF research flow.
    """
    def __init__(self):
        self.brief_agent = BriefingAgent()
        self.research_agent = ResearchAgent()
        self.voice_agent = CustomerVoiceAgent()
        self.sentiment_agent = SentimentAgent()
        self.gap_agent = MarketGapAgent()
        self.pmf_agent = PMFEvaluationAgent()
        self.strategy_agent = StrategyAgent()
        self.swot_agent = SWOTAnalysisAgent()
        self.report_agent = ReportAgent()

    def run(self, query: str, csv_path: str = None, mode: str = "fast") -> tuple[str, str]:
        console.print(Panel.fit(
            f"[bold cyan]Starting PMF Research Pipeline (V2 - SWOT)[/bold cyan]\n"
            f"[bold white]Initial Topic Input:[/bold white] {query}\n"
            f"[bold white]Mode:[/bold white] {mode.upper()}\n"
            f"[bold white]CSV File:[/bold white] {csv_path if csv_path else 'None (Using Web Search Grounding only)'}",
            border_style="cyan"
        ))

        # Stage 1: Briefing Agent
        with console.status("[bold yellow]Stage 1/9: Briefing Agent - Generating research brief...[/bold yellow]", spinner="dots"):
            brief = self.brief_agent.generate_brief(query)
            topic_title = brief.get("topic_title", query)
            topic_slug = brief.get("topic_slug", "market_research")
            competitors = brief.get("suggested_competitors", "General Competitors")
            audience = brief.get("suggested_target_audience", "General Demographics")
            guidelines = brief.get("research_guidelines", "")

        console.print(f"[green]OK[/green] Stage 1 Complete: Research Brief Generated.")
        console.print(f"   * [bold]Topic Title[/bold]: {topic_title}")
        console.print(f"   * [bold]Topic Slug[/bold]: {topic_slug}")
        console.print(f"   * [bold]Competitors[/bold]: {competitors}")
        console.print(f"   * [bold]Audience[/bold]: {audience}\n")

        # Stage 2: Research Agent
        with console.status(f"[bold yellow]Stage 2/9: Research Agent - Initiating {mode} research...[/bold yellow]", spinner="dots") as status:
            def update_status(text):
                status.update(f"[bold yellow]{text}[/bold yellow]")
            research_out = self.research_agent.run_research(topic_title, csv_path, status_callback=update_status, mode=mode)
        console.print(f"[green]OK[/green] Stage 2 Complete: Research compiled (Mode: {mode.upper()}).")

        # Stage 3: Customer Voice Agent
        with console.status("[bold yellow]Stage 3/9: Customer Voice Agent - Extracting reviews & issues...[/bold yellow]", spinner="dots"):
            voice_out = self.voice_agent.run(
                f"Analyze the research data and extract customer opinions for query '{topic_title}':\n\n{research_out}"
            )
        console.print("[green]OK[/green] Stage 3 Complete: Customer voice extracted.")

        # Stage 4: Sentiment Agent
        with console.status("[bold yellow]Stage 4/9: Sentiment Agent - Analyzing emotional trends...[/bold yellow]", spinner="dots"):
            sentiment_out = self.sentiment_agent.run(
                f"Evaluate customer sentiments and emotional intensity based on customer feedback:\n\n{voice_out}"
            )
        console.print("[green]OK[/green] Stage 4 Complete: Sentiment and emotional patterns mapped.")

        # Stage 5: Market Gap Agent
        with console.status("[bold yellow]Stage 5/9: Market Gap Agent - Finding unmet needs...[/bold yellow]", spinner="dots"):
            gap_out = self.gap_agent.run(
                f"Discover product opportunities and market gaps using customer feedback and sentiments:\n\n"
                f"--- Customer Voice ---\n{voice_out}\n\n--- Sentiment Analysis ---\n{sentiment_out}"
            )
        console.print("[green]OK[/green] Stage 5 Complete: Market gaps identified.")

        # Stage 6: PMF Evaluation Agent
        with console.status("[bold yellow]Stage 6/9: PMF Evaluation Agent - Testing viability...[/bold yellow]", spinner="dots"):
            pmf_out = self.pmf_agent.run(
                f"Assess PMF potential and calculate score for the market gaps:\n\n{gap_out}"
            )
        console.print("[green]OK[/green] Stage 6 Complete: Product-Market Fit evaluated.")

        # Stage 7: Strategy Agent
        with console.status("[bold yellow]Stage 7/9: Strategy Agent - Formulating business recommendations...[/bold yellow]", spinner="dots"):
            strategy_out = self.strategy_agent.run(
                f"Formulate product features and positioning strategy:\n\n"
                f"--- Market Gaps ---\n{gap_out}\n\n--- PMF Assessment ---\n{pmf_out}"
            )
        console.print("[green]OK[/green] Stage 7 Complete: Business strategy formulated.")

        # Stage 8: SWOT Analysis Agent
        with console.status("[bold yellow]Stage 8/9: SWOT Analysis Agent - Generating SWOT Matrix...[/bold yellow]", spinner="dots"):
            swot_out = self.swot_agent.run(
                f"Prepare a detailed SWOT matrix analyzing the business prospects:\n\n"
                f"--- Customer Insights ---\n{voice_out}\n\n"
                f"--- Market Gaps ---\n{gap_out}\n\n"
                f"--- PMF Assessment ---\n{pmf_out}\n\n"
                f"--- Strategy Framework ---\n{strategy_out}"
            )
        console.print("[green]OK[/green] Stage 8 Complete: SWOT Analysis completed.")

        # Stage 9: Report Agent
        with console.status("[bold yellow]Stage 9/9: Report Agent - Compiling executive report...[/bold yellow]", spinner="dots"):
            final_report = self.report_agent.run(
                f"Assemble all findings into a professional market research report.\n\n"
                f"Here are the inputs from the pipeline stages:\n"
                f"--- Available Information ---\n{research_out}\n\n"
                f"--- Customer Insights ---\n{voice_out}\n\n"
                f"--- Sentiment Analysis ---\n{sentiment_out}\n\n"
                f"--- Market Gaps ---\n{gap_out}\n\n"
                f"--- PMF Evaluation ---\n{pmf_out}\n\n"
                f"--- SWOT Analysis ---\n{swot_out}\n\n"
                f"--- Strategy Roadmap ---\n{strategy_out}"
            )
        console.print("[green]OK[/green] Stage 9 Complete: Executive report compiled successfully.\n")

        return final_report, topic_slug
