import { API_BASE_URL, USE_MOCK_API } from "./config";

const mockState = {
  user: {
    id: "ca1ae1de-1d9f-5f8b-8840-15821a988dff",
    email: "demo1@healthmate.local",
    firstName: "Ольга",
    lastName: "Козлова",
    birthDate: "1957-11-22",
  },
  profile: {
    heightCm: 178,
    weightKg: 76.5,
    bloodType: "A+",
    diagnoses: [{ name: "Hypertension", diagnosedAt: "2020-05-12" }],
    allergies: [{ allergen: "Penicillin", reaction: "Rash" }],
    updatedAt: new Date().toISOString(),
  },
  medications: [
    {
      id: "07e715e3-a6c3-55cd-9042-94d3c55228a5",
      tradeName: "Ибупрофен",
      customName: null,
      doseAmount: 200,
      doseUnit: "mg",
      instructions: "После еды",
      doseWarning: null,
      safetyStatus: "ok",
      safetyWarnings: [],
      isActive: true,
      startDate: "2026-04-01",
      endDate: null,
      schedules: [
        { id: "sch-1", timeOfDay: "08:00:00", daysOfWeek: [1, 2, 3, 4, 5] },
      ],
    },
    {
      id: "med-2",
      tradeName: null,
      customName: "Омепразол",
      doseAmount: 20,
      doseUnit: "mg",
      instructions: "Утром до еды",
      doseWarning: null,
      safetyStatus: "ok",
      safetyWarnings: [],
      isActive: true,
      startDate: "2026-04-10",
      endDate: null,
      schedules: [
        { id: "sch-2", timeOfDay: "12:30:00", daysOfWeek: [1, 2, 3, 4, 5] },
      ],
    },
  ],
  conversations: [
    {
      id: "conv-1",
      title: "Новая консультация",
      createdAt: new Date().toISOString(),
    },
  ],
  messagesByConversation: {
    "conv-1": [
      {
        id: "msg-1",
        conversationId: "conv-1",
        role: "assistant",
        content:
          "Здравствуйте. Опишите ваши симптомы, и я помогу с общими рекомендациями.",
        createdAt: new Date().toISOString(),
      },
    ],
  },
};

function readJsonBody(options) {
  if (!options?.body) return {};
  try {
    return JSON.parse(options.body);
  } catch {
    return {};
  }
}

function uid(prefix) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

function parseIsoDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDateKey(date) {
  return date.toISOString().slice(0, 10);
}

function getIntakeStore() {
  try {
    const raw = localStorage.getItem("intakeStatusStore");
    if (!raw) return { dayStatus: {}, history: [] };
    const parsed = JSON.parse(raw);
    return {
      marks: parsed.marks || parsed.dayStatus || {},
      history: parsed.history || [],
    };
  } catch {
    return { marks: {}, history: [] };
  }
}

function getDateRange(from, to) {
  const start = parseIsoDate(from);
  const end = parseIsoDate(to);
  if (!start || !end) return [];

  const dates = [];
  const cursor = new Date(start);
  cursor.setHours(0, 0, 0, 0);
  end.setHours(0, 0, 0, 0);

  while (cursor <= end) {
    dates.push(new Date(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }

  return dates;
}

function matchesScheduleDay(date, daysOfWeek = []) {
  if (!daysOfWeek.length) return true;
  const jsDay = date.getDay() === 0 ? 7 : date.getDay();
  return daysOfWeek.includes(jsDay);
}

function parseMarkKey(key) {
  const [date, medId, scheduleId, timeOfDay] = String(key).split("::");
  return { date, medId, scheduleId, timeOfDay };
}

function buildMarkKey(dateKey, medId, scheduleId, timeOfDay) {
  return `${dateKey}::${medId}::${scheduleId || ""}::${String(timeOfDay || "00:00").slice(0, 5)}`;
}

function resolveMockStatus(
  store,
  medId,
  scheduleId,
  timeOfDay,
  date,
  scheduledAt,
  now,
) {
  const dateKey = formatDateKey(date);
  const exactKey = buildMarkKey(dateKey, medId, scheduleId, timeOfDay);
  const timeOnlyKey = buildMarkKey(dateKey, medId, "", timeOfDay);
  const historyEntry = (store.history || []).find(
    (item) =>
      item.date === dateKey &&
      item.medId === medId &&
      item.scheduleId === scheduleId,
  );

  const storedStatus =
    store.marks?.[exactKey] ||
    store.marks?.[timeOnlyKey] ||
    historyEntry?.status;
  if (storedStatus === "taken") return "taken";
  if (storedStatus === "missed" || storedStatus === "skipped") return "missed";

  return scheduledAt > now ? "waiting" : "missed";
}

function buildDashboardSummary(from, to) {
  const meds = mockState.medications;
  const store = getIntakeStore();
  const rangeDates = getDateRange(from, to);
  const start = parseIsoDate(from);
  const end = parseIsoDate(to);
  const now = new Date();

  const dailySeries = rangeDates.map((date) => {
    const dateKey = formatDateKey(date);
    let taken = 0;
    let waiting = 0;
    let missed = 0;
    let totalScheduled = 0;

    for (const med of meds) {
      for (const schedule of med.schedules || []) {
        if (!matchesScheduleDay(date, schedule.daysOfWeek || [])) {
          continue;
        }

        totalScheduled += 1;
        const scheduledAt = new Date(
          `${dateKey}T${schedule.timeOfDay || "00:00:00"}`,
        );
        const status = resolveMockStatus(
          store,
          med.id,
          schedule.id,
          schedule.timeOfDay,
          date,
          scheduledAt,
          now,
        );

        if (status === "taken") {
          taken += 1;
        } else if (status === "waiting") {
          waiting += 1;
        } else {
          missed += 1;
        }
      }
    }

    return { date: dateKey, taken, waiting, missed, totalScheduled };
  });

  return {
    period: { from, to },
    dailySeries,
    adherence: meds.map((med) => {
      const scheduledOccurrences = [];
      for (const date of rangeDates) {
        for (const schedule of med.schedules || []) {
          if (matchesScheduleDay(date, schedule.daysOfWeek || [])) {
            scheduledOccurrences.push({
              date: formatDateKey(date),
              scheduleId: schedule.id,
              timeOfDay: schedule.timeOfDay || "00:00:00",
            });
          }
        }
      }

      const medHistory = store.history.filter((item) => {
        if (item.medId !== med.id) return false;
        const itemDate = parseIsoDate(item.date);
        if (!itemDate || !start || !end) return false;
        itemDate.setHours(0, 0, 0, 0);
        start.setHours(0, 0, 0, 0);
        end.setHours(0, 0, 0, 0);
        return itemDate >= start && itemDate <= end;
      });

      const markHistory = Object.entries(store.marks || {})
        .map(([key, status]) => ({ ...parseMarkKey(key), status }))
        .filter((item) => {
          if (item.medId !== med.id) return false;
          const itemDate = parseIsoDate(item.date);
          if (!itemDate || !start || !end) return false;
          itemDate.setHours(0, 0, 0, 0);
          start.setHours(0, 0, 0, 0);
          end.setHours(0, 0, 0, 0);
          return itemDate >= start && itemDate <= end;
        });

      const totalScheduled = scheduledOccurrences.length;
      const totalTaken =
        medHistory.filter((item) => item.status === "taken").length +
        markHistory.filter((item) => item.status === "taken").length;
      const missedDates = [
        ...medHistory
          .filter(
            (item) => item.status === "missed" || item.status === "skipped",
          )
          .map(
            (item) =>
              `${item.date}${item.timeOfDay ? ` ${String(item.timeOfDay).slice(0, 5)}` : ""}`,
          ),
        ...markHistory
          .filter(
            (item) => item.status === "missed" || item.status === "skipped",
          )
          .map(
            (item) =>
              `${item.date}${item.timeOfDay ? ` ${String(item.timeOfDay).slice(0, 5)}` : ""}`,
          ),
      ];

      return {
        medicationId: med.id,
        tradeName: med.tradeName || med.customName || "Medication",
        totalScheduled,
        totalTaken,
        adherencePercent:
          totalScheduled > 0
            ? Number(((totalTaken / totalScheduled) * 100).toFixed(2))
            : 0,
        missedDates,
      };
    }),
  };
}

function toDashboardSummary() {
  const active = mockState.medications.filter((item) => item.isActive);
  const adherence = active.map((item) => ({
    medicationId: item.id,
    tradeName: item.tradeName || item.customName || "Medication",
    totalScheduled: 7,
    totalTaken: 6,
    adherencePercent: 85.71,
    missedDates: ["2026-04-03"],
  }));
  return {
    period: {
      from: "2026-04-01",
      to: "2026-04-07",
    },
    adherence,
    insights: [
      `Overall adherence: ${adherence.length > 0 ? "85.71" : "0.00"}%`,
    ],
  };
}

async function mockRequest(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const body = readJsonBody(options);
  const now = new Date().toISOString();

  if (path === "/api/health" && method === "GET") {
    return { status: "UP", service: "healthmate-backend", timestamp: now };
  }

  if (path === "/api/auth/me" && method === "GET") {
    return mockState.user;
  }

  if (path === "/api/auth/login" && method === "POST") {
    return mockState.user;
  }

  if (path === "/api/auth/logout" && method === "POST") {
    return { message: "Logged out successfully" };
  }

  if (path === "/api/auth/register" && method === "POST") {
    const newUser = {
      id: uid("user"),
      email: body.email,
      firstName: body.firstName,
      lastName: body.lastName,
      birthDate: body.birthDate,
    };
    mockState.user = newUser;
    // Set optional profile data if provided
    if (body.heightCm || body.weightKg || body.bloodType) {
      mockState.profile = {
        ...mockState.profile,
        heightCm: body.heightCm || mockState.profile.heightCm,
        weightKg: body.weightKg || mockState.profile.weightKg,
        bloodType: body.bloodType || mockState.profile.bloodType,
        diagnoses: body.diagnoses || mockState.profile.diagnoses,
        allergies: body.allergies || mockState.profile.allergies,
        updatedAt: now,
      };
    }
    return newUser;
  }

  if (path === "/api/profile" && method === "GET") {
    return mockState.profile;
  }

  if (path === "/api/profile" && method === "PUT") {
    mockState.profile = {
      ...mockState.profile,
      ...body,
      updatedAt: now,
    };
    return { updatedAt: mockState.profile.updatedAt };
  }

  if (path.startsWith("/api/medications?page=") && method === "GET") {
    const active = mockState.medications.filter((item) => item.isActive);
    const inactive = mockState.medications.filter((item) => !item.isActive);
    return {
      active,
      inactive,
      page: 0,
      size: 20,
      total: mockState.medications.length,
    };
  }

  if (path === "/api/medications/validate" && method === "POST") {
    const warnings = [];
    if ((body.customName || "").toLowerCase().includes("ибупрофен")) {
      warnings.push(
        "Проверьте совместимость с гастропротекцией при длительном приеме.",
      );
    }
    return {
      status: warnings.length > 0 ? "warning" : "ok",
      warnings,
      blockers: [],
      metadata: {},
    };
  }

  if (path === "/api/medications" && method === "POST") {
    const created = {
      id: uid("med"),
      tradeName: null,
      customName: body.customName || "Новое лекарство",
      doseAmount: body.doseAmount || 0,
      doseUnit: body.doseUnit || "mg",
      instructions: body.instructions || "",
      doseWarning: null,
      safetyStatus: "ok",
      safetyWarnings: [],
      isActive: true,
      startDate: body.startDate || "2026-04-01",
      endDate: body.endDate || null,
      schedules: (body.schedules || []).map((schedule) => ({
        id: uid("sch"),
        ...schedule,
      })),
    };
    mockState.medications.unshift(created);
    return created;
  }

  if (path.startsWith("/api/medications/") && method === "DELETE") {
    const id = path.split("/").at(-1);
    const target = mockState.medications.find((item) => item.id === id);
    if (target) {
      target.isActive = false;
      return { id: target.id, isActive: false };
    }
    throw new Error("Medication not found");
  }

  if (path.endsWith("/active") && method === "PUT") {
    const id = path.split("/")[3];
    const target = mockState.medications.find((item) => item.id === id);
    if (target) {
      target.isActive = Boolean(body.isActive);
      return { id: target.id, isActive: target.isActive };
    }
    throw new Error("Medication not found");
  }

  if (path.startsWith("/api/conversations?page=") && method === "GET") {
    return {
      content: mockState.conversations,
      totalElements: mockState.conversations.length,
      number: 0,
      size: 20,
    };
  }

  if (path === "/api/conversations" && method === "POST") {
    const created = {
      id: uid("conv"),
      title: body.title || "Новая консультация",
      createdAt: now,
    };
    mockState.conversations.unshift(created);
    mockState.messagesByConversation[created.id] = [];
    return created;
  }

  if (path.includes("/messages") && method === "GET") {
    const conversationId = path.split("/")[3];
    return mockState.messagesByConversation[conversationId] || [];
  }

  if (path.includes("/messages") && method === "POST") {
    const conversationId = path.split("/")[3];
    const userMessage = {
      id: uid("msg"),
      conversationId,
      role: "user",
      content: body.content || "",
      createdAt: now,
    };
    const assistantMessage = {
      id: uid("msg"),
      conversationId,
      role: "assistant",
      content:
        "Тестовая заглушка AI: похоже на легкие симптомы. При ухудшении обратитесь к врачу.",
      createdAt: now,
    };
    const list = mockState.messagesByConversation[conversationId] || [];
    list.push(userMessage, assistantMessage);
    mockState.messagesByConversation[conversationId] = list;
    return {
      userMessage,
      assistantMessage,
      messageType: "question",
      disclaimer: "Это тестовые данные для просмотра интерфейса.",
      recommendedDrugs: [],
    };
  }

  if (path.startsWith("/api/dashboard/summary") && method === "GET") {
    const query = new URL(`http://localhost${path}`).searchParams;
    const from = query.get("from");
    const to = query.get("to");
    return buildDashboardSummary(from, to);
  }

  // Поиск лекарств
  if (path.startsWith("/api/drugs/search") && method === "GET") {
    const q = new URL(`http://localhost${path}`).searchParams.get("q");
    const drugs = [
      {
        id: "d1",
        tradeName: "Ибупрофен",
        internationalName: "Ibuprofen",
        atxCode: "M01AE01",
        doseUnit: "мг",
        minDose: 200,
        maxDose: 1200,
        isInRag: false,
        hasMedia: false,
      },
      {
        id: "d2",
        tradeName: "Омепразол",
        internationalName: "Omeprazole",
        atxCode: "A02BC01",
        doseUnit: "мг",
        minDose: 20,
        maxDose: 40,
        isInRag: false,
        hasMedia: false,
      },
      {
        id: "d3",
        tradeName: "Амоксициллин",
        internationalName: "Amoxicillin",
        atxCode: "J01CA04",
        doseUnit: "мг",
        minDose: 250,
        maxDose: 1000,
        isInRag: false,
        hasMedia: false,
      },
    ];
    if (!q) return { results: drugs };
    const results = drugs.filter(
      (d) =>
        d.tradeName.toLowerCase().includes(q.toLowerCase()) ||
        d.internationalName.toLowerCase().includes(q.toLowerCase()),
    );
    return { results };
  }

  // Расписания лекарства
  if (path.endsWith("/schedules") && method === "GET") {
    const medId = path.split("/")[3];
    const med = mockState.medications.find((m) => m.id === medId);
    return med?.schedules || [];
  }

  if (path.endsWith("/schedules") && method === "POST") {
    const medId = path.split("/")[3];
    const med = mockState.medications.find((m) => m.id === medId);
    if (med) {
      const schedule = { id: uid("sch"), ...body };
      med.schedules.push(schedule);
      return schedule;
    }
    throw new Error("Medication not found");
  }

  if (path.startsWith("/api/medications/schedules/") && method === "DELETE") {
    const scheduleId = path.split("/").at(-1);
    for (const med of mockState.medications) {
      const idx = med.schedules.findIndex((s) => s.id === scheduleId);
      if (idx >= 0) {
        med.schedules.splice(idx, 1);
        return { id: scheduleId, deleted: true };
      }
    }
    throw new Error("Schedule not found");
  }

  // Логи приема
  if (path.includes("/intake-logs") && method === "GET") {
    const logs = [
      {
        id: "log1",
        scheduledAt: "2026-04-01T08:00:00Z",
        takenAt: "2026-04-01T08:15:00Z",
        status: "taken",
        confirmedVia: "app",
      },
      {
        id: "log2",
        scheduledAt: "2026-04-02T08:00:00Z",
        takenAt: null,
        status: "missed",
        confirmedVia: "app",
      },
      {
        id: "log3",
        scheduledAt: "2026-04-03T08:00:00Z",
        takenAt: "2026-04-03T08:30:00Z",
        status: "taken",
        confirmedVia: "app",
      },
    ];
    return { logs };
  }

  if (
    path.includes("/intake-logs/") &&
    path.endsWith("/take") &&
    method === "POST"
  ) {
    const logId = path.split("/").at(-2);
    return { id: logId, status: "taken" };
  }

  if (
    path.includes("/intake-logs/") &&
    path.endsWith("/status") &&
    method === "PATCH"
  ) {
    const logId = path.split("/").at(-2);
    return { id: logId, status: body.status };
  }

  throw new Error(`Mock route is not implemented: ${method} ${path}`);
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : null;

  if (response.ok) {
    return payload;
  }

  const error = new Error(payload?.message || "Request failed");
  error.status = response.status;
  error.code = payload?.error || "REQUEST_ERROR";
  error.fields = payload?.fields || null;
  throw error;
}

export async function httpRequest(path, options = {}) {
  if (USE_MOCK_API) {
    return mockRequest(path, options);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  return parseResponse(response);
}
