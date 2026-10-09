import type { ReactNode } from "react";
import { AppNav } from "../components/app-nav";
import { HarnessButton, HarnessDialog } from "../components/harness/harness-dialog";
import { HarnessProvider } from "../components/harness/harness-context";
import { SettingsButton, SettingsDialog } from "../components/settings/settings-dialog";
import { SettingsProvider } from "../components/settings/settings-context";
import "./globals.css";

export const metadata = {
  title: "Harness LCA",
  description: "Pi SDK unified runtime control panel",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <SettingsProvider>
          <HarnessProvider>
            <div className="app-shell">
              <header className="app-header">
                <div className="app-header-title">
                  <h1>Harness LCA</h1>
                  <a
                    className="app-header-repo"
                    href="https://github.com/mrzed891194322/Harness-driven-LCA-dev-agents"
                    target="_blank"
                    rel="noreferrer"
                  >
                    github.com/mrzed891194322/Harness-driven-LCA-dev-agents
                  </a>
                </div>
                <div className="app-header-actions">
                  <HarnessButton />
                  <SettingsButton />
                </div>
              </header>
              <AppNav />
              {children}
            </div>
            <HarnessDialog />
            <SettingsDialog />
          </HarnessProvider>
        </SettingsProvider>
      </body>
    </html>
  );
}
