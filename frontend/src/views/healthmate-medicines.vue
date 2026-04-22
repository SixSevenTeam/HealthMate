<script setup>
import { computed, onMounted, ref } from "vue";
import {
  createMedication,
  deactivateMedication,
  getMedications,
  setMedicationActive,
  validateMedication,
  getSchedules,
  addSchedule,
  deleteSchedule,
} from "@/entities/medications/api/medicationsApi";
import { searchDrugs } from "@/entities/drugs/api/drugsApi";

const meds = ref([]);
const page = ref(0);
const size = ref(20);
const total = ref(0);
const loading = ref(false);
const errorMessage = ref("");
const notice = ref("");
const searchQuery = ref("");
const searchResults = ref([]);
const showSearch = ref(false);

const form = ref({
  drugId: null,
  customName: "",
  doseAmount: 0,
  doseUnit: "mg",
  instructions: "",
  startDate: new Date().toISOString().slice(0, 10),
  endDate: null,
  schedules: [{ timeOfDay: "08:00:00", daysOfWeek: [1, 2, 3, 4, 5] }],
});

const expandedMedId = ref(null);
const medicationSchedules = ref({});

async function loadMedications() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const data = await getMedications(page.value, size.value);
    meds.value = [...(data.active || []), ...(data.inactive || [])];
    total.value = data.total || meds.value.length;
  } catch (error) {
    errorMessage.value = error.message || "Не удалось загрузить лекарства";
  } finally {
    loading.value = false;
  }
}

async function searchDrugCatalog() {
  if (!searchQuery.value.trim()) {
    searchResults.value = [];
    return;
  }
  try {
    const result = await searchDrugs(searchQuery.value);
    searchResults.value = result.results || [];
  } catch (error) {
    console.error("Ошибка поиска:", error);
    searchResults.value = [];
  }
}

function selectDrug(drug) {
  form.value.drugId = drug.id;
  form.value.customName = drug.tradeName;
  form.value.doseUnit = drug.doseUnit || "мг";
  showSearch.value = false;
  searchQuery.value = "";
  searchResults.value = [];
}

async function onCreate() {
  notice.value = "";
  errorMessage.value = "";
  try {
    const validation = await validateMedication({
      drugId: form.value.drugId,
      customName: form.value.customName,
      doseAmount: Number(form.value.doseAmount),
      doseUnit: form.value.doseUnit,
      instructions: form.value.instructions,
      startDate: form.value.startDate,
      endDate: form.value.endDate,
    });

    if ((validation?.warnings || []).length > 0) {
      notice.value = validation.warnings.join("; ");
    }

    await createMedication({
      drugId: form.value.drugId,
      customName: form.value.customName,
      doseAmount: Number(form.value.doseAmount),
      doseUnit: form.value.doseUnit,
      instructions: form.value.instructions,
      startDate: form.value.startDate,
      endDate: form.value.endDate,
      schedules: form.value.schedules,
    });

    form.value = {
      drugId: null,
      customName: "",
      doseAmount: 0,
      doseUnit: "mg",
      instructions: "",
      startDate: new Date().toISOString().slice(0, 10),
      endDate: null,
      schedules: [{ timeOfDay: "08:00:00", daysOfWeek: [1, 2, 3, 4, 5] }],
    };
    await loadMedications();
  } catch (error) {
    errorMessage.value = error.message || "Не удалось добавить лекарство";
  }
}

async function onToggle(item) {
  try {
    await setMedicationActive(item.id, !item.isActive);
    await loadMedications();
  } catch (error) {
    errorMessage.value = error.message || "Не удалось изменить статус";
  }
}

async function onDeactivate(item) {
  try {
    await deactivateMedication(item.id);
    await loadMedications();
  } catch (error) {
    errorMessage.value = error.message || "Не удалось деактивировать лекарство";
  }
}

async function toggleMedicationDetails(medId) {
  if (expandedMedId.value === medId) {
    expandedMedId.value = null;
    return;
  }
  expandedMedId.value = medId;
  if (!medicationSchedules.value[medId]) {
    try {
      const schedules = await getSchedules(medId);
      medicationSchedules.value[medId] = schedules;
    } catch (error) {
      console.error("Ошибка загрузки расписания:", error);
    }
  }
}

async function onAddSchedule(medId) {
  const timeStr = prompt("Введите время (HH:MM):", "08:00");
  if (!timeStr) return;
  try {
    const schedule = await addSchedule(medId, {
      timeOfDay: `${timeStr}:00`,
      daysOfWeek: [1, 2, 3, 4, 5],
    });
    if (!medicationSchedules.value[medId]) {
      medicationSchedules.value[medId] = [];
    }
    medicationSchedules.value[medId].push(schedule);
  } catch (error) {
    errorMessage.value = "Не удалось добавить расписание";
  }
}

async function onDeleteSchedule(medId, scheduleId) {
  try {
    await deleteSchedule(scheduleId);
    medicationSchedules.value[medId] = medicationSchedules.value[medId].filter(
      (s) => s.id !== scheduleId,
    );
  } catch (error) {
    errorMessage.value = "Не удалось удалить расписание";
  }
}

onMounted(loadMedications);
</script>

<template>
  <section class="stack">
    <article class="card">
      <h2 class="card-title">Добавить лекарство</h2>
      <div class="form-grid">
        <div class="search-box">
          <input
            v-model="searchQuery"
            class="input"
            placeholder="Поиск в справочнике..."
            @focus="showSearch = true"
            @input="searchDrugCatalog"
          />
          <button
            v-if="showSearch"
            class="btn small"
            @click="showSearch = false"
          >
            Закрыть
          </button>
        </div>
        <div
          v-if="showSearch && searchResults.length > 0"
          class="search-results"
        >
          <div
            v-for="drug in searchResults"
            :key="drug.id"
            class="search-item"
            @click="selectDrug(drug)"
          >
            <strong>{{ drug.tradeName }}</strong> ({{ drug.internationalName }})
            - {{ drug.minDose }}-{{ drug.maxDose }} {{ drug.doseUnit }}
          </div>
        </div>

        <input
          v-model="form.customName"
          class="input"
          placeholder="Название лекарства"
        />
        <input
          v-model.number="form.doseAmount"
          class="input"
          type="number"
          placeholder="Доза"
        />
        <input
          v-model="form.doseUnit"
          class="input"
          placeholder="Единица (мг, мл и т.д.)"
        />
        <input
          v-model="form.instructions"
          class="input"
          placeholder="Инструкция (например: после еды)"
        />
        <input v-model="form.startDate" class="input" type="date" />
        <input
          v-model="form.endDate"
          class="input"
          type="date"
          placeholder="Дата окончания (опционально)"
        />
        <button class="btn" type="button" @click="onCreate">
          Сохранить лекарство
        </button>
      </div>
      <p v-if="notice" class="small warning">⚠️ {{ notice }}</p>
    </article>

    <article class="card">
      <h2 class="card-title">Список лекарств ({{ total }})</h2>
      <p v-if="loading" class="muted">Загрузка...</p>
      <p v-else-if="errorMessage" class="error-text">❌ {{ errorMessage }}</p>
      <div v-else class="medications-list">
        <div v-for="item in meds" :key="item.id" class="med-item">
          <div class="med-header" @click="toggleMedicationDetails(item.id)">
            <div>
              <strong>{{ item.tradeName || item.customName }}</strong>
              <p class="small">
                {{ item.doseAmount }} {{ item.doseUnit }} -
                {{ item.instructions }}
              </p>
            </div>
            <div class="med-actions">
              <span class="badge" :class="item.isActive ? 'ok' : 'warn'">
                {{ item.isActive ? "✓ Активно" : "○ Неактивно" }}
              </span>
              <button
                class="text-btn"
                type="button"
                @click.stop="onToggle(item)"
              >
                {{ item.isActive ? "Отключить" : "Включить" }}
              </button>
              <button
                class="text-btn danger"
                type="button"
                @click.stop="onDeactivate(item)"
              >
                Удалить
              </button>
            </div>
          </div>

          <div v-if="expandedMedId === item.id" class="med-details">
            <div
              v-if="item.safetyWarnings && item.safetyWarnings.length > 0"
              class="warnings"
            >
              <p class="small"><strong>Предупреждения безопасности:</strong></p>
              <ul>
                <li
                  v-for="(warning, idx) in item.safetyWarnings"
                  :key="idx"
                  class="small"
                >
                  ⚠️ {{ warning }}
                </li>
              </ul>
            </div>
            <div class="schedules">
              <h4>Расписание приема</h4>
              <ul v-if="medicationSchedules[item.id]?.length">
                <li
                  v-for="sch in medicationSchedules[item.id]"
                  :key="sch.id"
                  class="small"
                >
                  <span
                    >{{ sch.timeOfDay }} - дни:
                    {{ sch.daysOfWeek.join(", ") }}</span
                  >
                  <button
                    class="text-btn"
                    @click="onDeleteSchedule(item.id, sch.id)"
                  >
                    Удалить
                  </button>
                </li>
              </ul>
              <p v-else class="small muted">Нет расписания</p>
              <button class="btn small" @click="onAddSchedule(item.id)">
                + Добавить время приема
              </button>
            </div>
          </div>
        </div>
      </div>
    </article>
  </section>
</template>

<style scoped>
.search-box {
  display: flex;
  gap: 8px;
  grid-column: 1 / -1;
}
.search-box input {
  flex: 1;
}
.search-results {
  grid-column: 1 / -1;
  background: #f5f5f5;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
}
.search-item {
  padding: 8px;
  border-bottom: 1px solid #e0e0e0;
  cursor: pointer;
}
.search-item:hover {
  background: #efefef;
}
.medications-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.med-item {
  border: 1px solid #ddd;
  border-radius: 4px;
  overflow: hidden;
}
.med-header {
  padding: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  background: #fafafa;
}
.med-header:hover {
  background: #f0f0f0;
}
.med-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.med-details {
  padding: 12px;
  background: #f9f9f9;
  border-top: 1px solid #ddd;
}
.warnings {
  background: #fff3cd;
  padding: 8px;
  border-radius: 4px;
  margin-bottom: 12px;
}
.warnings ul {
  margin: 0;
  padding-left: 20px;
}
.schedules h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
}
.schedules ul {
  list-style: none;
  padding: 0;
  margin: 0 0 12px 0;
}
.schedules li {
  display: flex;
  justify-content: space-between;
  padding: 6px;
  background: white;
  border-radius: 3px;
  margin-bottom: 4px;
}
</style>
