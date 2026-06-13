import { Component, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: string;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: "" };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error: error.message };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          padding: "40px",
          color: "rgba(255,255,255,0.7)",
          fontFamily: "'DM Sans', sans-serif",
          background: "#08080d",
        }}>
          <h2 style={{ color: "#ef4444", marginBottom: 12 }}>应用错误</h2>
          <p style={{ color: "rgba(255,255,255,0.5)", fontSize: 14, marginBottom: 20 }}>
            {this.state.error}
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: "10px 24px",
              border: "1px solid rgba(0,229,255,0.3)",
              borderRadius: 8,
              background: "rgba(0,229,255,0.08)",
              color: "#00e5ff",
              cursor: "pointer",
              fontFamily: "'DM Sans', sans-serif",
              fontSize: 14,
            }}
          >
            重新加载
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
