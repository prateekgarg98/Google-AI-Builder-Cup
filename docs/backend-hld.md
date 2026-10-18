graph LR
    %% ==========================================
    %% 1. Client & Ingress Layer
    %% ==========================================
    Client["💻 Frontend UI\n(React/Next.js)"]
    
    subgraph Ingress ["Google Cloud Infrastructure"]
        Gateway["🌐 API Gateway\n(Auth & Routing)"]
    end

    Client -- "POST / (API Key)" --> Gateway
    Client -. "POST /approvals/{id}/decision" .-> Gateway

    %% ==========================================
    %% 2. Orchestrator Layer (Main Cloud Run)
    %% ==========================================
    subgraph Orchestrator ["Primary Planner (Cloud Run)"]
        direction TB
        Planner{"🧠 LangGraph Planner\n(Gemini Pro)"}
        
        %% Guardrails
        SecAgent["🛡️ Security Agent\n(Regex + LLM)"]
        PrivAgent["🔒 Privacy Agent"]
        OOSAgent["🚫 Out-of-Scope Agent"]
        
        %% Core Workers
        KnowAgent["📚 Knowledge Agent"]
        ProcAgent["⚙️ Processing Agent\n(Diagrams/Docs)"]
        MCPAgent["🛠️ MCP Agent\n(DevOps/Code)"]

        Planner -- "Prompt Injection?" --> SecAgent
        Planner -- "PII/Salaries?" --> PrivAgent
        Planner -- "World Knowledge?" --> OOSAgent
        
        Planner -- "Corporate SOPs" --> KnowAgent
        Planner -- "Create Visuals/Docs" --> ProcAgent
        Planner -- "Action/Investigation" --> MCPAgent
    end

    Gateway -- "Req: query, session_id" --> Planner

    %% ==========================================
    %% 3. State & Memory Layer
    %% ==========================================
    subgraph Memory ["Firestore (Sliding Window State)"]
        FS_Sessions[("📄 /sessions\n(Context & Summary)")]
        FS_Audits[("📁 /requests & /approvals")]
    end
    
    Planner <--> |"1. Fetch Context\n2. Async Save (0ms latency)"| FS_Sessions
    Planner -. "Log raw traces" .-> FS_Audits

    %% ==========================================
    %% 4. AI & Grounding Layer
    %% ==========================================
    subgraph AI_Layer ["Vertex AI & Grounding Services"]
        Gemini["✨ Gemini 3.1 Pro\n(Reasoning & Generation)"]
        Discovery["🔎 Vertex AI Search\n(100+ Indexed SOPs)"]
    end

    KnowAgent <--> |"Strict Grounded Search"| Discovery
    ProcAgent <--> |"1. Verify Evidence"| Discovery
    ProcAgent <--> |"2. Generate Mermaid/MD"| Gemini
    MCPAgent <--> |"Tool Calling logic"| Gemini

    %% ==========================================
    %% 5. Storage Layer
    %% ==========================================
    GCS[("☁️ Cloud Storage\n(SVG Diagrams & Docs)")]
    ProcAgent --> |"Uploads SVG/MD\nReturns Signed URL"| GCS

    %% ==========================================
    %% 6. Microservices & Execution Layer
    %% ==========================================
    subgraph Gateway_Microservice ["Secure Execution Boundary"]
        MCP["🚨 MCP Gateway (Cloud Run)"]
        HITL{"🛑 HITL Approval Gate\n(HTTP 202 State)"}
    end

    MCPAgent --> |"Bearer Token + JSON Args"| MCP
    Gateway -. "Proxy Approval Decision" .-> HITL
    MCP <--> HITL
    HITL <--> |"Read/Write Approval State"| FS_Audits

    %% ==========================================
    %% 7. Third-Party Integrations
    %% ==========================================
    subgraph External ["External Enterprise Systems"]
        GitHub["🐙 GitHub MCP"]
        Jira["🎫 Atlassian Jira API"]
        DevOps["☁️ GCP DevOps MCP\n(Deploy/Logs)"]
    end

    MCP --> GitHub
    MCP --> Jira
    MCP --> DevOps

    %% Styling for better visual presentation
    classDef gcp fill:#e3f2fd,stroke:#1565c0,stroke-width:2px;
    classDef agent fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px;
    classDef memory fill:#fff3e0,stroke:#e65100,stroke-width:2px;
    classDef core fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;
    classDef external fill:#eceff1,stroke:#455a64,stroke-width:2px;
    
    class Gateway,GCS gcp;
    class SecAgent,PrivAgent,OOSAgent,KnowAgent,ProcAgent,MCPAgent agent;
    class FS_Sessions,FS_Audits memory;
    class Planner,MCP core;
    class GitHub,Jira,DevOps,Discovery,Gemini external;
