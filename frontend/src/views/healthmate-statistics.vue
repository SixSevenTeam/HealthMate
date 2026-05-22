<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { getDashboardSummary } from "@/entities/dashboard/api/dashboardApi";
import {
  getIntakeLogs,
  getMedications,
} from "@/entities/medications/api/medicationsApi";

const loading = ref(false);
const errorMessage = ref("");
const summary = ref(null);
const recoveredDailySeries = ref([]);
const viewMode = ref(
  recoveredDailySeries.value.length > 0 ? "daily" : "medication",
);
const medicationScope = ref("active");
const periodPreset = ref("7d");
const fromDate = ref("");
const toDate = ref("");

const scopeOptions = [
  { value: "active", label: "Активные" },
  { value: "inactive", label: "Неактивные" },
  { value: "all", label: "Все" },
];

const presetOptions = [
  { value: "7d", label: "7 дней" },
  { value: "30d", label: "30 дней" },
  { value: "90d", label: "3 месяца" },
  { value: "custom", label: "Произвольный период" },
];

function pad(value) {
  return String(value).padStart(2, "0");
}

function toDateInputValue(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function shiftDays(date, amount) {
  const result = new Date(date);
  result.setDate(result.getDate() + amount);
  return result;
}

function formatAxisLabel(dateValue) {
  if (!dateValue) return "";
  const [year, month, day] = String(dateValue).split("-");
  if (!year || !month || !day) return String(dateValue);
  return `${day}.${month}`;
}

function applyPreset(preset = periodPreset.value) {
  const today = new Date();
  const to = new Date(today);
  let from = new Date(today);

  if (preset === "7d") {
    from = shiftDays(today, -6);
  } else if (preset === "30d") {
    from = shiftDays(today, -29);
  } else if (preset === "90d") {
    from = new Date(today);
    from.setMonth(from.getMonth() - 3);
  }

  fromDate.value = toDateInputValue(from);
  toDate.value = toDateInputValue(to);
}

const adherence = computed(() => summary.value?.adherence || []);
const dailySeries = computed(() => {
  const primary =
    summary.value?.dailySeries ||
    summary.value?.daily_series ||
    summary.value?.daily;
  if (Array.isArray(primary) && primary.length > 0) {
    return primary;
  }
  return recoveredDailySeries.value;
});
const chartMode = computed(() => viewMode.value);

function parseDateInput(dateValue) {
  if (!dateValue) return null;
  const date = new Date(`${dateValue}T00:00:00`);
  if (Number.isNaN(date.getTime())) return null;
  date.setHours(0, 0, 0, 0);
  return date;
}

function toDateKeyLocal(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function normalizeStatus(log) {
  const raw = String(log?.status || "")
    .trim()
    .toLowerCase();
  if (raw === "taken") return "taken";
  if (raw === "missed" || raw === "skipped") return "missed";
  if (raw === "pending") {
    const scheduledAt = log?.scheduledAt ? new Date(log.scheduledAt) : null;
    if (
      scheduledAt &&
      !Number.isNaN(scheduledAt.getTime()) &&
      scheduledAt > new Date()
    ) {
      return "waiting";
    }
    return "missed";
  }

  const scheduledAt = log?.scheduledAt ? new Date(log.scheduledAt) : null;
  if (
    scheduledAt &&
    !Number.isNaN(scheduledAt.getTime()) &&
    scheduledAt > new Date()
  ) {
    return "waiting";
  }
  return "missed";
}

function uniqueById(items = []) {
  const seen = new Set();
  return (items || []).filter((item) => {
    if (!item?.id || seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

function getScopedMedications(medsResponse, scope) {
  const active = uniqueById(medsResponse?.active || []);
  const inactive = uniqueById(medsResponse?.inactive || []);

  if (scope === "inactive") {
    return inactive;
  }
  if (scope === "all") {
    return [...active, ...inactive];
  }
  return active;
}

async function rebuildDailySeriesFromLogs(
  from,
  to,
  scope = medicationScope.value,
) {
  const fromParsed = parseDateInput(from);
  const toParsed = parseDateInput(to);
  if (!fromParsed || !toParsed || fromParsed > toParsed) {
    return [];
  }

  const byDate = new Map();
  for (
    let cursor = new Date(fromParsed);
    cursor <= toParsed;
    cursor.setDate(cursor.getDate() + 1)
  ) {
    const key = toDateKeyLocal(cursor);
    byDate.set(key, {
      date: key,
      taken: 0,
      waiting: 0,
      missed: 0,
      totalScheduled: 0,
    });
  }

  const medsResponse = await getMedications(0, 200);
  const allMeds = getScopedMedications(medsResponse, scope);
  if (allMeds.length === 0) {
    return Array.from(byDate.values());
  }

  const logsResponses = await Promise.all(
    allMeds.map(async (med) => {
      try {
        const payload = await getIntakeLogs(med.id, from, to);
        return payload?.logs || payload || [];
      } catch {
        return [];
      }
    }),
  );

  for (let i = 0; i < logsResponses.length; i++) {
    const med = allMeds[i];
    const logs = logsResponses[i] || [];
    for (const log of logs) {
      if (!log?.scheduledAt) continue;
      const scheduledAt = new Date(log.scheduledAt);
      if (Number.isNaN(scheduledAt.getTime())) continue;

      const dayKey = toDateKeyLocal(scheduledAt);
      const bucket = byDate.get(dayKey);
      if (!bucket) continue;

      const status = normalizeStatus(log);

      // If medication inactive, do not count future expected (waiting) items
      if (!med?.isActive && status === "waiting") {
        continue;
      }

      bucket.totalScheduled += 1;
      if (status === "taken") {
        bucket.taken += 1;
      } else if (status === "waiting") {
        bucket.waiting += 1;
      } else {
        bucket.missed += 1;
      }
    }
  }

  return Array.from(byDate.values());
}

const totals = computed(() =>
  dailySeries.value.length > 0
    ? dailySeries.value.reduce(
        (acc, day) => {
          acc.taken += day.taken || 0;
          acc.waiting += day.waiting || 0;
          acc.missed += day.missed || 0;
          acc.totalScheduled += day.totalScheduled || 0;
          return acc;
        },
        { taken: 0, waiting: 0, missed: 0, totalScheduled: 0 },
      )
    : adherence.value.reduce(
        (acc, item) => {
          const missed = Array.isArray(item.missedDates)
            ? item.missedDates.length
            : 0;
          const taken = item.totalTaken || 0;
          const totalScheduled = item.totalScheduled || 0;

          acc.taken += taken;
          acc.missed += missed;
          acc.waiting += Math.max(totalScheduled - taken - missed, 0);
          acc.totalScheduled += totalScheduled;
          return acc;
        },
        { taken: 0, waiting: 0, missed: 0, totalScheduled: 0 },
      ),
);

const overallAdherence = computed(() => {
  if (totals.value.totalScheduled === 0) return "0.00";
  return ((totals.value.taken / totals.value.totalScheduled) * 100).toFixed(2);
});

const adherenceColor = computed(() => {
  const avg = parseFloat(overallAdherence.value);
  if (avg >= 80) return "#27ae60";
  if (avg >= 60) return "#f39c12";
  return "#e74c3c";
});

const trackedMedications = computed(() => adherence.value.length);
const healthyAdherenceCount = computed(
  () => adherence.value.filter((item) => item.adherencePercent >= 80).length,
);
const attentionNeededCount = computed(
  () => adherence.value.filter((item) => item.adherencePercent < 60).length,
);

const chartMax = computed(() => {
  const source =
    chartMode.value === "daily" ? dailySeries.value : adherence.value;
  const maxValue = Math.max(
    ...source.map((item) => item.totalScheduled || 0),
    0,
  );
  return Math.max(maxValue, 1);
});

const chartBars = computed(() =>
  (chartMode.value === "daily" ? dailySeries.value : adherence.value).map(
    (item) => {
      const isDaily = chartMode.value === "daily";
      const taken = isDaily ? item.taken || 0 : item.totalTaken || 0;
      const missed = isDaily
        ? item.missed || 0
        : Array.isArray(item.missedDates)
          ? item.missedDates.length
          : 0;
      const totalScheduled = item.totalScheduled || 0;
      const waiting = Math.max(totalScheduled - taken - missed, 0);
      const segments = [
        {
          key: "missed",
          label: "Пропущено",
          value: missed,
          color: "#e74c3c",
        },
        {
          key: "waiting",
          label: "Ожидание",
          value: waiting,
          color: "#f39c12",
        },
        {
          key: "taken",
          label: "Принято",
          value: taken,
          color: "#27ae60",
        },
      ];

      let bottom = 0;
      return {
        ...item,
        label: isDaily
          ? formatAxisLabel(item.date)
          : item.tradeName || item.medicationId || "Лекарство",
        subtitle: isDaily ? item.date : `${taken} из ${totalScheduled}`,
        segments: segments.map((segment) => {
          const height = (segment.value / chartMax.value) * 100;
          const entry = { ...segment, height, bottom };
          bottom += height;
          return entry;
        }),
      };
    },
  ),
);

function loadStatistics() {
  if (!fromDate.value || !toDate.value) {
    applyPreset("7d");
  }

  loading.value = true;
  errorMessage.value = "";
  recoveredDailySeries.value = [];

  return getDashboardSummary(
    fromDate.value,
    toDate.value,
    medicationScope.value,
  )
    .then(async (data) => {
      summary.value = data;

      const apiSeries =
        data?.dailySeries || data?.daily_series || data?.daily || [];
      if (!Array.isArray(apiSeries) || apiSeries.length === 0) {
        recoveredDailySeries.value = await rebuildDailySeriesFromLogs(
          fromDate.value,
          toDate.value,
          medicationScope.value,
        );
      }
    })
    .catch((error) => {
      errorMessage.value = error.message || "Не удалось загрузить статистику";
    })
    .finally(() => {
      loading.value = false;
    });
}

function handlePresetChange() {
  if (periodPreset.value === "custom") {
    return;
  }

  applyPreset(periodPreset.value);
  loadStatistics();
}

function applyCustomPeriod() {
  periodPreset.value = "custom";
  if (!fromDate.value || !toDate.value) {
    applyPreset("7d");
    periodPreset.value = "custom";
  }
  loadStatistics();
}

function handleScopeChange() {
  loadStatistics();
}

function refreshIfVisible() {
  if (document.visibilityState !== "visible") return;
  if (loading.value) return;
  if (!fromDate.value || !toDate.value) return;
  loadStatistics();
}

function onIntakeMarked() {
  if (loading.value) return;
  if (!fromDate.value || !toDate.value) return;
  loadStatistics();
}

onMounted(() => {
  applyPreset("7d");
  loadStatistics();
  window.addEventListener("focus", refreshIfVisible);
  document.addEventListener("visibilitychange", refreshIfVisible);
  window.addEventListener("storage", () => {
    const lastMarked = localStorage.getItem("healthmate.intakeMarked");
    if (lastMarked) {
      onIntakeMarked();
    }
  });
});

onUnmounted(() => {
  window.removeEventListener("focus", refreshIfVisible);
  document.removeEventListener("visibilitychange", refreshIfVisible);
});
</script>

<template>
  <section class="stack">
    <article class="card">
      <h2 class="card-title">Фильтр периода</h2>
      <div class="period-toolbar">
        <div>
          <label class="small">Быстрый выбор</label>
          <select
            v-model="periodPreset"
            class="input"
            @change="handlePresetChange"
          >
            <option
              v-for="option in presetOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </div>

        <div class="form-grid" style="grid-template-columns: 1fr 1fr">
          <div>
            <label class="small">От</label>
            <input v-model="fromDate" class="input" type="date" />
          </div>
          <div>
            <label class="small">До</label>
            <input v-model="toDate" class="input" type="date" />
          </div>
        </div>

        <button
          class="btn"
          type="button"
          @click="applyCustomPeriod"
          style="align-self: flex-end"
        >
          Показать период
        </button>
      </div>
    </article>

    <article class="card">
      <h2 class="card-title">Фильтр лекарств</h2>
      <div class="scope-toolbar">
        <button
          v-for="option in scopeOptions"
          :key="option.value"
          class="btn"
          :class="{ active: medicationScope === option.value }"
          type="button"
          @click="
            medicationScope = option.value;
            handleScopeChange();
          "
        >
          {{ option.label }}
        </button>
      </div>
    </article>

    <article class="card">
      <div class="card-headline">
        <h2 class="card-title">Приёмы лекарств</h2>
        <span class="muted small">{{ fromDate }} → {{ toDate }}</span>
      </div>

      <p v-if="loading" class="muted">Загрузка...</p>
      <p v-else-if="errorMessage" class="error-text">❌ {{ errorMessage }}</p>

      <div v-else class="chart-shell">
        <div class="chart-summary-grid">
          <div class="kpi-item main">
            <div class="kpi-value" :style="{ color: adherenceColor }">
              {{ overallAdherence }}%
            </div>
            <div class="kpi-label">Общая приверженность</div>
            <div class="kpi-meta">
              {{ totals.taken }} принято из
              {{ totals.totalScheduled }} назначений
            </div>
          </div>

          <div class="kpi-grid">
            <div class="kpi-box">
              <div class="kpi-number">{{ totals.taken }}</div>
              <div class="kpi-text">Принято</div>
            </div>
            <div class="kpi-box">
              <div class="kpi-number">{{ totals.waiting }}</div>
              <div class="kpi-text">Ожидание</div>
            </div>
            <div class="kpi-box">
              <div class="kpi-number">{{ totals.missed }}</div>
              <div class="kpi-text">Пропущено</div>
            </div>
            <div class="kpi-box compact">
              <div class="kpi-number">{{ trackedMedications }}</div>
              <div class="kpi-text">Лекарств в отчёте</div>
            </div>
          </div>
        </div>

        <div class="chart-card">
          <div
            style="
              display: flex;
              justify-content: space-between;
              align-items: center;
              margin-bottom: 10px;
            "
          >
            <div class="chart-legend">
              <span class="legend-item"
                ><i class="legend-swatch taken"></i> Принято</span
              >
              <span class="legend-item"
                ><i class="legend-swatch waiting"></i> Ожидание</span
              >
              <span class="legend-item"
                ><i class="legend-swatch missed"></i> Пропущено</span
              >
            </div>

            <div style="display: flex; gap: 8px; align-items: center">
              <label class="small muted" style="margin-right: 8px">Вид</label>
              <button
                class="btn"
                :class="{ active: viewMode === 'daily' }"
                @click="viewMode = 'daily'"
              >
                Дни
              </button>
              <button
                class="btn"
                :class="{ active: viewMode === 'medication' }"
                @click="viewMode = 'medication'"
              >
                Лекарства
              </button>
            </div>
          </div>

          <div v-if="chartBars.length === 0" class="empty-state">
            <p class="muted">Нет данных для выбранного периода</p>
          </div>

          <div v-else class="chart-wrap">
            <div class="chart-area">
              <div class="chart-grid-lines"></div>
              <div
                v-for="bar in chartBars"
                :key="bar.date || bar.medicationId || bar.tradeName"
                class="chart-bar"
              >
                <div class="bar-total">{{ bar.totalScheduled }}</div>
                <div class="bar-stack">
                  <div
                    v-for="segment in bar.segments"
                    :key="segment.key"
                    class="bar-segment"
                    :style="{
                      height: segment.height + '%',
                      bottom: segment.bottom + '%',
                      backgroundColor: segment.color,
                    }"
                  ></div>
                </div>
                <div class="bar-label">{{ bar.label }}</div>
                <div class="bar-subtitle">{{ bar.subtitle }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </article>

    <article class="card">
      <h2 class="card-title">Приверженность по лекарствам</h2>
      <div v-if="adherence.length === 0" class="empty-state">
        <p class="muted">Нет данных о приверженности за выбранный период</p>
      </div>
      <div v-else class="medications-adherence">
        <div
          v-for="item in adherence"
          :key="item.medicationId"
          class="adherence-item"
        >
          <div class="adherence-header">
            <strong>{{ item.tradeName }}</strong>
            <span
              class="adherence-badge"
              :style="{
                backgroundColor:
                  item.adherencePercent >= 80
                    ? '#27ae60'
                    : item.adherencePercent >= 60
                      ? '#f39c12'
                      : '#e74c3c',
              }"
            >
              {{ item.adherencePercent.toFixed(1) }}%
            </span>
          </div>

          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{
                width: item.adherencePercent + '%',
                backgroundColor:
                  item.adherencePercent >= 80
                    ? '#27ae60'
                    : item.adherencePercent >= 60
                      ? '#f39c12'
                      : '#e74c3c',
              }"
            ></div>
          </div>

          <div class="adherence-stats">
            <span>✓ Принято: {{ item.totalTaken }}</span>
            <span>Назначено: {{ item.totalScheduled }}</span>
            <span v-if="item.missedDates && item.missedDates.length">
              ✗ Пропущено: {{ item.missedDates.join(", ") }}
            </span>
          </div>
        </div>
      </div>
    </article>

    <article class="card">
      <h2 class="card-title">Подсказки</h2>
      <ul v-if="summary?.insights?.length" class="list">
        <li
          v-for="insight in summary.insights"
          :key="insight"
          class="list-item"
        >
          {{ insight }}
        </li>
      </ul>
      <p v-else class="muted">Нет дополнительных подсказок</p>
    </article>
  </section>
</template>

<style scoped>
.period-toolbar {
  display: grid;
  grid-template-columns: 220px 1fr auto;
  gap: 14px;
  align-items: end;
}

.scope-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.card-headline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
}

.chart-shell {
  display: grid;
  gap: 20px;
}

.chart-summary-grid {
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 20px;
  align-items: start;
}

.chart-card {
  padding: 18px;
  border: 1px solid #e4ebf7;
  border-radius: 16px;
  background: linear-gradient(180deg, #fbfcff 0%, #f5f8ff 100%);
}

.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 14px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #4b5970;
}

.legend-swatch {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  display: inline-block;
}

.legend-swatch.taken {
  background: #27ae60;
}

.legend-swatch.waiting {
  background: #f39c12;
}

.legend-swatch.missed {
  background: #e74c3c;
}

.chart-wrap {
  overflow-x: auto;
}

.chart-area {
  position: relative;
  min-height: 280px;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(18px, 1fr);
  gap: 8px;
  align-items: end;
  padding: 18px 10px 8px;
  background-image: linear-gradient(
    to top,
    rgba(148, 163, 184, 0.18) 1px,
    transparent 1px
  );
  background-size: 100% 25%;
  border-radius: 14px;
}

.chart-grid-lines {
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: 14px;
}

.chart-bar {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: end;
  min-width: 26px;
  height: 100%;
}

.bar-total {
  font-size: 11px;
  font-weight: 700;
  color: #41526a;
  margin-bottom: 6px;
  min-height: 16px;
}

.bar-stack {
  position: relative;
  width: 100%;
  height: 210px;
  border-radius: 12px 12px 0 0;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.5);
  box-shadow: inset 0 0 0 1px rgba(124, 146, 181, 0.14);
}

.bar-segment {
  position: absolute;
  left: 0;
  right: 0;
  border-radius: 8px 8px 0 0;
  opacity: 0.95;
}

.bar-label {
  margin-top: 8px;
  font-size: 11px;
  color: #5f6f87;
}

.bar-subtitle {
  margin-top: 3px;
  font-size: 10px;
  color: #8a97aa;
  text-align: center;
}

.kpi-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  align-items: start;
}

.kpi-item.main {
  grid-row: 1 / 3;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 30px;
  background: linear-gradient(
    145deg,
    rgba(26, 86, 219, 0.12) 0%,
    rgba(26, 86, 219, 0.04) 100%
  );
  border: 1px solid rgba(26, 86, 219, 0.22);
  border-radius: 12px;
}

.kpi-value {
  font-size: 48px;
  font-weight: 700;
  margin: 10px 0;
}

.kpi-label {
  font-size: 16px;
  font-weight: 500;
  color: #1e293b;
}

.kpi-meta {
  font-size: 13px;
  color: #4b638e;
  margin-top: 8px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.kpi-box {
  padding: 16px;
  background: #f7faff;
  border: 1px solid #d9e5ff;
  border-radius: 8px;
  text-align: center;
}

.kpi-box.compact {
  background: #edf3ff;
  border-color: #cfe0ff;
}

.kpi-number {
  font-size: 28px;
  font-weight: 700;
  color: #1a56db;
  margin-bottom: 4px;
}

.kpi-text {
  font-size: 13px;
  color: #5e6e86;
}

.medications-adherence {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.adherence-item {
  padding: 16px;
  background: #f7faff;
  border-radius: 8px;
  border-left: 4px solid #1a56db;
}

.adherence-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.adherence-badge {
  padding: 4px 12px;
  border-radius: 20px;
  color: white;
  font-weight: 600;
  font-size: 13px;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: #e0e0e0;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 12px;
}

.progress-fill {
  height: 100%;
  transition: width 0.3s ease;
}

.adherence-stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #666;
}

.empty-state {
  text-align: center;
  padding: 40px 20px;
}

@media (max-width: 768px) {
  .kpi-section {
    grid-template-columns: 1fr;
  }

  .kpi-item.main {
    grid-row: auto;
  }

  .adherence-stats {
    flex-direction: column;
  }
}
</style>
