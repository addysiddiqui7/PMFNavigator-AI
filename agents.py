import google.generativeai as genai
import json
import re
from config import MODEL_NAME
from tools import CSVReaderTool

class BaseAgent:
    """
    Base class for all specialized agents in the PMF Research System.
    """
    def __init__(self, name: str, system_instruction: str, model: str = MODEL_NAME):
        self.name = name
        self.system_instruction = system_instruction
        self.model = model
        self.tools = None  # Default is no tools

    def safe_generate(self, contents, generation_config=None, system_instruction=None, tools=None) -> str:
        """
        Generates content safely with retry-on-quota-limits (429) logic.
        """
        import time
        max_retries = 5  # Number of retries before failing
        retry_delay = 30 # Default delay if parsing fails

        # Use overrides if provided, otherwise default to instance configurations
        active_instruction = system_instruction if system_instruction is not None else self.system_instruction
        active_tools = tools if tools is not None else self.tools

        for attempt in range(max_retries):
            try:
                # Re-instantiate the model to load the active configuration
                active_model = genai.GenerativeModel(
                    model_name=self.model,
                    system_instruction=active_instruction,
                    tools=active_tools
                )
                response = active_model.generate_content(
                    contents,
                    generation_config=generation_config
                )
                return response.text
            except Exception as e:
                err_str = str(e)
                # Print exact error for diagnostics
                print(f"\n[{self.name}] Attempt {attempt+1}/{max_retries} failed: {err_str[:120]}", flush=True)
                
                is_quota_error = "429" in err_str or "Quota exceeded" in err_str or "ResourceExhausted" in err_str
                
                if is_quota_error:
                    match = re.search(r'retry in (\d+\.?\d*)s', err_str)
                    wait_time = float(match.group(1)) + 1.0 if match else retry_delay
                    
                    if attempt < max_retries - 1:
                        print(f"\n[{self.name}] Quota limit hit (429). Sleeping for {wait_time:.1f}s before retry...", flush=True)
                        time.sleep(wait_time)
                        continue
                raise e

    def run(self, prompt: str) -> str:
        """
        Sends the prompt to the Gemini API with the agent's specific system instructions.
        """
        try:
            generation_config = genai.types.GenerationConfig(
                temperature=0.2, # Lower temperature for analytical precision
            )
            return self.safe_generate(prompt, generation_config)
        except Exception as e:
            return f"[{self.name} Error]: {str(e)}"

# -------------------------------------------------------------
# 1. Research Agent
# -------------------------------------------------------------
class ResearchAgent(BaseAgent):
    """
    Research Agent: Gathers and compiles available information.
    Answers: "What information is available?"
    """
    def __init__(self):
        system_instruction = (
            "You are a professional Market Research Analyst. Your job is to answer: 'What information is available?' "
            "based on the provided inputs.\n"
            "Compile all data sources (CSV user feedback and/or Google Search results) into a unified, structured "
            "data summary. Highlight where the data came from (internal user feedback CSV vs. public web discussion). "
            "Do not analyze sentiments or draw conclusions yet—simply lay out the raw customer feedback facts cleanly."
        )
        super().__init__("Research Agent", system_instruction)
        self.csv_reader = CSVReaderTool()

    def run_research(self, query: str, csv_path: str = None, status_callback=None, mode: str = "fast") -> str:
        csv_data = ""
        search_data_list = []
        web_sources_count = 0
        csv_count = 0

        # Decision Logic:
        # 1. If CSV or local document folder exists -> use DocumentIngestionTool (via CSVReaderTool wrapper)
        if csv_path:
            import os
            if status_callback:
                status_callback("Stage 2/9: Research Agent - Indexing local documents & files...")
            csv_data = self.csv_reader.run(csv_path)
            meta = self.csv_reader.get_metadata_summary()
            csv_count = meta["sources_count"]

        # 2. Run targeted web searches based on selected mode
        if mode == "fast":
            sub_queries = [
                f"comprehensive customer feedback, reviews, technical problems, and market trends for: {query}"
            ]
        else:
            sub_queries = [
                f"customer reviews, complaints, problems, and discussions on reddit or forums for: {query}",
                f"professional reviews, technical blogs, expert analysis, and issues for: {query}",
                f"buyer satisfaction, user feedback, and requested features for: {query}"
            ]

        for i, sub_query in enumerate(sub_queries):
            total_queries = len(sub_queries)
            print(f"Running DDG Web Search {i+1}/{total_queries}: '{sub_query}'...", flush=True)
            if status_callback:
                status_callback(f"Stage 2/9: Research Agent - DDG Search {i+1}/{total_queries}...")
            
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    results = list(ddgs.text(sub_query, max_results=5))
                
                if not results:
                    raise Exception("No search results returned from DuckDuckGo.")
                
                web_sources_count += len(results)
                
                # Format search results
                context_parts = []
                for idx, r in enumerate(results):
                    context_parts.append(f"[{idx+1}] Source: {r.get('href')}\nTitle: {r.get('title')}\nSnippet: {r.get('body')}\n")
                search_context = "\n".join(context_parts)
                
                synthesis_prompt = (
                    f"Analyze the following web search results for the query '{sub_query}' and synthesize "
                    f"a detailed research summary highlighting customer reviews, technical issues, "
                    f"market trends, and competitor signals.\n\n"
                    f"--- Search Results ---\n{search_context}\n\n"
                    f"Synthesis Summary:"
                )
                
                response_text = self.safe_generate(
                    synthesis_prompt,
                    generation_config=genai.types.GenerationConfig(temperature=0.1),
                    system_instruction="You are a professional market research analyst. Synthesize the provided web search context into a cohesive research brief."
                )
                search_data_list.append(f"### Deep Search {i+1}: Query: '{sub_query}'\n{response_text}")
            except Exception as e:
                # Fallback to model's pre-trained knowledge if DDG search fails
                try:
                    print(f"DDG Search failed (Error: {e}), falling back to model knowledge...", flush=True)
                    response_text = self.safe_generate(
                        sub_query,
                        system_instruction="You are a web research analyst. Summarize your existing knowledge on the query."
                    )
                    search_data_list.append(f"### Deep Search {i+1} (Fallback): Query: '{sub_query}'\n{response_text}\n*(Search failed, fell back to model knowledge. Error: {e})*")
                except Exception as ex:
                    search_data_list.append(f"### Deep Search {i+1} Failed: {str(ex)}")

        search_data = "\n\n".join(search_data_list)

        # Combine information sources
        prompt = f"User Query/Objective: {query}\n\n"
        if csv_data:
            prompt += f"--- START INTERNAL CSV FEEDBACK DATA ---\n{csv_data}\n--- END INTERNAL CSV FEEDBACK DATA ---\n\n"
        
        prompt += f"--- START PUBLIC WEB DISCUSSIONS (DEEP GROUNDED SEARCH) ---\n{search_data}\n--- END PUBLIC WEB DISCUSSIONS (DEEP GROUNDED SEARCH) ---\n\n"
        prompt += "Please synthesize the above available data into a comprehensive report summarizing 'What information is available?'"
        
        if status_callback:
            status_callback("Stage 2/9: Research Agent - Synthesizing all gathered data...")
            
        synthesized_text = self.run(prompt)
        
        total_sources = web_sources_count + csv_count
        types_str = "None"
        if csv_path and csv_count > 0:
            meta = self.csv_reader.get_metadata_summary()
            types_str = ", ".join(t.upper() for t in meta.get("types_present", []))
            
        metadata_block = (
            f"--- RESEARCH METADATA ---\n"
            f"- Number of Web Sources Analyzed: {web_sources_count}\n"
            f"- Number of Local Documents Ingested: {csv_count} (Types: {types_str})\n"
            f"- Total Sources Analyzed: {total_sources}\n"
            f"--- END RESEARCH METADATA ---\n\n"
        )
        return metadata_block + synthesized_text

# -------------------------------------------------------------
# 2. Customer Voice Agent
# -------------------------------------------------------------
class CustomerVoiceAgent(BaseAgent):
    """
    Customer Voice Agent: Focuses on complaints, praises, issues, and requests.
    Answers: "What are customers saying?"
    """
    def __init__(self):
        system_instruction = (
            "You are a Customer Insight Specialist. Your task is to answer: 'What are customers saying?'\n"
            "Analyze the Research Agent's output. You must:\n"
            "- Categorize your findings into distinct **Customer Themes** (e.g. Wearability & Comfort, Battery & Charging, Cost & Subscriptions, Lifestyle & Notifications) and state the total number of customer themes identified.\n"
            "- Under each theme, extract and compile findings into four clear areas:\n"
            "  1. Major Customer Complaints & Frustrations\n"
            "  2. Customer Praise & Positive Highlights\n"
            "  3. Recurring Unresolved Issues\n"
            "  4. Specifically Requested Features\n"
            "IMPORTANT: Focus exclusively on what customers are saying. Do NOT perform sentiment scoring or rate customer satisfaction numerically."
        )
        super().__init__("Customer Voice Agent", system_instruction)

# -------------------------------------------------------------
# 3. Sentiment Agent
# -------------------------------------------------------------
class SentimentAgent(BaseAgent):
    """
    Sentiment Agent: Evaluates emotional intensity and trends.
    Answers: "How strongly do customers feel about these issues?"
    """
    def __init__(self):
        system_instruction = (
            "You are a Customer Sentiment Analyst. Your task is to answer: 'How strongly do customers feel about these issues?'\n"
            "Analyze the Customer Voice Agent's findings. You must:\n"
            "- Confirm and list the total number of **Customer Themes** identified and analyzed.\n"
            "- Determine emotional intensity for each theme (e.g., high rage, mild annoyance, strong enthusiasm, passive satisfaction).\n"
            "- Track positive vs. negative sentiment trends across these themes.\n"
            "- Map customer satisfaction levels.\n"
            "- Measure overall sentiment distribution and recurring emotional patterns."
        )
        super().__init__("Sentiment Agent", system_instruction)

# -------------------------------------------------------------
# 4. Market Gap Agent
# -------------------------------------------------------------
class MarketGapAgent(BaseAgent):
    """
    Market Gap Agent: Identifies unmet needs and underserved demands.
    Answers: "What opportunities exist?"
    """
    def __init__(self):
        system_instruction = (
            "You are an Opportunity Discovery Specialist. Your task is to answer: 'What opportunities exist?'\n"
            "Analyze the complaints, requested features, and sentiment intensity identified so far.\n"
            "For each market gap or opportunity identified, you must include:\n"
            "- **Opportunity Name & Description**: What is the unmet need, underserved demand, or competitive gap?\n"
            "- **Opportunity Severity**: How critical is this gap to the customer? (Scale: Low / Medium / High / Critical)\n"
            "- **Estimated Business Impact**: What is the potential strategic or financial benefit to the business? (Scale: Low / Medium / High / Game-Changer)\n"
            "Highlight gaps that rivals are currently ignoring or not addressing."
        )
        super().__init__("Market Gap Agent", system_instruction)

# -------------------------------------------------------------
# 5. PMF Evaluation Agent
# -------------------------------------------------------------
class PMFEvaluationAgent(BaseAgent):
    """
    PMF Evaluation Agent: Calculates demand, PMF scores, and confidence.
    Answers: "Is there sufficient product-market fit?"
    """
    def __init__(self):
        system_instruction = (
            "You are a Product-Market Fit Evaluator. Your task is to answer: 'Is there sufficient product-market fit?'\n"
            "Analyze the market gaps, customer sentiments, and research metrics. You must structure your assessment with these exact elements:\n"
            "1. **PMF Score Calculation & Methodology**: Explain clearly how the PMF score is calculated as the average of four key measurable factors scaled to 0-100 (average score out of 10 multiplied by 10):\n"
            "   - **Demand Strength** (Is there high market search interest, customer demand, and purchase intent? Scored 1 to 10)\n"
            "   - **Pain Severity** (Are current complaints and frustrations intense enough that users are desperate for a solution? Scored 1 to 10)\n"
            "   - **Competition Gap** (Are competitor solutions ignoring this gap or failing to satisfy users? Scored 1 to 10)\n"
            "   - **Adoption Potential** (How easily can the target audience integrate this solution without friction? Scored 1 to 10)\n"
            "2. **Evidence-Based Confidence Metrics**: Report the following metrics explicitly derived from the preceding agent data:\n"
            "   - **Number of Sources Analyzed**: Read this directly from the 'RESEARCH METADATA' header at the top of the research data.\n"
            "   - **Number of Customer Themes Identified**: Read the total count of distinct themes from the customer voice/sentiment analysis.\n"
            "   - **Confidence Score**: Out of 100, representing the reliability and density of the evidence. Explain the calculation based on data completeness (e.g. source density, theme consistency, and clarity of signals).\n"
            "   - **Confidence Level**: Low / Medium / High, with justification based on the scores and evidence.\n"
            "3. **Viability Recommendation**: Evaluate whether the identified market opportunities justify substantial investment, product improvements, or new innovation."
        )
        super().__init__("PMF Evaluation Agent", system_instruction)

# -------------------------------------------------------------
# 6. Strategy Agent
# -------------------------------------------------------------
class StrategyAgent(BaseAgent):
    """
    Strategy Agent: Prioritizes and plans product roadmap and positioning.
    Answers: "What should the business do?"
    """
    def __init__(self):
        system_instruction = (
            "You are a Business Strategy Consultant. Your task is to answer: 'What should the business do?'\n"
            "Using the PMF evaluation and market gaps, build an actionable strategic framework.\n"
            "You must separate your recommendations and roadmap into distinct categories:\n"
            "1. **Strategic Recommendations**:\n"
            "   - **Short-Term Actions (Quick Wins)**: Actionable, immediate steps that can be implemented in 1-6 months.\n"
            "   - **Long-Term Opportunities**: Strategic, high-value objectives for the next 12-24 months.\n"
            "2. **Product Roadmap & Innovation**:\n"
            "   - **Realistic Product Improvements**: Incremental upgrades, fixes, and enhancements that address existing user complaints directly.\n"
            "   - **Future Innovations**: Bold, new-to-market features and long-term research-and-development concepts that create new value.\n"
            "3. **Product Positioning & Go-To-Market (GTM) Strategy**: Suggestions on how to position the product to stand out from competitors.\n"
            "4. **Concrete Business Recommendations**: Actionable, high-level business suggestions for commercial success."
        )
        super().__init__("Strategy Agent", system_instruction)

# -------------------------------------------------------------
# 7. Briefing Agent
# -------------------------------------------------------------
class BriefingAgent(BaseAgent):
    """
    Briefing Agent: Conducts briefing based on user query.
    Extracts a topic title, topic slug (dynamic naming), competitors, audience, and guidelines.
    """
    def __init__(self):
        system_instruction = (
            "You are a Project Briefing Specialist. Your role is to take a short query or topic and build a structured "
            "Research Brief that will guide a multi-agent system.\n"
            "You MUST output your response strictly as a single JSON object. Do not include markdown code block syntax "
            "except for the JSON format itself. The JSON must contain these exact keys:\n"
            "{\n"
            "  \"topic_title\": \"A clean, professional title for the research (e.g., 'Smart Rings for Health')\",\n"
            "  \"topic_slug\": \"A 2-3 word lowercase snake_case filename slug using only letters, numbers and underscores (e.g., 'smart_rings_health')\",\n"
            "  \"suggested_competitors\": \"2-3 prominent competitors or brands in this segment\",\n"
            "  \"suggested_target_audience\": \"A brief description of the target demographics or users\",\n"
            "  \"research_guidelines\": \"Specific instructions or guidelines for search tools regarding this segment\"\n"
            "}"
        )
        super().__init__("Briefing Agent", system_instruction)

    def generate_brief(self, query: str) -> dict:
        """
        Generates the brief, parses the JSON response, and returns a dictionary.
        """
        response_text = self.run(f"Please build a research brief for the query: '{query}'")
        
        # Strip markdown json block tags if present
        clean_text = response_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        try:
            return json.loads(clean_text)
        except Exception as e:
            # Fallback parsing in case JSON is imperfect
            slugified = re.sub(r'[^a-z0-9_]', '', query.lower().replace(' ', '_'))[:30]
            if not slugified:
                slugified = "market_research"
            return {
                "topic_title": query,
                "topic_slug": slugified,
                "suggested_competitors": "General competitors",
                "suggested_target_audience": "General consumers",
                "research_guidelines": f"Investigate the general market for: {query}"
            }

# -------------------------------------------------------------
# 8. SWOT Analysis Agent
# -------------------------------------------------------------
class SWOTAnalysisAgent(BaseAgent):
    """
    SWOT Analysis Agent: Synthesizes findings into a SWOT Matrix.
    Answers: "What are the Strengths, Weaknesses, Opportunities, and Threats?"
    """
    def __init__(self):
        system_instruction = (
            "You are a Strategic SWOT Analyst. Your task is to analyze the preceding agent outputs "
            "(Customer Voice, Sentiment, Gaps, and PMF Evaluation) and compile a formal SWOT Analysis Matrix "
            "for the target business/product strategy. Structure it clearly using Markdown tables and lists:\n"
            "- **Strengths (S)**: What is working well? Positive customer feedback, highly valued features.\n"
            "- **Weaknesses (W)**: Product defects, battery degradation, connection issues, poor call quality, design flaws.\n"
            "- **Opportunities (O)**: Market gaps, unmet needs, emerging technologies (e.g. non-invasive tracking, modularity).\n"
            "- **Threats (T)**: Competitor ecosystem lock-in, regulatory compliance, subscription-only backlash, pricing pressure.\n"
            "Output a detailed, executive-ready SWOT matrix."
        )
        super().__init__("SWOT Analysis Agent", system_instruction)

# -------------------------------------------------------------
# 9. Report Agent
# -------------------------------------------------------------
class ReportAgent(BaseAgent):
    """
    Report Agent: Compiles findings into an executive market research report.
    Answers: "How should the findings be communicated?"
    """
    def __init__(self):
        system_instruction = (
            "You are an Executive Reporting Specialist. Your task is to compile all the outputs from the entire agent pipeline "
            "into a polished, executive-ready Business Report.\n"
            "Your report must be structured using clean Markdown headings, tables, or bullet points, and include these sections in order:\n"
            "1. **Executive Summary**\n"
            "2. **Information Available & Sources** (Summarize search data and include the count of web/CSV sources analyzed)\n"
            "3. **Customer Voice Insights** (Major complaints, praise, and requested features categorized by themes)\n"
            "4. **Sentiment & Emotional Trends Analysis** (With emotional mapping and satisfaction levels)\n"
            "5. **Market Gaps & Unexplored Opportunities** (Including opportunity severity and estimated business impact)\n"
            "6. **Product-Market Fit (PMF) Assessment** (Explaining calculation methodology, listing measurable factors 1-10, and providing PMF and Confidence scores/levels)\n"
            "7. **Strategic SWOT Analysis Matrix**\n"
            "8. **Strategic Recommendations & Feature Roadmap** (Divided into short-term actions vs long-term opportunities, and product improvements vs future innovations)\n"
            "9. **Key Metrics Summary** (A final high-level table/dashboard summarizing: PMF Score, Confidence Score, Major Pain Points, Top Opportunities, and Risk Level)\n"
            "Format the report professionally so it is ready to present to stakeholders and leadership."
        )
        super().__init__("Report Agent", system_instruction)
