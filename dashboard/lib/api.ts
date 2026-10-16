const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function getApiHealth(): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE_URL}/api/v1/health`, { cache: "no-store" });
  if (!response.ok) throw new Error(`API health check failed: ${response.status}`);
  return response.json() as Promise<{ status: string }>;
}
