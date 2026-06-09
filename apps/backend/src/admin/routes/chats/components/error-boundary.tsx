import { Heading, Text } from "@medusajs/ui";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { WarningIcon } from "../icons";

type ChatPanelErrorBoundaryProps = {
  children: ReactNode;
  strings: {
    panelTitle: string;
    panelDescription: string;
  };
};

type ChatPanelErrorBoundaryState = {
  error: Error | null;
};

export class ChatPanelErrorBoundary extends Component<
  ChatPanelErrorBoundaryProps,
  ChatPanelErrorBoundaryState
> {
  state: ChatPanelErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("CHAT_PANEL_RENDER_ERROR", error, errorInfo);
  }

  componentDidUpdate(prevProps: ChatPanelErrorBoundaryProps) {
    if (this.state.error && prevProps.children !== this.props.children) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 bg-ui-bg-subtle p-6 text-ui-fg-base">
          <WarningIcon className="h-10 w-10 text-ui-fg-error" />
          <Heading level="h2" className="text-lg">
            {this.props.strings.panelTitle}
          </Heading>
          <Text size="small" className="max-w-md text-center text-ui-fg-muted">
            {this.props.strings.panelDescription}
          </Text>
        </div>
      );
    }

    return this.props.children;
  }
}
