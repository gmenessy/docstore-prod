import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";

// Runtime config from env (injected by nginx at container start)
// Defaults to same-origin /api/v1 which works with nginx reverse proxy
window.__DOCSTORE_API__ = window.__DOCSTORE_API__ || "/api/v1";
window.__DOCSTORE_KEY__ = window.__DOCSTORE_KEY__ || "";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<React.StrictMode><App /></React.StrictMode>);
