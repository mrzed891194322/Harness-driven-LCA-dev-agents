/** Validates a launch_spec against the generated JSON Schema before a session starts. */
import { LAUNCH_SPEC_SCHEMA, type SessionLaunchSpec } from "./spec.generated.js";

type Node = Record<string, any>;
const DEFS = (LAUNCH_SPEC_SCHEMA as Node).$defs as Record<string, Node>;

function typeOk(type: string, value: unknown): boolean {
  if (type === "object") return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  if (type === "array") return Array.isArray(value);
  if (type === "integer") return Number.isInteger(value);
  return typeof value === type;
}

function walk(schema: Node, value: unknown, at: string, errors: string[]): void {
  if (schema.$ref) {
    walk(DEFS[String(schema.$ref).split("/").pop() as string], value, at, errors);
    return;
  }
  if ("const" in schema && value !== schema.const) errors.push(`${at}: must be ${JSON.stringify(schema.const)}`);
  if (schema.enum && !schema.enum.includes(value)) errors.push(`${at}: must be one of ${schema.enum.join(", ")}`);
  if (schema.type && !typeOk(schema.type, value)) {
    errors.push(`${at}: must be ${schema.type}`);
    return;
  }
  if (schema.type === "array" && schema.items) {
    (value as unknown[]).forEach((item, i) => walk(schema.items, item, `${at}[${i}]`, errors));
  }
  if (schema.type === "object") {
    const obj = value as Record<string, unknown>;
    for (const key of schema.required ?? []) if (!(key in obj)) errors.push(`${at}.${key}: required`);
    for (const [key, item] of Object.entries(obj)) {
      const prop = schema.properties?.[key];
      if (prop) walk(prop, item, `${at}.${key}`, errors);
      else if (schema.additionalProperties === false) errors.push(`${at}.${key}: unknown field`);
      else if (schema.additionalProperties && typeof schema.additionalProperties === "object") {
        walk(schema.additionalProperties, item, `${at}.${key}`, errors);
      }
    }
  }
}

export function launchSpecErrors(value: unknown): string[] {
  const errors: string[] = [];
  walk(LAUNCH_SPEC_SCHEMA as Node, value, "launch_spec", errors);
  return errors;
}

export function checkedLaunchSpec(value: unknown): SessionLaunchSpec {
  const errors = launchSpecErrors(value);
  if (errors.length) throw new Error(`invalid launch_spec: ${errors.slice(0, 5).join("; ")}`);
  return value as SessionLaunchSpec;
}
