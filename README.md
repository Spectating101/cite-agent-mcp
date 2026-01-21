# Cite-Agent MCP Server 🚀

**The Professional AI Research Assistant for Claude, Cursor, and LangGraph.**

Cite-Agent MCP adds institutional-grade research capabilities to your AI agents. It connects your LLM to 200M+ academic papers and provides real-time, cited financial data with zero hallucination.

### ✨ Features
*   🔬 **Search 200M+ Papers:** Direct integration with Semantic Scholar, PubMed, and OpenAlex.
*   🎯 **Citation Verification:** (Pro) Programmatically verify if a claim is supported by academic sources.
*   📈 **Financial Provenance:** (Pro) Get SEC EDGAR and FRED data with machine-readable citations.
*   📦 **Plug-and-Play:** Zero configuration required for basic research.

### 📦 Installation
```bash
uvx cite-agent-mcp
```

### 🔑 Configuration & Pricing
The server provides **Free Paper Search** (capped results) by default.

To unlock **Unlimited Search**, **Citation Verification**, and **Financial Data**, you need a Pro License.
👉 **Get a Lifetime Pro License ($99):** [https://noctscraper.gumroad.com/l/cite-agent-pro](https://noctscraper.gumroad.com/l/cite-agent-pro)

Once you have your key, set it in your MCP client config:
```json
{
  "cite-agent": {
    "command": "uvx",
    "args": ["cite-agent-mcp"],
    "env": {
      "CITE_AGENT_API_KEY": "YOUR_GUMROAD_KEY"
    }
  }
}
```

### 🛠️ Tools
*   `search_papers`: Search academic databases for titles, abstracts, and DOIs.
*   `verify_citation`: [PRO] Cross-reference a text citation against global databases.
*   `get_financial_data`: [PRO] Fetch verified SEC/FRED metrics.

---
Built by [Molina Group](https://github.com/Spectating101).
