import type { ReactNode } from "react";
import { FaGithub } from "react-icons/fa6";
import Link from "next/link";
import { AppNav } from "../components/app-nav";
import { HarnessButton, HarnessDialog } from "../components/harness/harness-dialog";
import { HarnessProvider } from "../components/harness/harness-context";
import { SettingsButton, SettingsDialog } from "../components/settings/settings-dialog";
import { SettingsProvider } from "../components/settings/settings-context";
import { LanguageButton } from "../components/language-button";
import { TutorialButton } from "../components/tutorial-button";
import "./globals.css";

export const metadata = {
  title: "Harness-driven agentic LCA",
  description: "Pi SDK unified runtime control panel",
  icons: {
    icon: "/brand-mark.svg",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <SettingsProvider>
          <HarnessProvider>
            <div className="app-frame">
              <header className="app-header">
                <div className="app-header-bar">
                  <div className="app-header-title">
                    <h1>
                      <Link className="app-header-home" href="/status">
                        <img className="title-mark" src="/brand-mark.svg" alt="" />
                        Harness-driven agentic LCA
                      </Link>
                    </h1>
                  </div>
                  <div className="app-header-actions">
                    <LanguageButton />
                    <TutorialButton />
                    <HarnessButton />
                    <SettingsButton />
                    <span className="app-header-divider" aria-hidden="true" />
                    <a
                      className="app-header-github"
                      href="https://github.com/mrzed891194322/Harness-driven-LCA-dev-agents"
                      target="_blank"
                      rel="noreferrer"
                      aria-label="GitHub"
                      title="github.com/mrzed891194322/Harness-driven-LCA-dev-agents"
                    >
                      <FaGithub size={18} aria-hidden="true" />
                    </a>
                  </div>
                </div>
              </header>
              <div className="app-shell">
                <AppNav />
                {children}
              </div>
            </div>
            <HarnessDialog />
            <SettingsDialog />
          </HarnessProvider>
        </SettingsProvider>
      </body>
    </html>
  );
}
