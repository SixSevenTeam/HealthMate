<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { getDashboardSummary } from "@/entities/dashboard/api/dashboardApi";

const loading = ref(false);
const errorMessage = ref("");
const summary = ref(null);
const fromDate = ref("");
const toDate = ref("");

function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

function initializeDates() {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - 6);

  toDate.value = formatDate(to);
  fromDate.value = formatDate(from);
}

const adherence = computed(() => summary.value?.adherence || []);
const averageAdherence = computed(() => {
  if (adherence.value.length === 0) return "0.00";
  const total = adherence.value.reduce(
    (acc, item) => acc + (item.adherencePercent || 0),
    0,
  );
  return (total / adherence.value.length).toFixed(2);
});

const adherenceColor = computed(() => {
  const avg = parseFloat(averageAdherence.value);
  if (avg >= 80) return "#27ae60"; // green
  if (avg >= 60) return "#f39c12"; // orange
  return "#e74c3c"; // red
});

async function loadStatistics() {
  if (!fromDate.value || !toDate.value) {
    initializeDates();
    return;
  }

  loading.value = true;
  errorMessage.value = "";

  try {
    summary.value = await getDashboardSummary(fromDate.value, toDate.value);
  } catch (error) {
    errorMessage.value = error.message || "Не удалось загрузить статистику";
  } finally {
    loading.value = false;
  }
}

watch([fromDate, toDate], () => {
  if (fromDate.value && toDate.value) {
    loadStatistics();
  }
});

const trackedMedications = computed(() => adherence.value.length);
const healthyAdherenceCount = computed(() =>
  adherence.value.filter((item) => item.adherencePercent >= 80).length,
);
const attentionNeededCount = computed(() =>
  adherence.value.filter((item) => item.adherencePercent < 60).length,
);

onMounted(() => {
  initializeDates();
  loadStatistics();
});
</script>

<template>
  <section class="stack">
    <article class="card">
      <h2 class="card-title">Фильтр периода</h2>
      <div class="form-grid" style="grid-template-columns: 1fr 1fr auto">
        <div>
          <label class="small">От</label>
          <input v-model="fromDate" class="input" type="date" />
        </div>
        <div>
          <label class="small">До</label>
          <input v-model="toDate" class="input" type="date" />
        </div>
        <button
          class="btn"
          @click="loadStatistics"
          style="align-self: flex-end"
        >
          Обновить
        </button>
      </div>
    </article>

    <article class="card">
      <h2 class="card-title">Сводка по приверженности</h2>
      <p v-if="loading" class="muted">Загрузка...</p>
      <p v-else-if="errorMessage" class="error-text">❌ {{ errorMessage }}</p>
      <div v-else class="kpi-section">
        <div class="kpi-item main">
          <div class="kpi-value" :style="{ color: adherenceColor }">
            {{ averageAdherence }}%
          </div>
          <div class="kpi-label">Средняя приверженность</div>
          <div class="kpi-meta">{{ trackedMedications }} лекарств отслежено</div>
        </div>

        <div class="kpi-grid">
          <div class="kpi-box">
            <div class="kpi-number">{{ trackedMedications }}</div>
            <div class="kpi-text">Активных лекарств</div>
          </div>
          <div class="kpi-box">
            <div class="kpi-number">{{ healthyAdherenceCount }}</div>
            <div class="kpi-text">Хорошая приверженность</div>
          </div>
          <div class="kpi-box">
            <div class="kpi-number">{{ attentionNeededCount }}</div>
            <div class="kpi-text">Требует внимания</div>
          </div>
          <div class="kpi-box compact">
            <div class="kpi-number">{{ fromDate }}</div>
            <div class="kpi-text">Начало периода</div>
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

  </section>
</template>

<style scoped>
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
  background: linear-gradient(145deg, rgba(26, 86, 219, 0.12) 0%, rgba(26, 86, 219, 0.04) 100%);
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
