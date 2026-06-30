import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
};

type State = {
  error: Error | null;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <main className="app-shell" aria-labelledby="error-boundary-title">
          <div className="state-card" role="alert" aria-live="assertive">
            <h2 id="error-boundary-title">Something went wrong</h2>
            <p className="muted">{this.state.error.message}</p>
            <button type="button" className="secondary-button" onClick={this.handleReset}>
              Try again
            </button>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}
