import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  /** The boundary resets when this changes, so navigating away from a broken page recovers the console. */
  resetKey: string;
  children: ReactNode;
}

interface State {
  failedKey: string | null;
  message: string | null;
}

/**
 * Keeps one broken page from blanking the whole console: the navigation stays usable and the person
 * sees what failed. Rendering errors only; failed requests are handled by each page's own error state.
 */
export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { failedKey: null, message: null };

  static getDerivedStateFromError(error: unknown): Partial<State> {
    return { message: error instanceof Error ? error.message : "Unknown error" };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    this.setState({ failedKey: this.props.resetKey });
    console.error("Page crashed:", error, info.componentStack);
  }

  render() {
    // getDerivedStateFromError runs before componentDidCatch records the key, so a null key still means "failed".
    const failing = this.state.message !== null && (this.state.failedKey === null || this.state.failedKey === this.props.resetKey);
    if (!failing) return this.props.children;
    return (
      <section className="surface-panel error-state" role="alert">
        <h3>Something went wrong on this page</h3>
        <p>{this.state.message}</p>
        <button type="button" className="btn-outline" onClick={() => window.location.reload()}>
          Reload page
        </button>
      </section>
    );
  }

  componentDidUpdate(previous: Props): void {
    if (previous.resetKey !== this.props.resetKey && this.state.message !== null) {
      this.setState({ failedKey: null, message: null });
    }
  }
}
