export function formatEnergy(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Not simulated";
  }
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}`;
}

export function formatDelta(value: number | null | undefined, unit: string, status?: string): string {
  if (status === "pending") {
    return "Running…";
  }
  if (status === "failed") {
    return "Failed";
  }
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Not available";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} ${unit}`;
}

export function neverInvented(value: number | null | undefined): boolean {
  return value === null || value === undefined;
}
