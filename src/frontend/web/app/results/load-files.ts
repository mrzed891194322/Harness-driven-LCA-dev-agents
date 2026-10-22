export type ResultFile = {
  path: string;
  kind: "markdown" | "json" | "text" | "too-large";
  size: number;
  text: string;
};
