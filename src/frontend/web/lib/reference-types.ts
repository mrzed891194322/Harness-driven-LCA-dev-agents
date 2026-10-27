export type ReferenceType = "knowledge" | "bom" | "lci";

export const REFERENCE_TYPES: ReferenceType[] = ["knowledge", "bom", "lci"];

export type ReferenceFile = {
  name: string;
  size: number;
  type?: ReferenceType;
  note?: string;
  path?: string;
};

export function normalizeReferenceType(value: string | undefined): ReferenceType {
  const key = (value || "").trim().toLowerCase();
  if (key === "bom" || key === "lci") return key;
  return "knowledge";
}

export function referenceRowKey(file: ReferenceFile): string {
  return `${normalizeReferenceType(file.type)}:${file.name}`;
}

export function referencesPayload(files: ReferenceFile[]): { name: string; type: ReferenceType }[] {
  return files.map((file) => ({
    name: file.name,
    type: normalizeReferenceType(file.type),
  }));
}
