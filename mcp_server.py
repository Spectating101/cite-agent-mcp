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

    # 2. Logic Implementation (Wraps cite-agent CLI)
    try:
        if name == "search_papers":
            query = arguments["query"]
            max_results = arguments.get("max_results", 10)
            if not is_pro:
                max_results = min(max_results, 5) # Capped for free
            
            cmd = ["cite-agent", f"Find academic papers on: {query}. Show {max_results} results."]
            
        elif name == "verify_citation":
            cmd = ["cite-agent", f"Verify this citation: {arguments['citation']}"]
            
        elif name == "get_financial_data":
            cmd = ["cite-agent", arguments["query"]]
            
        else:
            raise ValueError(f"Unknown tool: {name}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            return [TextContent(type="text", text=f"❌ Error: {result.stderr or 'Cite-Agent CLI not found. Please install it with: pip install cite-agent'}")]

        return [TextContent(type="text", text=result.stdout)]

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
