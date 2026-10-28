import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "./api";

type Farm = {
  farm_id?: number;
  id?: number;
  farm_name?: string;
  name?: string;
  location?: string;
  owner_id?: number;
};


type LatestReview = {
  id: number;
  advisor_id: number;
  comments: string;
  recommendations: string;
  status: "reviewed" | "follow_up_required";
  follow_up_date: string | null;
  created_at: string;
};

type AdvisoryRequest = {
  id: number;
  farm_id: number;
  farmer_id: number;
  advisor_id?: number | null;
  subject: string;
  description: string;
  category: string;
  priority: string;
  status: string;
  created_at: string;
  updated_at?: string;
  latest_review: LatestReview | null;
};

type ReviewContext = {
  request: {
    id: number;
    subject: string;
    description: string;
    category: string;
    priority: string;
    status: string;
    created_at: string;
  };
  farm: {
    id: number;
    name: string;
    location?: string | null;
    area?: number | null;
    area_unit?: string | null;
  };
  fields: {
    id: number;
    name: string;
    area?: number | null;
    soil_type?: string | null;
    irrigation_method?: string | null;
    crop_cycles: {
      id: number;
      crop_name: string;
      variety?: string | null;
      planting_date?: string | null;
      status: string;
      expected_harvest_date?: string | null;
    }[];
    recent_soil_tests: {
      id: number;
      test_date: string;
      ph?: number | null;
      nitrogen?: number | null;
      phosphorus?: number | null;
      potassium?: number | null;
      npk_unit?: string | null;
      notes?: string | null;
    }[];
  }[];
};

type AdminUser = {
  id: number;
  email: string;
  full_name: string;
  role: "farmer" | "advisor" | "farm_manager" | "admin";
};

type AuditLog = {
  id: number;
  actor_user_id?: number | null;
  action: string;
  entity_type: string;
  entity_id?: number | null;
  created_at: string;
};

function Message({ text }: { text: string }) {
  return text ? (
    <p role="status" className="my-3 rounded-lg bg-green-50 p-3 text-sm text-green-800">
      {text}
    </p>
  ) : null;
}

function ErrorMessage({ text }: { text: string }) {
  return text ? (
    <p role="alert" className="my-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">
      {text}
    </p>
  ) : null;
}

function StatusBadge({ value }: { value: string }) {
  return (
    <span className="inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">
      {value.replace("_", " ")}
    </span>
  );
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="portal-panel">
      <h2 className="mb-4 text-lg font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return <p className="py-5 text-sm text-slate-500">{children}</p>;
}


export function FarmerAdvisorPanel({
  token,
  farms,
}: {
  token: string;
  farms: { id: number; name: string }[];
}) {
  const [requests, setRequests] = useState<AdvisoryRequest[]>([]);
  const [selectedFarm, setSelectedFarm] = useState("");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("general");
  const [priority, setPriority] = useState("normal");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await apiRequest<AdvisoryRequest[]>(
        token,
        "/api/v1/advisory/reviews",
      );
      setRequests(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load review requests");
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");

    try {
      await apiRequest(token, "/api/v1/advisory/reviews", {
        method: "POST",
        body: JSON.stringify({
          farm_id: Number(selectedFarm),
          subject: subject.trim(),
          description: description.trim(),
          category,
          priority,
        }),
      });

      setSubject("");
      setDescription("");
      setSelectedFarm("");
      setMessage("Review request submitted successfully.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="portal-stack">
      <div>
        <h1 className="text-2xl font-bold">Agricultural Advisor</h1>
        <p className="mt-1 text-sm text-slate-600">
          Submit a farm-related question and track expert reviews.
        </p>
      </div>

      <Panel title="Request agricultural advice">
        {farms.length === 0 ? (
          <EmptyState>Add a farm before submitting a review request.</EmptyState>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <label className="block text-sm font-medium">
              Farm
              <select
                required
                value={selectedFarm}
                onChange={(e) => setSelectedFarm(e.target.value)}
                className="mt-1 block w-full rounded-lg border p-2.5"
              >
                <option value="">Choose a farm</option>
                {farms.map((farm) => (
                  <option key={farm.id} value={farm.id}>
                    {farm.name}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm font-medium">
              Subject
              <input
                required
                minLength={3}
                maxLength={160}
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="mt-1 block w-full rounded-lg border p-2.5"
                placeholder="e.g. Yellowing leaves in my rice crop"
              />
            </label>

            <label className="block text-sm font-medium">
              Category
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="mt-1 block w-full rounded-lg border p-2.5"
              >
                {[
                  "general",
                  "crop_health",
                  "soil",
                  "irrigation",
                  "pest",
                  "weather",
                  "market",
                ].map((item) => (
                  <option key={item} value={item}>
                    {item.replace("_", " ")}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-sm font-medium">
              Priority
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="mt-1 block w-full rounded-lg border p-2.5"
              >
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </label>

            <label className="block text-sm font-medium">
              Describe the issue
              <textarea
                required
                minLength={10}
                maxLength={5000}
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="mt-1 block w-full rounded-lg border p-2.5"
                placeholder="Describe the crop stage, symptoms, recent weather and actions already tried."
              />
            </label>

            <button
              disabled={busy || !selectedFarm}
              className="rounded-lg bg-green-700 px-4 py-2.5 font-medium text-white disabled:opacity-50"
            >
              {busy ? "Submitting..." : "Submit review request"}
            </button>
          </form>
        )}
        <Message text={message} />
        <ErrorMessage text={error} />
      </Panel>

      <Panel title="My review requests">
        {requests.length === 0 ? (
          <EmptyState>Your submitted review requests will appear here.</EmptyState>
        ) : (
          <div className="space-y-4">
            {requests.map((request) => (
              <article key={request.id} className="rounded-lg border p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <h3 className="font-semibold">{request.subject}</h3>
                  <StatusBadge value={request.status} />
                </div>

                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600">
                  {request.description}
                </p>

                <p className="mt-2 text-xs text-slate-500">
                  Farm #{request.farm_id} · {request.category} · {request.priority}
                </p>

                {request.latest_review ? (
                  <div className="mt-4 rounded-lg bg-green-50 p-4">
                    <h4 className="font-semibold text-green-900">
                      Advisor response
                    </h4>
                    <p className="mt-2 whitespace-pre-wrap text-sm">
                      {request.latest_review.comments}
                    </p>

                    {request.latest_review.recommendations && (
                      <>
                        <h5 className="mt-3 text-sm font-semibold">
                          Recommendations
                        </h5>
                        <p className="mt-1 whitespace-pre-wrap text-sm">
                          {request.latest_review.recommendations}
                        </p>
                      </>
                    )}

                    <p className="mt-3 text-xs text-slate-600">
                      Review status: {request.latest_review.status.replace(/_/g, " ")}
                    </p>

                    {request.latest_review.follow_up_date && (
                      <p className="mt-1 text-xs text-slate-600">
                        Follow-up date: {request.latest_review.follow_up_date}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-slate-500">
                    Waiting for an advisor's review.
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}



export function AdvisorPortal({ token }: { token: string }) {
  const [requests, setRequests] = useState<AdvisoryRequest[]>([]);
  const [contexts, setContexts] = useState<Record<number, ReviewContext>>({});
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [recommendations, setRecommendations] = useState<Record<number, string>>({});
  const [actions, setActions] = useState<Record<number, string>>({});
  const [statuses, setStatuses] = useState<Record<number, string>>({});
  const [followUpDates, setFollowUpDates] = useState<Record<number, string>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await apiRequest<AdvisoryRequest[]>(
        token,
        "/api/v1/advisory/reviews",
      );
      setRequests(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load review requests");
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function loadContext(id: number) {
    setBusyId(id);
    setError("");
    try {
      const data = await apiRequest<ReviewContext>(
        token,
        `/api/v1/advisory/reviews/${id}/context`,
      );
      setContexts((old) => ({ ...old, [id]: data }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load farm context");
    } finally {
      setBusyId(null);
    }
  }

  async function submitReview(id: number) {
    const comments = (drafts[id] ?? "").trim();
    const recommendation = (recommendations[id] ?? "").trim();
    const status = statuses[id] ?? "reviewed";

    if (comments.length < 3) {
      setError("Comments must contain at least 3 characters.");
      return;
    }

    if (recommendation.length > 10000) {
      setError("Recommendations must not exceed 10,000 characters.");
      return;
    }

    const actionItems = (actions[id] ?? "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);

    if (actionItems.length > 50) {
      setError("Enter no more than 50 action items.");
      return;
    }

    setBusyId(id);
    setError("");
    setMessage("");

    try {
      await apiRequest(
        token,
        `/api/v1/advisory/reviews/${id}/responses`,
        {
          method: "POST",
          body: JSON.stringify({
            comments,
            recommendations: recommendation || null,
            action_items: actionItems,
            status,
            follow_up_date:
              status === "follow_up_required"
                ? followUpDates[id] || null
                : null,
          }),
        },
      );

      setDrafts((old) => ({ ...old, [id]: "" }));
      setRecommendations((old) => ({ ...old, [id]: "" }));
      setActions((old) => ({ ...old, [id]: "" }));
      setMessage(`Review submitted for request #${id}.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit review");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="portal-stack">
      <div>
        <h1 className="text-2xl font-bold">Advisor Portal</h1>
        <p className="mt-1 text-sm text-slate-600">
          Review assigned requests, inspect authorized farm context and submit
          recommendations.
        </p>
      </div>

      <ErrorMessage text={error} />
      <Message text={message} />

      <Panel title={`Review queue (${requests.length})`}>
        {requests.length === 0 ? (
          <EmptyState>
            No review requests are available for your assigned farms.
          </EmptyState>
        ) : (
          <div className="space-y-4">
            {requests.map((request) => {
              const context = contexts[request.id];

              return (
                <article key={request.id} className="rounded-lg border p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="font-semibold">{request.subject}</h3>
                    <StatusBadge value={request.status} />
                  </div>

                  <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600">
                    {request.description}
                  </p>

                  <p className="mt-2 text-xs text-slate-500">
                    Request #{request.id} · Farm #{request.farm_id} ·
                    Farmer #{request.farmer_id}
                  </p>

                  <button
                    type="button"
                    disabled={busyId === request.id}
                    onClick={() => void loadContext(request.id)}
                    className="mt-3 rounded-lg border px-3 py-2 text-sm font-medium disabled:opacity-50"
                  >
                    {busyId === request.id
                      ? "Loading..."
                      : context
                        ? "Refresh farm context"
                        : "View authorized farm context"}
                  </button>

                  {context && (
                    <div className="mt-3 space-y-3 rounded-lg bg-slate-50 p-4">
                      <div>
                        <h4 className="font-semibold">
                          {context.farm.name}
                        </h4>
                        <p className="text-sm text-slate-600">
                          {context.farm.location || "Location not provided"}
                          {context.farm.area != null
                            ? ` · ${context.farm.area} ${context.farm.area_unit || ""}`
                            : ""}
                        </p>
                      </div>

                      {context.fields.length === 0 ? (
                        <p className="text-sm text-slate-500">
                          No field records are available.
                        </p>
                      ) : (
                        context.fields.map((field) => (
                          <div
                            key={field.id}
                            className="rounded-lg border bg-white p-3"
                          >
                            <h5 className="font-medium">{field.name}</h5>
                            <p className="text-xs text-slate-500">
                              Field #{field.id}
                              {field.soil_type ? ` · Soil: ${field.soil_type}` : ""}
                              {field.irrigation_method
                                ? ` · Irrigation: ${field.irrigation_method}`
                                : ""}
                            </p>

                            <p className="mt-2 text-sm font-medium">
                              Crop cycles
                            </p>
                            {field.crop_cycles.length === 0 ? (
                              <p className="text-sm text-slate-500">
                                No crop cycles recorded.
                              </p>
                            ) : (
                              <ul className="list-disc pl-5 text-sm">
                                {field.crop_cycles.map((cycle) => (
                                  <li key={cycle.id}>
                                    {cycle.crop_name}
                                    {cycle.variety ? ` (${cycle.variety})` : ""}
                                    {" · "}
                                    {cycle.status}
                                    {cycle.planting_date
                                      ? ` · Planted ${cycle.planting_date}`
                                      : ""}
                                  </li>
                                ))}
                              </ul>
                            )}

                            <p className="mt-2 text-sm font-medium">
                              Recent soil tests
                            </p>
                            {field.recent_soil_tests.length === 0 ? (
                              <p className="text-sm text-slate-500">
                                No soil-test records available.
                              </p>
                            ) : (
                              <ul className="list-disc pl-5 text-sm">
                                {field.recent_soil_tests.map((soil) => (
                                  <li key={soil.id}>
                                    {soil.test_date}
                                    {soil.ph != null ? ` · pH ${soil.ph}` : ""}
                                    {soil.nitrogen != null
                                      ? ` · N ${soil.nitrogen}`
                                      : ""}
                                    {soil.phosphorus != null
                                      ? ` · P ${soil.phosphorus}`
                                      : ""}
                                    {soil.potassium != null
                                      ? ` · K ${soil.potassium}`
                                      : ""}
                                    {soil.npk_unit ? ` ${soil.npk_unit}` : ""}
                                    {soil.notes ? ` · ${soil.notes}` : ""}
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {request.latest_review && (
                    <div className="mt-3 rounded-lg bg-green-50 p-3">
                      <p className="text-sm font-semibold">
                        Previous review
                      </p>
                      <p className="mt-1 whitespace-pre-wrap text-sm">
                        {request.latest_review.comments}
                      </p>
                      {request.latest_review.recommendations && (
                        <p className="mt-2 whitespace-pre-wrap text-sm">
                          {request.latest_review.recommendations}
                        </p>
                      )}
                    </div>
                  )}

                  <div className="mt-4 space-y-3">
                    <label className="block text-sm font-medium">
                      Review comments (required)
                      <textarea
                        required
                        minLength={3}
                        maxLength={10000}
                        rows={3}
                        value={drafts[request.id] ?? ""}
                        onChange={(e) =>
                          setDrafts((old) => ({
                            ...old,
                            [request.id]: e.target.value,
                          }))
                        }
                        className="mt-1 block w-full rounded-lg border p-2.5"
                        placeholder="Record your assessment and observations."
                      />
                    </label>

                    <label className="block text-sm font-medium">
                      Recommendations (optional)
                      <textarea
                        maxLength={10000}
                        rows={3}
                        value={recommendations[request.id] ?? ""}
                        onChange={(e) =>
                          setRecommendations((old) => ({
                            ...old,
                            [request.id]: e.target.value,
                          }))
                        }
                        className="mt-1 block w-full rounded-lg border p-2.5"
                        placeholder="Suggested next steps and precautions."
                      />
                    </label>

                    <label className="block text-sm font-medium">
                      Action items (one per line, maximum 50)
                      <textarea
                        rows={3}
                        value={actions[request.id] ?? ""}
                        onChange={(e) =>
                          setActions((old) => ({
                            ...old,
                            [request.id]: e.target.value,
                          }))
                        }
                        className="mt-1 block w-full rounded-lg border p-2.5"
                        placeholder={"Inspect affected plants\nCheck soil moisture"}
                      />
                    </label>

                    <label className="block text-sm font-medium">
                      Review outcome
                      <select
                        value={statuses[request.id] ?? "reviewed"}
                        onChange={(e) =>
                          setStatuses((old) => ({
                            ...old,
                            [request.id]: e.target.value,
                          }))
                        }
                        className="mt-1 block w-full rounded-lg border p-2.5"
                      >
                        <option value="reviewed">Reviewed</option>
                        <option value="follow_up_required">
                          Follow-up required
                        </option>
                      </select>
                    </label>

                    {(statuses[request.id] ?? "reviewed") ===
                      "follow_up_required" && (
                      <label className="block text-sm font-medium">
                        Follow-up date (optional)
                        <input
                          type="date"
                          value={followUpDates[request.id] ?? ""}
                          onChange={(e) =>
                            setFollowUpDates((old) => ({
                              ...old,
                              [request.id]: e.target.value,
                            }))
                          }
                          className="mt-1 block w-full rounded-lg border p-2.5"
                        />
                      </label>
                    )}

                    <button
                      type="button"
                      disabled={busyId === request.id}
                      onClick={() => void submitReview(request.id)}
                      className="rounded-lg bg-green-700 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-50"
                    >
                      {busyId === request.id
                        ? "Submitting..."
                        : "Submit advisor review"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}


export function AdminPortal({ token }: { token: string }) {
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [farms, setFarms] = useState<Farm[]>([]);
  const [assignFarm, setAssignFarm] = useState("");
  const [assignAdvisor, setAssignAdvisor] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [summaryData, userData, logData] = await Promise.all([
        apiRequest<Record<string, number>>(token, "/api/v1/admin/summary"),
        apiRequest<AdminUser[]>(token, "/api/v1/admin/users"),
        apiRequest<AuditLog[]>(token, "/api/v1/admin/audit-logs?limit=100"),
      ]);

      setSummary(summaryData);
      setUsers(userData);
      setLogs(logData);

      // The existing farmer farms endpoint is owner-scoped, so it must not
      // be used as an admin-wide farm listing. Load all farms through the
      // dedicated admin endpoint added in the next backend step.
      const farmData = await apiRequest<Farm[]>(
        token,
        "/api/v1/admin/farms",
      );
      setFarms(farmData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load admin data");
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  async function updateRole(user: AdminUser, role: AdminUser["role"]) {
    setError("");
    setMessage("");
    try {
      await apiRequest(token, `/api/v1/admin/users/${user.id}/role`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      });
      setMessage(`Updated ${user.email} to ${role}.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Role update failed");
    }
  }

  async function assign() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await apiRequest(
        token,
        `/api/v1/admin/farms/${Number(assignFarm)}/advisor`,
        {
          method: "POST",
          body: JSON.stringify({ advisor_id: Number(assignAdvisor) }),
        },
      );
      setMessage("Advisor assigned successfully.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assignment failed");
    } finally {
      setBusy(false);
    }
  }

  const advisors = users.filter((user) => user.role === "advisor");

  return (
    <div className="portal-stack">
      <div>
        <h1 className="text-2xl font-bold">Administration Portal</h1>
        <p className="mt-1 text-sm text-slate-600">
          Manage accounts, assign agricultural advisors and review audit activity.
        </p>
      </div>

      <ErrorMessage text={error} />
      <Message text={message} />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(summary).map(([key, value]) => (
          <div key={key} className="rounded-xl border bg-white p-4">
            <p className="text-sm capitalize text-slate-500">
              {key.replace(/_/g, " ")}
            </p>
            <p className="mt-1 text-2xl font-bold">{value}</p>
          </div>
        ))}
      </div>

      <Panel title="Assign an advisor to a farm">
        {farms.length === 0 || advisors.length === 0 ? (
          <EmptyState>
            You need at least one farm and one user with the advisor role.
            The farm list requires the admin farms endpoint.
          </EmptyState>
        ) : (
          <div className="space-y-3">
            <label className="block text-sm font-medium">
              Farm
              <select
                value={assignFarm}
                onChange={(e) => setAssignFarm(e.target.value)}
                className="mt-1 block w-full rounded-lg border p-2.5"
              >
                <option value="">Choose farm</option>
                {farms.map((farm) => {
                  const id = farm.farm_id ?? farm.id!;
                  return (
                    <option key={id} value={id}>
                      {farm.farm_name ?? farm.name ?? `Farm ${id}`}
                    </option>
                  );
                })}
              </select>
            </label>

            <label className="block text-sm font-medium">
              Advisor
              <select
                value={assignAdvisor}
                onChange={(e) => setAssignAdvisor(e.target.value)}
                className="mt-1 block w-full rounded-lg border p-2.5"
              >
                <option value="">Choose advisor</option>
                {advisors.map((advisor) => (
                  <option key={advisor.id} value={advisor.id}>
                    {advisor.full_name} — {advisor.email}
                  </option>
                ))}
              </select>
            </label>

            <button
              type="button"
              disabled={busy || !assignFarm || !assignAdvisor}
              onClick={() => void assign()}
              className="rounded-lg bg-green-700 px-4 py-2.5 text-white disabled:opacity-50"
            >
              {busy ? "Assigning…" : "Assign advisor"}
            </button>
          </div>
        )}
      </Panel>

      <Panel title="User management">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] text-left text-sm">
            <thead>
              <tr className="border-b text-slate-500">
                <th className="p-3">User</th>
                <th className="p-3">Email</th>
                <th className="p-3">Role</th>
                <th className="p-3">Change role</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-b last:border-0">
                  <td className="p-3">{user.full_name}</td>
                  <td className="p-3">{user.email}</td>
                  <td className="p-3"><StatusBadge value={user.role} /></td>
                  <td className="p-3">
                    <select
                      value={user.role}
                      onChange={(e) =>
                        void updateRole(user, e.target.value as AdminUser["role"])
                      }
                      className="rounded-md border p-2"
                    >
                      <option value="farmer">Farmer</option>
                      <option value="advisor">Advisor</option>
                      <option value="farm_manager">Farm manager</option>
                      <option value="admin">Admin</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Recent audit activity">
        {logs.length === 0 ? (
          <EmptyState>No audit events have been recorded yet.</EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[540px] text-left text-sm">
              <thead>
                <tr className="border-b text-slate-500">
                  <th className="p-3">Action</th>
                  <th className="p-3">Resource</th>
                  <th className="p-3">Actor</th>
                  <th className="p-3">Time</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b last:border-0">
                    <td className="p-3">{log.action}</td>
                    <td className="p-3">
                      {log.entity_type} {log.entity_id ?? ""}
                    </td>
                    <td className="p-3">{log.actor_user_id ?? "System"}</td>
                    <td className="p-3">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}