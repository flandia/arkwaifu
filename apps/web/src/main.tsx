import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import "@fontsource-variable/atkinson-hyperlegible-next";
import "./i18n";
import App from "./App";
import { BackgroundMotionProvider } from "./shared/BackgroundMotion";
import "./styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("Missing application root");

createRoot(root).render(
  <StrictMode>
    <BrowserRouter useTransitions={false}>
      <BackgroundMotionProvider>
        <App />
      </BackgroundMotionProvider>
    </BrowserRouter>
  </StrictMode>,
);
