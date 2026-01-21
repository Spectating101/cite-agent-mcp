from typing import Any, Sequence
import asyncio
import os
import json
import sys
import subprocess
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
import httpx
from starlette.applications import Starlette
from starlette.routing import Route
import uvicorn

# Configuration
API_KEY = os.getenv("CITE_AGENT_API_KEY")
GUMROAD_PRODUCT_PERMALINK = os.getenv("GUMROAD_PERMALINK", "cite-agent-pro")

async def validate_license_key(key: str) -> bool:
    """Verify license key with Gumroad API."""
    if not key:
        return False
        
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                "https://api.gumroad.com/v2/licenses/verify",
                data={
                    "product_permalink": GUMROAD_PRODUCT_PERMALINK,
                    "license_key": key
                },
                timeout=5.0
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("success", False) and not data.get("purchase", {}).get("refunded", False)
            return False
        except Exception:
            return False

# Define the server
app = Server("cite-agent-mcp")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available research tools."""
    return [
        Tool(
            name="search_papers",
            description="[FREE] Search 200M+ academic papers from Semantic Scholar, OpenAlex, and PubMed. Returns titles, abstracts, and DOIs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Research topic (e.g., 'transformer architecture')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Results count (max 10 for free users)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="research_deep_dive",
            description="[PRO] Perform institutional-grade literature review. Synthesizes findings from 200M+ papers into a comprehensive report with citations. Use for complex research questions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The complex research question to answer (e.g. 'Synthesize current research on LLM alignment techniques')",
                    },
                },
                "required": ["question"],
            },
        ),
        Tool(
            name="get_zotero_papers",
            description="[PRO] Search and retrieve metadata/notes from your personal Zotero library. Requires Zotero API configuration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term within your Zotero library",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="read_arxiv_pdf",
            description="[PRO] Download and read the full text of an ArXiv paper using its PDF URL or ID. Best for deep analysis beyond abstracts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url_or_id": {
                        "type": "string",
                        "description": "ArXiv PDF URL (e.g. https://arxiv.org/pdf/2308.07901.pdf) or ID (2308.07901)",
                    },
                },
                "required": ["url_or_id"],
            },
        ),
        Tool(
            name="verify_citation",
            description="[PRO] Verify academic citations and check if claims are supported by sources. Requires License Key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "citation": {
                        "type": "string",
                        "description": "Full citation text to verify",
                    },
                },
                "required": ["citation"],
            },
        ),
        Tool(
            name="get_financial_data",
            description="[PRO] Get verified financial data from SEC EDGAR and FRED. Requires License Key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Ticker or financial question (e.g. 'AAPL Revenue')",
                    },
                },
                "required": ["query"],
            },
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
    """Execute tools with monetization gating."""
    
    # 1. Monetization Gate
    is_pro = await validate_license_key(API_KEY)
    
    if name != "search_papers" and not is_pro:
        return [TextContent(type="text", text=f"⚠️ **PRO Feature Locked**\n\n'{name}' requires a Cite-Agent Pro license.\n\n👉 **Get your key here:** https://gumroad.com/l/{GUMROAD_PRODUCT_PERMALINK}\n\nSet the CITE_AGENT_API_KEY environment variable to unlock.")]

    # 2. Logic Implementation
    try:
        if name == "search_papers":
            query = arguments["query"]
            max_results = arguments.get("max_results", 10)
            if not is_pro:
                max_results = min(max_results, 5) 
            cmd = ["cite-agent", f"Find academic papers on: {query}. Show {max_results} results."]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return [TextContent(type="text", text=result.stdout)]

        elif name == "research_deep_dive":
            # This uses the IntelligentSearch engine from the core
            try:
                # Add Cite-Agent core to path dynamically
                parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                core_path = os.path.join(parent_dir, "Cite-Agent")
                if core_path not in sys.path:
                    sys.path.insert(0, core_path)
                
                from cite_agent.enhanced_ai_agent import EnhancedNocturnalAgent, ChatRequest
                
                agent = EnhancedNocturnalAgent()
                await agent.initialize()
                
                req = ChatRequest(question=arguments["question"])
                response = await agent.process_request(req)
                
                await agent.close()
                
                if response.error_message:
                    return [TextContent(type="text", text=f"❌ Agent Error: {response.error_message}")]
                
                return [TextContent(type="text", text=f"🧠 **Deep Research Synthesis**\n\n{response.response}")]
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Integration Error: {str(e)}")]

        elif name == "get_zotero_papers":
            # This requires pyzotero and ZOTERO_API_KEY / ZOTERO_USER_ID
            try:
                from pyzotero import zotero
                zot = zotero.Zotero(os.getenv("ZOTERO_USER_ID"), 'user', os.getenv("ZOTERO_API_KEY"))
                items = zot.top(q=arguments["query"])
                return [TextContent(type="text", text=json.dumps(items, indent=2))]
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Zotero Error: {str(e)}. Ensure ZOTERO_USER_ID and ZOTERO_API_KEY are set.")]

        elif name == "read_arxiv_pdf":
            # This requires PyPDF2 and httpx
            import io
            from PyPDF2 import PdfReader
            url = arguments["url_or_id"]
            if not url.startswith("http"):
                url = f"https://arxiv.org/pdf/{url}.pdf"
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=30.0)
                if resp.status_code != 200:
                    return [TextContent(type="text", text=f"❌ Failed to download PDF: {resp.status_code}")]
                
                f = io.BytesIO(resp.content)
                reader = PdfReader(f)
                text = ""
                # Extract first 10 pages to avoid context window blowup
                for i in range(min(10, len(reader.pages))):
                    text += reader.pages[i].extract_text()
                
                return [TextContent(type="text", text=f"📄 **Full Text (First 10 pages)**\n\n{text[:15000]}...")]

        elif name == "verify_citation":
            cmd = ["cite-agent", f"Verify this citation: {arguments['citation']}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return [TextContent(type="text", text=result.stdout)]
            
        elif name == "get_financial_data":
            cmd = ["cite-agent", arguments["query"]]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return [TextContent(type="text", text=result.stdout)]
            
        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        return [TextContent(type="text", text=f"❌ System Error: {str(e)}")]

def main():
    """Smart entry point for stdio/SSE."""
    port = os.getenv("PORT")
    if port:
        port_int = int(port)
        sse = SseServerTransport("/messages")
        async def handle_sse(request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await app.run(streams[0], streams[1], app.create_initialization_options())
        async def handle_messages(request):
            await sse.handle_post_message(request.scope, request.receive, request._send)
        starlette_app = Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_messages, methods=["POST"]),
            ],
        )
        print(f"🚀 Starting Cite-Agent MCP (REMOTE) on port {port_int}", file=sys.stderr)
        uvicorn.run(starlette_app, host="0.0.0.0", port=port_int)
    else:
        print("💻 Starting Cite-Agent MCP (LOCAL)", file=sys.stderr)
        asyncio.run(stdio_server(app))

if __name__ == "__main__":
    main()
