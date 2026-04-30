<script setup>
import { computed, onMounted, ref } from "vue";
import Icon from "@/shared/components/Icon.vue";
import { API_BASE_URL } from "@/shared/api/config";
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
const HIDDEN_DELETED_KEY = "hiddenDeletedMedicationIds";
function loadHiddenDeleted() {
  try {
    const raw = localStorage.getItem(HIDDEN_DELETED_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    return new Set(Array.isArray(arr) ? arr : []);
  } catch (e) {
    return new Set();
  }
}

function saveHiddenDeleted(set) {
  try {
    localStorage.setItem(HIDDEN_DELETED_KEY, JSON.stringify(Array.from(set)));
  } catch (e) {
    // ignore
  }
}

const hiddenDeletedMedicationIds = loadHiddenDeleted();
const loading = ref(false);
const errorMessage = ref("");
const validationErrors = ref({});
const notice = ref("");
const searchQuery = ref("");
const searchResults = ref([]);
const showSearch = ref(false);

const form = ref({
  drugId: null,
  customName: "",
  doseAmount: 0,
  doseUnit: "mg",
  customDoseUnit: "",
  instructions: "",
  startDate: new Date().toISOString().slice(0, 10),
  endDate: null,
  schedules: [{ timeOfDay: "08:00:00", daysOfWeek: [1, 2, 3, 4, 5] }],
});

const expandedMedId = ref(null);
const medicationSchedules = ref({});
const showScheduleModal = ref(false);
const selectedMedForSchedule = ref(null);
const scheduleError = ref("");
const scheduleForm = ref({
  timeOfDay: "",
  daysOfWeek: [],
});

const dayNames = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const doseUnitOptions = [
  { value: "mg", label: "мг" },
  { value: "pcs", label: "шт" },
  { value: "ml", label: "мл" },
  { value: "tab", label: "таб" },
  { value: "drops", label: "капли" },
  { value: "other", label: "другое..." },
];

function getDoseLabel(unit) {
  if (!unit) return "";
  const found = doseUnitOptions.find((o) => o.value === unit);
  if (found) return found.label;
  // If unit matches a known label (user-entered custom in Cyrillic), return as-is
  const byLabel = doseUnitOptions.find((o) => o.label === unit);
  if (byLabel) return byLabel.label;
  return unit;
}

function translateScheduleError(error) {
  const fieldMessages = error?.fields ? Object.values(error.fields).filter(Boolean) : [];
  if (fieldMessages.length > 0) {
    return fieldMessages
      .map((message) => {
        if (message.includes("must not be empty")) return "Заполните это поле";
        if (message.includes("must not be null")) return "Заполните это поле";
        if (message.includes("must be greater than or equal to")) return "Выберите корректное значение";
        return message;
      })
      .join("; ");
  }

  const message = (error?.message || "").toLowerCase();
  if (message.includes("validation failed")) {
    return "Проверьте время и дни недели";
  }
  if (message.includes("medication not found")) {
    return "Лекарство не найдено";
  }
  if (message.includes("schedule not found")) {
    return "Расписание не найдено";
  }
  return "Не удалось добавить расписание. Проверьте данные и попробуйте снова.";
}

function validateForm() {
  validationErrors.value = {};
  
  if (!form.value.customName?.trim()) {
    validationErrors.value.customName = "Введите название лекарства";
  }
  if (form.value.doseAmount <= 0) {
    validationErrors.value.doseAmount = "Доза должна быть больше 0";
  }
  if (!form.value.doseUnit?.trim()) {
    validationErrors.value.doseUnit = "Выберите единицу измерения";
  }
  if (form.value.doseUnit === "other" && !form.value.customDoseUnit?.trim()) {
    validationErrors.value.doseUnit = "Введите свою единицу измерения";
  }
  if (!form.value.startDate) {
    validationErrors.value.startDate = "Выберите дату начала";
  }
  
  return Object.keys(validationErrors.value).length === 0;
}

async function loadMedications() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const data = await getMedications(page.value, size.value);
    const active = data.active || [];
    const inactive = data.inactive || [];
    meds.value = [...active, ...inactive].filter(
      (medication) => !hiddenDeletedMedicationIds.has(medication.id),
    );
    total.value = meds.value.length;
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
  
  if (!validateForm()) {
    return;
  }
  
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

    const filteredWarnings = (validation?.warnings || []).filter(
      (warning) => !warning.toLowerCase().includes("safety validation is temporarily unavailable"),
    );

    if (filteredWarnings.length > 0) {
      notice.value = filteredWarnings.join("; ");
    }

    await createMedication({
      drugId: form.value.drugId,
      customName: form.value.customName,
      doseAmount: Number(form.value.doseAmount),
      doseUnit:
        form.value.doseUnit === "other"
          ? form.value.customDoseUnit.trim()
          : form.value.doseUnit,
      instructions: form.value.instructions,
      startDate: form.value.startDate,
      endDate: form.value.endDate,
      schedules: form.value.schedules.map((schedule) => ({
        timeOfDay: schedule.timeOfDay,
        daysOfWeek: schedule.daysOfWeek,
      })),
    });

    form.value = {
      drugId: null,
      customName: "",
      doseAmount: 0,
      doseUnit: "mg",
      customDoseUnit: "",
      instructions: "",
      startDate: new Date().toISOString().slice(0, 10),
      endDate: null,
      schedules: [{ timeOfDay: "08:00:00", daysOfWeek: [1, 2, 3, 4, 5] }],
    };
    validationErrors.value = {};
    await loadMedications();
  } catch (error) {
    errorMessage.value = error.message || "Не удалось добавить лекарство";
  }
}

async function onToggle(item) {
  try {
    const nextState = !item.isActive;
    await setMedicationActive(item.id, nextState);
    item.isActive = nextState;
  } catch (error) {
    errorMessage.value = error.message || "Не удалось изменить статус";
  }
}

async function onDeactivate(item) {
  try {
    await deactivateMedication(item.id);
    // mark as deleted by user and persist so it doesn't reappear after reload
    hiddenDeletedMedicationIds.add(item.id);
    saveHiddenDeleted(hiddenDeletedMedicationIds);
    meds.value = meds.value.filter((medication) => medication.id !== item.id);
    total.value = meds.value.length;
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

function openScheduleModal(medId) {
  selectedMedForSchedule.value = medId;
  showScheduleModal.value = true;
  scheduleError.value = "";
  scheduleForm.value = {
    timeOfDay: "",
    daysOfWeek: [],
  };
}

function closeScheduleModal() {
  showScheduleModal.value = false;
  selectedMedForSchedule.value = null;
  scheduleError.value = "";
}

function toggleDay(day) {
  const idx = scheduleForm.value.daysOfWeek.indexOf(day);
  if (idx >= 0) {
    scheduleForm.value.daysOfWeek.splice(idx, 1);
  } else {
    scheduleForm.value.daysOfWeek.push(day);
    scheduleForm.value.daysOfWeek.sort((a, b) => a - b);
  }
}

async function onAddSchedule() {
  const medId = selectedMedForSchedule.value;
  if (!medId) return;

  scheduleError.value = "";
  if (!scheduleForm.value.timeOfDay) {
    scheduleError.value = "Выберите время приема";
    return;
  }
  if (!scheduleForm.value.daysOfWeek.length) {
    scheduleError.value = "Выберите хотя бы один день недели";
    return;
  }

  try {
    const timeOfDay = scheduleForm.value.timeOfDay.includes(":")
      ? `${scheduleForm.value.timeOfDay.length === 5 ? `${scheduleForm.value.timeOfDay}:00` : scheduleForm.value.timeOfDay}`
      : scheduleForm.value.timeOfDay;

    const schedule = await addSchedule(medId, {
      timeOfDay,
      daysOfWeek: scheduleForm.value.daysOfWeek,
    });
    if (!medicationSchedules.value[medId]) {
      medicationSchedules.value[medId] = [];
    }
    medicationSchedules.value[medId].push(schedule);
    closeScheduleModal();
  } catch (error) {
    scheduleError.value = translateScheduleError(error);
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

async function openDrugDetails(item) {
  try {
    let id = item.drugId || null;
    if (!id) {
      const q = (item.tradeName || item.customName || "").trim();
      if (!q) return;
      const result = await searchDrugs(q);
      const first = result?.results?.[0];
      if (!first) return;
      id = first.id;
    }
    if (!id) return;
    const url = `${API_BASE_URL}/api/drugs/${id}/details`;
    window.open(url, "_blank");
  } catch (err) {
    console.error("openDrugDetails error:", err);
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

        <div class="form-field">
          <label class="form-label">Название лекарства *</label>
          <input
            v-model="form.customName"
            class="input"
            :class="{ 'input-error': validationErrors.customName }"
            placeholder="Введите или выберите из справочника"
          />
          <p v-if="validationErrors.customName" class="error-text">
            {{ validationErrors.customName }}
          </p>
        </div>

        <div class="form-field">
          <label class="form-label">Доза *</label>
          <input
            v-model.number="form.doseAmount"
            class="input"
            :class="{ 'input-error': validationErrors.doseAmount }"
            type="number"
            placeholder="0"
          />
          <p v-if="validationErrors.doseAmount" class="error-text">
            {{ validationErrors.doseAmount }}
          </p>
        </div>

        <div class="form-field">
          <label class="form-label">Единица измерения *</label>
          <select
            v-model="form.doseUnit"
            class="input"
            :class="{ 'input-error': validationErrors.doseUnit }"
          >
            <option v-for="opt in doseUnitOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
          <input
            v-if="form.doseUnit === 'other'"
            v-model="form.customDoseUnit"
            class="input"
            placeholder="Введите свою единицу (например: капс.)"
            style="margin-top:8px;"
          />
          <p v-if="validationErrors.doseUnit" class="error-text">
            {{ validationErrors.doseUnit }}
          </p>
        </div>

        <div class="form-field">
          <label class="form-label">Инструкция</label>
          <input
            v-model="form.instructions"
            class="input"
            placeholder="например: после еды"
          />
        </div>

        <div class="form-field">
          <label class="form-label">Дата начала приема *</label>
          <input
            v-model="form.startDate"
            class="input"
            :class="{ 'input-error': validationErrors.startDate }"
            type="date"
          />
          <p v-if="validationErrors.startDate" class="error-text">
            {{ validationErrors.startDate }}
          </p>
        </div>

        <div class="form-field">
          <label class="form-label">Дата окончания (опционально)</label>
          <input
            v-model="form.endDate"
            class="input"
            type="date"
          />
        </div>

        <button class="btn" type="button" @click="onCreate" style="grid-column: 1 / -1;">
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
              <Icon
                name="profileHelp"
                :size="18"
                className="med-help-icon"
                @click.stop="openDrugDetails(item)"
                title="Открыть карточку препарата"
              />
              <p class="small">
                {{ item.doseAmount }} {{ getDoseLabel(item.doseUnit) }} -
                {{ item.instructions }}
              </p>
            </div>
            <div class="med-actions">
              <button
                class="icon-action-btn"
                type="button"
                :title="item.isActive ? 'Активно (нажмите, чтобы приостановить)' : 'Приостановлено (нажмите, чтобы включить)'"
                :aria-label="item.isActive ? 'Приостановить препарат' : 'Включить препарат'"
                @click.stop="onToggle(item)"
              >
                <Icon
                  :name="item.isActive ? 'medStateActive' : 'medStatePaused'"
                  :size="22"
                  className="med-state-icon"
                />
              </button>
              <button
                class="icon-action-btn"
                type="button"
                title="Удалить из списка"
                aria-label="Удалить из списка"
                @click.stop="onDeactivate(item)"
              >
                <Icon
                  name="medDelete"
                  :size="20"
                  className="med-delete-icon"
                />
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
                    class="schedule-delete-btn"
                    type="button"
                    title="Удалить время приема"
                    aria-label="Удалить время приема"
                    @click="onDeleteSchedule(item.id, sch.id)"
                  >
                    <Icon name="medDelete" :size="18" className="schedule-delete-icon" />
                  </button>
                </li>
              </ul>
              <p v-else class="small muted">Нет расписания</p>
              <button type="button" class="btn small" @click="openScheduleModal(item.id)">
                + Добавить время приема
              </button>
            </div>
          </div>
        </div>
      </div>
    </article>
  </section>

  <!-- Modal for adding schedule -->
  <div v-if="showScheduleModal" class="modal-overlay" @click.self="closeScheduleModal">
    <div class="modal-dialog">
      <div class="modal-header">
        <h3 class="modal-title">Добавить время приема</h3>
        <button type="button" class="modal-close" @click="closeScheduleModal">×</button>
      </div>
      
      <div class="modal-body">
        <div class="form-field">
          <label class="form-label">Время приема</label>
          <input
            v-model="scheduleForm.timeOfDay"
            type="time"
            class="input"
            placeholder="Выберите время"
          />
          <p class="small muted">Например, 08:00 или 13:30</p>
        </div>

        <div class="form-field">
          <label class="form-label">Дни недели</label>
          <div class="days-grid">
            <label v-for="(day, idx) in dayNames" :key="idx" class="day-checkbox">
              <input
                type="checkbox"
                :checked="scheduleForm.daysOfWeek.includes(idx + 1)"
                @change="toggleDay(idx + 1)"
              />
              <span>{{ day }}</span>
            </label>
          </div>
        </div>

        <p v-if="scheduleError" class="error-text schedule-error">
          {{ scheduleError }}
        </p>
      </div>

      <div class="modal-footer">
        <button type="button" class="btn secondary" @click="closeScheduleModal">
          Отмена
        </button>
        <button type="button" class="btn" @click="onAddSchedule">
          Добавить
        </button>
      </div>
    </div>
  </div>
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

.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-size: 13px;
  font-weight: 500;
  color: #333;
}

.input-error {
  border-color: #dc2626 !important;
  background-color: #fef2f2;
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

.icon-action-btn {
  border: none;
  background: transparent;
  padding: 0;
  margin: 0;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 6px;
}

.icon-action-btn:hover {
  background: rgba(0, 0, 0, 0.06);
}

.icon-action-btn:focus-visible {
  outline: 2px solid #1c7ed6;
  outline-offset: 2px;
}

.med-state-icon,
.med-delete-icon {
  background: transparent;
  display: block;
}
.med-details {
  padding: 12px;
  background: #f9f9f9;
  border-top: 1px solid #ddd;
}

.med-help-icon {
  margin-left: 8px;
  cursor: pointer;
  border-radius: 4px;
  background: transparent;
  border: none;
  padding: 0;
  vertical-align: middle;
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
  align-items: center;
  padding: 6px;
  background: transparent;
  border-radius: 3px;
  margin-bottom: 4px;
}

.schedule-delete-btn {
  border: none;
  background: transparent;
  padding: 0;
  margin: 0;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-radius: 6px;
}

.schedule-delete-btn:hover {
  background: rgba(0, 0, 0, 0.06);
}

.schedule-delete-icon {
  background: transparent;
  display: block;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-dialog {
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  max-width: 400px;
  width: 90%;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eaeaf2;
}

.modal-title {
  font-size: 18px;
  font-weight: 600;
  color: #111;
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: #666;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-close:hover {
  color: #111;
}

.modal-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.modal-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding: 16px 20px;
  border-top: 1px solid #eaeaf2;
}

.modal-footer .btn {
  min-width: 100px;
}

.schedule-error {
  margin-top: 4px;
}

.days-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.day-checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s;
}

.day-checkbox:hover {
  background: #f0f0f0;
}

.day-checkbox input[type="checkbox"] {
  cursor: pointer;
  margin: 0;
}

.day-checkbox input[type="checkbox"]:checked {
  accent-color: #0079e0;
}

.day-checkbox input[type="checkbox"]:checked + span {
  font-weight: 600;
  color: #0079e0;
}
</style>
