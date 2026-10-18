import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import "./App.css";

interface AIBlock {
  type: "text" | "approval" | "structured" | "image" | "document" | "mermaid";
  content?: string;
  url?: string;
  data?: any;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  text?: string;
  blocks?: AIBlock[];
}

interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
}

const API_ENDPOINT = "/api/query";

const SUGGESTED_QUESTIONS = [
  "Based on our corporate policies, draw a flowchart of our production release approval process.",
  "What are our data retention and encryption requirements for customer PII under company security standards?",
];

async function sendQuery(query: string, sessionId?: string | null) {
  const payload: { query: string; session_id?: string } = { query };

  // Only attach session_id if it's a real backend UUID, not a local temporary one
  if (sessionId && !sessionId.startsWith("local-")) {
    payload.session_id = sessionId;
  }

  const response = await fetch(API_ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      `API request failed (${response.status}): ${errorData.error || response.statusText}`
    );
  }

  return response.json();
}

const INITIAL_MESSAGE: Message = {
  id: "initial-message",
  role: "assistant",
  blocks: [
    {
      type: "text",
      content:
        "Hello! I’m Enterprise Assistant. Describe the workflow, infrastructure, deployment, or process you want to build.",
    },
  ],
};
 
function renderCollapsibleWorkflow(codeText: string | undefined, key?: number) {
  const safeCode = codeText ? codeText : "";
  return (
    <details
      key={key}
      className="artifact-card"
      style={{
        marginBottom: "16px",
        borderRadius: "8px",
        overflow: "hidden",
        border: "1px solid var(--border-color)",
        background: "var(--bg-card)",
      }}
    >
      <summary
        className="artifact-header"
        style={{
          padding: "12px 16px",
          cursor: "pointer",
          fontWeight: 600,
          fontSize: "14px",
          userSelect: "none",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "var(--bg-input)",
          color: "var(--text-main)",
        }}
      >
        <span>Generated Workflow (Click to view code)</span>
        <span style={{ fontSize: "12px" }}>▼</span>
      </summary>
      <div>
        <pre
          style={{
            margin: 0,
            padding: "14px",
            fontSize: "12px",
            overflowX: "auto",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            fontFamily: "monospace",
            background: "var(--code-bg)",
            color: "var(--code-text)",
          }}
        >
          <code>{safeCode}</code>
        </pre>
      </div>
    </details>
  );
}

const markdownComponentsConfig = {
  code(props: any) {
    const { children, className } = props;
    const cls = className ? className : "";
    const match = /language-(\w+)/.exec(cls);
    const codeString = String(children).replace(/\n$/, "");

    if (match && match[1] === "mermaid") {
      return renderCollapsibleWorkflow(codeString);
    }

    return match ? (
      <pre
        style={{
          padding: "12px",
          borderRadius: "4px",
          overflowX: "auto",
          marginBottom: "16px",
          marginTop: "8px",
          background: "var(--code-bg)",
        }}
      >
        <code className={cls} style={{ color: "var(--code-text)" }}>
          {children}
        </code>
      </pre>
    ) : (
      <code
        className={cls}
        style={{
          padding: "2px 6px",
          borderRadius: "4px",
          background: "var(--bg-input)",
          color: "var(--code-text)",
        }}
      >
        {children}
      </code>
    );
  },
};

export default function App() {
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(true);

  // Theme State
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return (
      localStorage.getItem("theme") === "dark" ||
      (!("theme" in localStorage) &&
        window.matchMedia("(prefers-color-scheme: dark)").matches)
    );
  });

  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.remove("light");
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.classList.add("light");
      localStorage.setItem("theme", "light");
    }
  }, [darkMode]);

  const [approvalStates, setApprovalStates] = useState<
    Record<string, { status: string; isProcessing: boolean; resultMsg: string }>
  >({});
  const [imageZooms, setImageZooms] = useState<Record<string, number>>({});

  const [sessions, setSessions] = useState<ChatSession[]>([
    {
      id: `local-${Date.now()}`,
      title: "New conversation",
      messages: [INITIAL_MESSAGE],
      createdAt: Date.now(),
    },
  ]);

  const [activeSessionId, setActiveSessionId] = useState(sessions[0].id);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const foundSession = sessions.find((s) => s.id === activeSessionId);
  const activeSession = foundSession ? foundSession : sessions[0];
  const messages = activeSession ? activeSession.messages : [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const updateZoom = (zoomKey: string, delta: number, reset = false) => {
    setImageZooms((prev) => {
      if (reset) {
        return { ...prev, [zoomKey]: 1 };
      }
      const current = prev[zoomKey] !== undefined ? prev[zoomKey] : 1;
      const next = Math.min(
        Math.max(Number((current + delta).toFixed(2)), 0.5),
        3
      );
      return { ...prev, [zoomKey]: next };
    });
  };

  const handleDownloadImage = (imageUrl: string | undefined) => {
    if (!imageUrl) return;
    const proxyDownloadUrl = `/api/download?url=${encodeURIComponent(imageUrl)}`;
    const link = document.createElement("a");
    link.href = proxyDownloadUrl;
    link.download = `architecture-diagram-${Date.now()}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const renderArchitectureImage = (
    imageUrl: string | undefined,
    messageId: string,
    index: number
  ) => {
    const zoomKey = `${messageId}-${index}`;
    const zoom = imageZooms[zoomKey] !== undefined ? imageZooms[zoomKey] : 1;
    const zoomPercent = Math.round(zoom * 100);

    const controlButtonStyle: React.CSSProperties = {
      borderRadius: "4px",
      padding: "5px 10px",
      fontSize: "12px",
      cursor: "pointer",
      lineHeight: 1,
      userSelect: "none",
      background: "var(--bg-input)",
      color: "var(--text-main)",
      border: "1px solid var(--border-color)",
    };

    return (
      <div
        key={index}
        className="artifact-card"
        style={{ marginBottom: "16px", overflow: "hidden" }}
      >
        <div
          className="artifact-header"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "8px",
            flexWrap: "wrap",
            background: "var(--bg-card)",
            color: "var(--text-muted)",
          }}
        >
          <span>Architecture Diagram</span>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              position: "relative",
              zIndex: 2,
            }}
          >
            <button
              type="button"
              onClick={() => updateZoom(zoomKey, -0.25)}
              style={controlButtonStyle}
              title="Zoom Out"
            >
              −
            </button>
            <span
              style={{
                fontSize: "12px",
                minWidth: "44px",
                textAlign: "center",
                fontWeight: 600,
                color: "var(--text-main)",
              }}
            >
              {zoomPercent}%
            </span>
            <button
              type="button"
              onClick={() => updateZoom(zoomKey, 0.25)}
              style={controlButtonStyle}
              title="Zoom In"
            >
              +
            </button>
            <button
              type="button"
              onClick={() => updateZoom(zoomKey, 0, true)}
              style={controlButtonStyle}
              title="Reset Zoom"
            >
              Reset
            </button>
            <button
              type="button"
              onClick={() => handleDownloadImage(imageUrl)}
              style={{
                ...controlButtonStyle,
                fontWeight: 600,
                background: "#3b82f6",
                color: "#ffffff",
                border: "none",
              }}
              title="Download Diagram"
            >
              ⬇ Download
            </button>
          </div>
        </div>

        <div
          className="image-wrapper"
          style={{ overflow: "auto", maxHeight: "540px" }}
        >
          <div
            style={{
              width: "100%",
              transform: `scale(${zoom})`,
              transformOrigin: "top left",
              transition: "transform 0.15s ease-out",
            }}
          >
            <img src={imageUrl} alt="Generated Diagram" />
          </div>
        </div>
      </div>
    );
  };

  const handleDecision = async (
    approvalId: string,
    initialStatus: string,
    decision: "APPROVE" | "REJECT"
  ) => {
    setApprovalStates((prev) => ({
      ...prev,
      [approvalId]: {
        status: prev[approvalId]?.status ? prev[approvalId].status : initialStatus,
        isProcessing: true,
        resultMsg: "",
      },
    }));

    try {
      const response = await fetch(`/api/approvals/${approvalId}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || data.message || "Decision failed");
      }

      const nextStatus = data.approval?.status
        ? data.approval.status
        : decision === "APPROVE"
        ? "APPROVED"
        : "REJECTED";

      setApprovalStates((prev) => ({
        ...prev,
        [approvalId]: {
          status: nextStatus,
          isProcessing: false,
          resultMsg: data.message ? data.message : "Decision processed successfully.",
        },
      }));
    } catch (error: any) {
      alert(`Error: ${error.message}`);
      setApprovalStates((prev) => ({
        ...prev,
        [approvalId]: {
          status: prev[approvalId]?.status ? prev[approvalId].status : initialStatus,
          isProcessing: false,
          resultMsg: "",
        },
      }));
    }
  };

  const renderApprovalCard = (approvalData: any, key: number) => {
    if (!approvalData) return null;
    const approvalId = approvalData.approval_id;
    const initialStatus = approvalData.status ? approvalData.status : "PENDING";
    const tracked = approvalStates[approvalId];

    const currentStatus = tracked ? tracked.status : initialStatus;
    const isProcessing = tracked ? tracked.isProcessing : false;
    const resultMsg = tracked ? tracked.resultMsg : "";
    const isPending = currentStatus.toUpperCase() === "PENDING";

    const args = approvalData.arguments || {};
    const toolLabel = String(approvalData.tool || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());

    return (
      <div
        key={key}
        className="artifact-card"
        style={{
          borderLeft: isPending ? "4px solid #f59e0b" : "4px solid #10b981",
          marginBottom: "16px",
        }}
      >
        <div
          className="artifact-header"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <span>⚠️ Action Requires Approval</span>
          <span
            style={{
              fontSize: "10px",
              fontWeight: 700,
              padding: "3px 8px",
              borderRadius: "4px",
              letterSpacing: "0.05em",
              background: "var(--bg-input)",
              color: "var(--text-main)",
            }}
          >
            {currentStatus}
          </span>
        </div>

        <div style={{ padding: "14px", fontSize: "14px", lineHeight: "1.6" }}>
          <p style={{ margin: "0 0 10px 0" }}>
            Request to execute <strong>{toolLabel}</strong> via{" "}
            <span style={{ textTransform: "capitalize", fontWeight: 600 }}>
              {approvalData.provider}
            </span>
            :
          </p>

          <div
            style={{
              padding: "10px 14px",
              borderRadius: "6px",
              fontSize: "13px",
              background: "var(--bg-input)",
              border: "1px solid var(--border-color)",
            }}
          >
            {args.service && (
              <div>
                <strong>Service:</strong> {args.service}
              </div>
            )}
            {args.environment && (
              <div>
                <strong>Environment:</strong> {args.environment}
              </div>
            )}
            {args.target_version && (
              <div>
                <strong>Target Version:</strong> {args.target_version}
              </div>
            )}

            {Object.entries(args)
              .filter(
                ([k]) =>
                  !["service", "environment", "target_version"].includes(k)
              )
              .map(([k, v]) => (
                <div key={k}>
                  <strong style={{ textTransform: "capitalize" }}>
                    {k.replace(/_/g, " ")}:
                  </strong>{" "}
                  {String(v)}
                </div>
              ))}
          </div>
        </div>

        {isPending ? (
          <div
            style={{
              display: "flex",
              gap: "8px",
              padding: "12px",
            }}
          >
            <button
              type="button"
              disabled={isProcessing}
              onClick={() => handleDecision(approvalId, initialStatus, "APPROVE")}
              style={{
                flex: 1,
                padding: "8px",
                borderRadius: "4px",
                cursor: isProcessing ? "wait" : "pointer",
                border: "none",
                fontWeight: 600,
                background: "#3b82f6",
                color: "#ffffff",
              }}
            >
              {isProcessing ? "Processing..." : "Approve"}
            </button>
            <button
              type="button"
              disabled={isProcessing}
              onClick={() => handleDecision(approvalId, initialStatus, "REJECT")}
              style={{
                flex: 1,
                padding: "8px",
                borderRadius: "4px",
                cursor: isProcessing ? "wait" : "pointer",
                fontWeight: 600,
                background: "var(--bg-input)",
                color: "var(--text-main)",
                border: "1px solid var(--border-color)",
              }}
            >
              Reject
            </button>
          </div>
        ) : (
          <div
            style={{
              padding: "12px",
              fontSize: "12px",
              textAlign: "center",
              color: "var(--text-muted)",
            }}
          >
            {resultMsg
              ? resultMsg
              : `This request was ${currentStatus.toLowerCase()}.`}
          </div>
        )}
      </div>
    );
  };

  const createNewChat = () => {
    const newSession: ChatSession = {
      id: `local-${Date.now()}`,
      title: "New conversation",
      messages: [{ ...INITIAL_MESSAGE, id: `initial-${Date.now()}` }],
      createdAt: Date.now(),
    };
    setSessions((prev) => [newSession, ...prev]);
    setActiveSessionId(newSession.id);
    setInput("");
  };

  const updateActiveMessages = (
    updater: (messages: Message[]) => Message[],
    targetId: string = activeSessionId
  ) => {
    setSessions((prev) =>
      prev.map((session) =>
        session.id === targetId
          ? { ...session, messages: updater(session.messages) }
          : session
      )
    );
  };

  // Reusable submit function for both text input and suggested question chips
  const submitMessage = async (rawQuery: string) => {
    const userMessage = rawQuery.trim();
    if (!userMessage || isLoading) return;

    const currentSessionId = activeSessionId;

    const userMessageObject: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      text: userMessage,
    };

    updateActiveMessages((prev) => [...prev, userMessageObject], currentSessionId);
    setInput("");
    setIsLoading(true);

    setSessions((prev) =>
      prev.map((session) => {
        if (
          session.id === currentSessionId &&
          session.title === "New conversation"
        ) {
          return {
            ...session,
            title:
              userMessage.length > 42
                ? `${userMessage.substring(0, 42)}...`
                : userMessage,
          };
        }
        return session;
      })
    );

    try {
      const data = await sendQuery(userMessage, currentSessionId);

      const returnedBlocks = data.data?.blocks
        ? data.data.blocks
        : [{ type: "text", content: "The API returned an empty blocks array." }];

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        blocks: returnedBlocks,
      };

      const resolvedSessionId = data.session_id || currentSessionId;

      setSessions((prev) =>
        prev.map((session) =>
          session.id === currentSessionId
            ? {
                ...session,
                id: resolvedSessionId,
                messages: [...session.messages, assistantMessage],
              }
            : session
        )
      );

      if (resolvedSessionId !== currentSessionId) {
        setActiveSessionId(resolvedSessionId);
      }
    } catch (error) {
      console.error("API error:", error);
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: "assistant",
        blocks: [
          {
            type: "text",
            content:
              error instanceof Error
                ? `Backend error: ${error.message}`
                : "Unknown backend error.",
          },
        ],
      };
      updateActiveMessages((prev) => [...prev, errorMessage], currentSessionId);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    await submitMessage(input);
  };

  const handleInputKeyDown = (
    event: React.KeyboardEvent<HTMLTextAreaElement>
  ) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isLoading && input.trim()) {
        submitMessage(input);
      }
    }
  };

  // Show suggested questions only when no user messages have been sent yet in this session
  const showSuggestions =
    !isLoading && !messages.some((m) => m.role === "user");

  return (
    <div className="app-shell">
      {/* SIDEBAR */}
      <aside className={`sidebar ${sidebarOpen ? "" : "sidebar-collapsed"}`}>
        <div className="sidebar-top">
          <div className="sidebar-header-row">
            <button
              className="sidebar-toggle-btn"
              onClick={() => setSidebarOpen((prev) => !prev)}
              type="button"
              title="Toggle Sidebar"
            >
              ☰
            </button>
            {sidebarOpen && (
              <button
                className="new-chat-button"
                onClick={createNewChat}
                type="button"
                title="New Chat"
              >
                <span className="new-chat-icon">+</span>
                <span>New Chat</span>
              </button>
            )}
          </div>

          {!sidebarOpen && (
            <button
              className="new-chat-button-collapsed"
              onClick={createNewChat}
              type="button"
              title="New Chat"
            >
              +
            </button>
          )}
        </div>

        {sidebarOpen && (
          <>
            <button
              className="history-header"
              onClick={() => setHistoryOpen((prev) => !prev)}
              type="button"
            >
              <span>History</span>
              <span
                className={`history-chevron ${
                  historyOpen ? "history-chevron-open" : ""
                }`}
              >
                ›
              </span>
            </button>

            {historyOpen && (
              <div className="history-list">
                {sessions.map((session) => (
                  <button
                    key={session.id}
                    type="button"
                    className={`history-item ${
                      session.id === activeSessionId
                        ? "history-item-active"
                        : ""
                    }`}
                    onClick={() => setActiveSessionId(session.id)}
                  >
                    <span className="history-item-title">{session.title}</span>
                  </button>
                ))}
              </div>
            )}
          </>
        )}

        <div className="sidebar-footer">
          <div className="sidebar-footer-row">
            {sidebarOpen && <span className="footer-label">Theme</span>}
            <button
              onClick={() => setDarkMode(!darkMode)}
              className="theme-toggle-btn"
              type="button"
              title="Toggle Theme"
            >
              {darkMode ? "☀️" : "🌙"}
            </button>
          </div>

          {sidebarOpen && (
            <div className="tester-box">
              <label className="tester-label">Tester Name</label>
              <input
                type="text"
                readOnly
                value="Hackathon Judge"
                className="tester-input"
              />
            </div>
          )}
        </div>
      </aside>

      {/* MAIN CHAT AREA */}
      <main className="chat-area">
        <header className="chat-header">
          <div className="chat-header-title">Enterprise Assistant</div>
          <div style={{ fontSize: "11px", fontFamily: "monospace", opacity: 0.6 }}>
            Session: {activeSessionId.startsWith("local-") ? "New" : activeSessionId.slice(0, 8)}
          </div>
        </header>

        <section className="messages-container">
          <div className="messages-inner">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`message-row ${
                  message.role === "user"
                    ? "message-row-user"
                    : "message-row-assistant"
                }`}
              >
                {message.role === "assistant" && (
                  <div className="assistant-avatar">AI</div>
                )}

                <div
                  className={`message-content ${
                    message.role === "user"
                      ? "user-content"
                      : "assistant-content"
                  }`}
                >
                  {message.role === "user" && (
                    <div className="message-text">{message.text}</div>
                  )}

                  {message.role === "assistant" &&
                    message.blocks?.map((block, index) => {
                      switch (block.type) {
                        case "text": {
                          const textContent = block.content ? block.content : "";
                          return (
                            <div
                              key={index}
                              className="message-text"
                              style={{ marginBottom: "16px" }}
                            >
                              {React.createElement(
                                ReactMarkdown,
                                { components: markdownComponentsConfig },
                                textContent
                              )}
                            </div>
                          );
                        }
                        case "mermaid":
                          return renderCollapsibleWorkflow(block.content, index);
                        case "image":
                          return renderArchitectureImage(
                            block.url,
                            message.id,
                            index
                          );
                        case "document":
                          return (
                            <div
                              key={index}
                              className="artifact-card"
                              style={{ marginBottom: "16px", padding: "16px" }}
                            >
                              <a
                                href={`/api/download?url=${encodeURIComponent(
                                  block.url ? block.url : ""
                                )}`}
                                style={{
                                  textDecoration: "none",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "8px",
                                  fontWeight: 500,
                                  fontSize: "13px",
                                  color: "#3b82f6",
                                }}
                              >
                                📄 Download Generated Document
                              </a>
                            </div>
                          );
                        case "structured": {
                          if (
                            block.data &&
                            block.data.approval_required &&
                            block.data.approval
                          ) {
                            return renderApprovalCard(block.data.approval, index);
                          }
                          const hasTextBlock = message.blocks?.some(
                            (b) => b.type === "text"
                          );
                          if (hasTextBlock) {
                            return null;
                          }
                          const mcpContent = block.data?.content;
                          const extractedText = Array.isArray(mcpContent)
                            ? mcpContent
                                .map((item: any) => item.text || JSON.stringify(item))
                                .join("\n\n")
                            : block.content || JSON.stringify(block.data, null, 2);

                          return (
                            <div
                              key={index}
                              className="message-text"
                              style={{ marginBottom: "16px" }}
                            >
                              {React.createElement(
                                ReactMarkdown,
                                { components: markdownComponentsConfig },
                                extractedText
                              )}
                            </div>
                          );
                        }
                        case "approval":
                          return renderApprovalCard(block.data, index);
                        default:
                          return null;
                      }
                    })}
                </div>
              </div>
            ))}

            {/* Clickable Suggested Starter Question Tags */}
            {showSuggestions && (
              <div className="suggested-questions-container">
                <div className="suggested-questions-label">
                  <span>✨ Suggested Questions</span>
                </div>
                <div className="suggested-questions">
                  {SUGGESTED_QUESTIONS.map((question, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className="suggested-chip"
                      onClick={() => submitMessage(question)}
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Gemini Cascading Dot Loader */}
            {isLoading && (
              <div className="message-row message-row-assistant">
                <div className="assistant-avatar">AI</div>
                <div className="assistant-content">
                  <div className="gemini-chat-loader">
                    <div className="gemini-dot"></div>
                    <div className="gemini-dot"></div>
                    <div className="gemini-dot"></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </section>

        <footer className="input-area">
          <form className="chat-input-wrapper" onSubmit={handleSubmit}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder="Ask your queries..."
              rows={1}
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="send-button"
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M22 2L11 13"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M22 2L15 22L11 13L2 9L22 2Z"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </form>
          <div className="input-disclaimer">
            AI-generated responses may require verification before execution.
          </div>
        </footer>
      </main>
    </div>
  );
}