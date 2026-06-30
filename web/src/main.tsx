import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./App";
import { ErrorBoundary } from "./ErrorBoundary";
import { createBrowserAuthClient } from "./auth/authClient";
import "./styles.css";

async function bootstrap() {
  const queryClient = new QueryClient();
  const authClient = await createBrowserAuthClient();

  ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
    <React.StrictMode>
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <App authClient={authClient} />
        </QueryClientProvider>
      </ErrorBoundary>
    </React.StrictMode>,
  );
}

void bootstrap();
