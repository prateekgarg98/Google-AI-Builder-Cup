# Enterprise Assistant 🛡️
**By Team Tech Titans | AI Builder Cup 2026**

Enterprise Assistant is a strictly grounded, multi-agent enterprise orchestrator. It bridges the gap between static corporate knowledge bases and active engineering workflows. Featuring zero-hallucination architecture, instant sliding-window memory, and Human-in-the-Loop (HITL) DevOps approvals, TitanWork is built for secure, enterprise-grade AI execution.

## 🌟 Key Features

*   **Zero-Hallucination Guardrails:** Utilizes a custom LangGraph Planner to enforce strict routing. Requests for general world knowledge, prompt injections, or private data are blocked instantly.
*   **Grounded Visual Architecture:** Generates high-quality, infinitely scalable SVG Mermaid diagrams and markdown documents *only* if the facts exist in the Vertex AI Search corpus.
*   **Human-in-the-Loop (HITL) DevOps:** Integrates with an isolated MCP Gateway to safely execute GitHub, Jira, and DevOps operations, catching destructive actions (like production rollbacks) with an HTTP 202 Approval state.
*   **0ms Latency Memory:** Uses Cloud Firestore for a "Sliding-Window" conversation context, rewriting user pronouns (e.g., "draw a diagram of *it*") in a single LLM pass before hitting downstream agents, saving seconds of execution time.

## 🏗️ Architecture

Enterprise Assistant leverages Google Cloud Run, API Gateway, LangGraph, and Vertex AI.

```mermaid
graph TB
    %% 1. Client & Ingress Layer
    Client["💻 Frontend UI\n(React/Next.js)"]
    subgraph Ingress ["Google Cloud Infrastructure"]
        Gateway["🌐 API Gateway\n(Auth & Routing)"]
    end
    Client -- "POST / (API Key)" --> Gateway
    Client -. "POST /approvals/{id}/decision" .-> Gateway

    %% 2. Orchestrator Layer
    subgraph Orchestrator ["Primary Planner (Cloud Run)"]
        direction TB
        Planner{"🧠 LangGraph Planner\n(Gemini Flash)"}
        SecAgent["🛡️ Security Agent"]
        PrivAgent["🔒 Privacy Agent"]
        OOSAgent["🚫 Out-of-Scope Agent"]
        KnowAgent["📚 Knowledge Agent"]
        ProcAgent["⚙️ Processing Agent"]
        MCPAgent["🛠️ MCP Agent"]

        Planner -- "Prompt Injection?" --> SecAgent
        Planner -- "PII/Salaries?" --> PrivAgent
        Planner -- "World Knowledge?" --> OOSAgent
        Planner -- "Corporate SOPs" --> KnowAgent
        Planner -- "Create Visuals/Docs" --> ProcAgent
        Planner -- "Action/Investigation" --> MCPAgent
    end
    Gateway -- "Req: query, session_id" --> Planner

    %% 3. State & Memory Layer
    subgraph Memory ["Firestore (Sliding Window State)"]
        FS_Sessions[("📄 /sessions")]
        FS_Audits[("📁 /requests")]
    end
    Planner <--> |"Fetch & Async Save"| FS_Sessions
    Planner -. "Audit Logging" .-> FS_Audits

    %% 4. AI & Grounding Layer
    subgraph AI_Layer ["Vertex AI & Grounding"]
        Gemini["✨ Gemini 3.1 Pro"]
        Discovery["🔎 Vertex AI Search"]
    end
    KnowAgent <--> |"Strict Search"| Discovery
    ProcAgent <--> |"Verify Evidence"| Discovery
    ProcAgent <--> |"Generate SVG/MD"| Gemini
    MCPAgent <--> |"Tool Calling"| Gemini

    %% 5. Storage Layer
    GCS[("☁️ Cloud Storage\n(SVG/MD)")]
    ProcAgent --> GCS

    %% 6. MCP Gateway & External
    subgraph Gateway_Microservice ["Secure Execution Boundary"]
        MCP["🚨 MCP Gateway (Cloud Run)"]
        HITL{"🛑 HITL Approval Gate"}
    end
    MCPAgent --> MCP
    Gateway -. "Proxy Approval" .-> HITL
    MCP <--> HITL

    subgraph External ["Enterprise Systems"]
        GitHub["🐙 GitHub"]
        Jira["🎫 Jira"]
        DevOps["☁️ GCP DevOps"]
    end
    MCP --> GitHub
    MCP --> Jira
    MCP --> DevOps
```

## 📁 Repository Structure

```text
TechTitans-EnterpriseAssistant/
├── frontend/                   # UI for the Enterprise Work Agent
├── backend/
│   ├── orchestrator/           # LangGraph Planner & Agent Nodes (main.py)
│   └── mcp-gateway/            # Tool execution & HITL approval logic
├── infrastructure/             # API Gateway YAML configurations
└── docs/                       # Architecture diagrams and sample prompts
```

## 🚀 How to Test
1. Set the API URL to our Gateway endpoint.
2. Provide your API Key in the UI settings.
3. Use the prompts outlined in `docs/sample_prompts.md` to see the multi-agent routing in action!
