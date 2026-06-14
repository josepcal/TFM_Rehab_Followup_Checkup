import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./App";
import { createBrowserAuthClient } from "./auth/authClient";
import "./styles.css";

const queryClient = new QueryClient();
const authClient = createBrowserAuthClient();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App authClient={authClient} />
    </QueryClientProvider>
  </React.StrictMode>,
);
