import type {
  ExtractRequest,
  PlanBundle,
  Health,
  Plan,
  PlanRequest,
  ReplanRequest,
  ReplanResponse,
  Resource,
  ResourceStatus,
  StatusUpdate,
  UserConstraints,
} from "./types";
export const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "/api").replace(
  /\/+$/,
  "",
);
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}
function describeErrorBody(text: string): string {
  try {
    const parsed: unknown = JSON.parse(text);
    if (parsed && typeof parsed === "object" && "detail" in parsed) {
      const detail = (
        parsed as {
          detail: unknown;
        }
      ).detail;
      return typeof detail === "string" ? detail : JSON.stringify(detail);
    }
  } catch {}
  return text;
}
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      signal: AbortSignal.timeout(30000),
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  } catch {
    throw new ApiError(
      0,
      `Could not reach the AidGraph API at ${API_BASE}. Is the backend running?`,
    );
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(
      res.status,
      describeErrorBody(text) || `${res.status} ${res.statusText}`,
    );
  }
  return (await res.json()) as T;
}
function post<TBody, TResponse>(
  path: string,
  body?: TBody,
): Promise<TResponse> {
  return request<TResponse>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
export function extract(text: string): Promise<UserConstraints> {
  return post<ExtractRequest, UserConstraints>("/extract", { text });
}
export function createPlan(body: PlanRequest): Promise<Plan> {
  return post<PlanRequest, Plan>("/plan", body);
}
export function replan(body: ReplanRequest): Promise<ReplanResponse> {
  return post<ReplanRequest, ReplanResponse>("/replan", body);
}
export function getResources(): Promise<Resource[]> {
  return request<Resource[]>("/resources");
}
export function setResourceStatus(
  id: string,
  status: ResourceStatus,
  capacity?: number,
): Promise<Resource> {
  const body: StatusUpdate =
    capacity === undefined ? { status } : { status, capacity };
  return request<Resource>(`/resources/${encodeURIComponent(id)}/status`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}
export function resetResources(): Promise<Resource[]> {
  return post<undefined, Resource[]>("/resources/reset");
}
export function getHealth(): Promise<Health> {
  return request<Health>("/health");
}
export function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message || "Something went wrong.";
  if (typeof err === "string") return err;
  return "Something went wrong.";
}
export function generatePlans(
  constraints: UserConstraints,
  now: string,
  previous_plan_id?: string,
): Promise<PlanBundle> {
  return post("/plans", { constraints, now, previous_plan_id });
}
