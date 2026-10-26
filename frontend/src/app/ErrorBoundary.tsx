import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Phase 8 wires this to GlitchTip; until then keep it in the console.
    console.error("NOMAX UI crashed", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <main className="flex min-h-[100dvh] flex-col items-center justify-center gap-4 bg-slate-50 px-6 text-center">
        <div className="text-4xl">⚠️</div>
        <h1 className="text-lg font-bold text-slate-900">مشکلی پیش آمد</h1>
        <p className="max-w-sm text-sm leading-6 text-slate-500">
          صفحه به‌درستی بارگذاری نشد. یک‌بار دیگر تلاش کنید؛ اگر تکرار شد با پشتیبانی
          نومکس تماس بگیرید.
        </p>
        <button
          type="button"
          className="h-11 rounded-xl bg-brand-600 px-5 text-sm font-medium text-white"
          onClick={() => window.location.reload()}
        >
          تلاش دوباره
        </button>
      </main>
    );
  }
}
