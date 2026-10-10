function rememberReturn(key: string, path: string, skip: (path: string) => boolean) {
  if (typeof window === "undefined") return;
  if (!path || skip(path)) return;
  try {
    sessionStorage.setItem(key, path);
  } catch {
    // Private browsing can reject sessionStorage; the close button falls back.
  }
}

function readReturn(key: string, skip: (path: string) => boolean) {
  if (typeof window === "undefined") return "/status";
  try {
    const stored = sessionStorage.getItem(key);
    if (stored && stored.startsWith("/") && !stored.startsWith("//") && !skip(stored)) {
      return stored;
    }
  } catch {
    // Same fallback as a missing entry.
  }
  return "/status";
}

function isTutorialPath(path: string) {
  return path === "/tutorial" || path.startsWith("/tutorial/");
}

function isHarnessPath(path: string) {
  return path === "/harness" || path.startsWith("/harness/");
}

export function rememberTutorialReturn(path: string) {
  rememberReturn("tutorial-return-to", path, isTutorialPath);
}

export function readTutorialReturn() {
  return readReturn("tutorial-return-to", isTutorialPath);
}

export function rememberHarnessReturn(path: string) {
  rememberReturn("harness-return-to", path, isHarnessPath);
}

export function readHarnessReturn() {
  return readReturn("harness-return-to", isHarnessPath);
}
