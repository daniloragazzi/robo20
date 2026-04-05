import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-screen flex-col items-center justify-center bg-zinc-950 p-8 text-center">
          <h1 className="mb-4 text-xl font-bold text-red-500">Erro na aplicação</h1>
          <pre className="max-w-2xl overflow-auto whitespace-pre-wrap rounded bg-zinc-900 p-4 text-left text-sm text-red-400">
            {this.state.error.message}
            {"\n\n"}
            {this.state.error.stack}
          </pre>
          <button
            className="mt-4 rounded bg-zinc-700 px-4 py-2 text-sm text-white hover:bg-zinc-600"
            onClick={() => window.location.reload()}
          >
            Recarregar
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
