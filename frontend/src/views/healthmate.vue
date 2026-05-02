<script setup>
import { computed, onMounted, ref } from "vue";
import { getProfile } from "@/entities/profile/api/profileApi";
import {
  getMedications,
  getSchedules,
  getIntakeLogs,
  confirmIntake,
  updateIntakeStatus,
  markIntakeByDate,
} from "@/entities/medications/api/medicationsApi";
import { toLocalDateString } from "@/shared/utils/date";
import Icon from "@/shared/components/Icon.vue";

const profile = ref(null);
const meds = ref([]);
const intakeStore = ref({ marks: {}, history: [] });
const loading = ref(true);
const errorMessage = ref("");
const weekdayLabels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const monthNames = [
  "Января",
  "Февраля",
  "Марта",
  "Апреля",
  "Мая",
  "Июня",
  "Июля",
  "Августа",
  "Сентября",
  "Октября",
  "Ноября",
  "Декабря",
];

function getTodayKey(date = new Date()) {
  const now = date instanceof Date ? date : new Date(date);
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getLocalDateKey(isoValue) {
  if (!isoValue) return getTodayKey();
  const date = new Date(isoValue);
  if (Number.isNaN(date.getTime())) return getTodayKey();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function dateKeyToDate(key) {
  if (!key) return new Date();
  const date = new Date(`${key}T00:00:00`);
  return Number.isNaN(date.getTime()) ? new Date() : date;
}

function addMonthsToDateKey(key, delta) {
  const date = dateKeyToDate(key);
  date.setMonth(date.getMonth() + delta);
  return getTodayKey(date);
}

function getWeekdayIndex(dateKey) {
  const weekday = dateKeyToDate(dateKey).getDay();
  return weekday === 0 ? 7 : weekday;
}

function formatSelectedDate(dateKey) {
  const date = dateKeyToDate(dateKey);
  return date.toLocaleDateString("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

function formatMonthLabel(dateKey) {
  const date = dateKeyToDate(dateKey);
  return `${monthNames[date.getMonth()]} ${date.getFullYear()}`;
}

function getScheduleDaysLabel(daysOfWeek = []) {
  if (!daysOfWeek.length) return "каждый день";
  return daysOfWeek
    .slice()
    .sort((a, b) => a - b)
    .map((day) => weekdayLabels[(day + 6) % 7])
    .join(", ");
}

function uniqueSchedules(schedules = []) {
  const seen = new Set();
  return (schedules || []).filter((schedule) => {
    const key = `${schedule?.timeOfDay || ""}::${(schedule?.daysOfWeek || []).join(",")}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

const activeMeds = computed(() => meds.value.filter((item) => item.isActive));

const bmi = computed(() => {
  if (!profile.value?.heightCm || !profile.value?.weightKg) return null;
  const heightM = profile.value.heightCm / 100;
  return (profile.value.weightKg / (heightM * heightM)).toFixed(1);
});

const bmiStatus = computed(() => {
  const val = parseFloat(bmi.value);
  if (val < 18.5) return "Недостаточный вес";
  if (val < 25) return "Нормальный вес";
  if (val < 30) return "Избыточный вес";
  return "Ожирение";
});

onMounted(async () => {
  loading.value = true;
  errorMessage.value = "";

  try {
    const [profileData, medsData] = await Promise.all([
      getProfile(),
      getMedications(0, 20),
    ]);

    profile.value = profileData;
    const active = medsData?.active || [];
    const inactive = medsData?.inactive || [];
    // Keep intake marking visible even if all medications are currently inactive.
    meds.value = [...active, ...inactive];

    loadLocalStatuses();

    // Load schedules + a wider intake log window so backdated marks and calendar states work.
    for (const med of meds.value) {
      med.selectedDate = getTodayKey();
      med.calendarAnchor = getTodayKey();
      med.calendarOpen = false;
      med.schedules = med.schedules || [];
      med.dailyItems = [];
      try {
        const schedules = await getSchedules(med.id);
        const fromDate = new Date();
        fromDate.setDate(fromDate.getDate() - 30);
        const toDate = new Date();
        toDate.setDate(toDate.getDate() + 14);
        const logsResp = await getIntakeLogs(
          med.id,
          getTodayKey(fromDate),
          getTodayKey(toDate),
        );
        const logs = logsResp?.logs || logsResp || [];

        med.schedules = schedules || [];
        med.intakeLogs = logs;
        refreshMedItems(med);
      } catch (e) {
        refreshMedItems(med);
      }
    }
  } catch (error) {
    errorMessage.value = error.message || "Не удалось загрузить дашборд";
  } finally {
    loading.value = false;
  }
});

function loadLocalStatuses() {
  try {
    const raw = localStorage.getItem("intakeStatusStore");
    const legacyRaw = localStorage.getItem("localIntakeStatuses");
    const parsed = raw ? JSON.parse(raw) : {};

    if (!raw && legacyRaw) {
      const legacyParsed = JSON.parse(legacyRaw);
      intakeStore.value = {
        marks:
          legacyParsed.marks || legacyParsed.dayStatus || legacyParsed || {},
        history: legacyParsed.history || [],
      };
      saveLocalStatuses();
      return;
    }

    intakeStore.value = {
      marks: parsed.marks || parsed.dayStatus || {},
      history: parsed.history || [],
    };
  } catch {
    intakeStore.value = { marks: {}, history: [] };
  }
}

function saveLocalStatuses() {
  try {
    localStorage.setItem(
      "intakeStatusStore",
      JSON.stringify(intakeStore.value || {}),
    );
  } catch {}
}

function buildMarkKey(dayKey, medId, scheduleId, timeOfDay) {
  return `${dayKey}::${medId}::${scheduleId || ""}::${normalizeTime(timeOfDay)}`;
}

function getSavedStatus(medId, scheduleId, timeOfDay, dayKey = getTodayKey()) {
  const exactKey = buildMarkKey(dayKey, medId, scheduleId, timeOfDay);
  const timeOnlyKey = buildMarkKey(dayKey, medId, "", timeOfDay);
  return (
    intakeStore.value.marks?.[exactKey] ||
    intakeStore.value.marks?.[timeOnlyKey] ||
    null
  );
}

function findLogForItem(med, item, dayKey) {
  const targetTime = normalizeTime(item.timeOfDay);
  return (
    (med.intakeLogs || []).find((log) => {
      if (!log?.scheduledAt) return false;
      const logDateKey = getLocalDateKey(log.scheduledAt);
      if (logDateKey !== dayKey) return false;
      return normalizeTime(log.scheduledAt) === targetTime;
    }) || null
  );
}

function refreshItemState(med, item) {
  const dayKey = item.markDate || getTodayKey();
  const saved = getSavedStatus(med.id, item.scheduleId, item.timeOfDay, dayKey);
  const matched = findLogForItem(med, item, dayKey);
  item.log = matched;
  item.status = saved || (matched && matched.status) || null;
}

function upsertHistoryEntry(entry) {
  const idx = intakeStore.value.history.findIndex(
    (item) =>
      item.date === entry.date &&
      item.medId === entry.medId &&
      item.scheduleId === entry.scheduleId,
  );

  if (idx >= 0) {
    intakeStore.value.history[idx] = entry;
  } else {
    intakeStore.value.history.push(entry);
  }
}

function normalizeTime(timeOfDay) {
  if (!timeOfDay) return "00:00";
  return String(timeOfDay).slice(0, 5);
}

function statusIconName(status) {
  if (status === "taken") return "medStateActive";
  if (status === "skipped") return "medStateCanceled";
  if (status === "missed") return "medStateWaiting";
  return null;
}

function statusLabel(status) {
  if (status === "taken") return "Принял";
  if (status === "skipped") return "Намеренно пропущено";
  if (status === "missed") return "Пропущено";
  return "";
}

function buildDailyItemsFromSchedules(
  schedules,
  logs = [],
  medId = null,
  dayKey = getTodayKey(),
) {
  const targetIndex = getWeekdayIndex(dayKey);

  return uniqueSchedules(schedules || [])
    .filter((sch) => {
      const days = sch.daysOfWeek || [];
      return days.length === 0 || days.includes(targetIndex);
    })
    .map((sch) => {
      const matched = (logs || []).find((log) => {
        if (!log?.scheduledAt) return false;
        return (
          getLocalDateKey(log.scheduledAt) === dayKey &&
          normalizeTime(log.scheduledAt) ===
            normalizeTime(sch.timeOfDay || "00:00:00")
        );
      });

      const saved = medId
        ? getSavedStatus(medId, sch.id, sch.timeOfDay, dayKey)
        : null;

      return {
        scheduleId: sch.id,
        timeOfDay: sch.timeOfDay || "00:00:00",
        markDate: dayKey,
        log: matched || null,
        status: saved || (matched && matched.status) || null,
      };
    });
}

function refreshMedItems(med) {
  const dayKey = med.selectedDate || getTodayKey();
  med.dailyItems = buildDailyItemsFromSchedules(
    med.schedules || [],
    med.intakeLogs || [],
    med.id,
    dayKey,
  );
}

async function toggleStatus(med, item, status) {
  const prevStatus = item.status || null;
  const prevLog = item.log ? { ...item.log } : null;
  const dayKey = item.markDate || getTodayKey();
  const exactKey = buildMarkKey(
    dayKey,
    med.id,
    item.scheduleId,
    item.timeOfDay,
  );
  const timeOnlyKey = buildMarkKey(dayKey, med.id, "", item.timeOfDay);
  const prevExactValue = intakeStore.value.marks?.[exactKey];
  const prevTimeOnlyValue = intakeStore.value.marks?.[timeOnlyKey];
  try {
    item.status = status;

    intakeStore.value.marks[exactKey] = status;
    intakeStore.value.marks[timeOnlyKey] = status;
    upsertHistoryEntry({
      date: dayKey,
      medId: med.id,
      scheduleId: item.scheduleId,
      status,
      scheduledAt: item.timeOfDay || null,
      takenAt: status === "taken" ? new Date().toISOString() : null,
    });
    saveLocalStatuses();

    const logDateKey = item.markDate || dayKey;
    const targetLog = item.log || findLogForItem(med, item, logDateKey);

    if (targetLog?.id) {
      if (status === "taken") {
        await confirmIntake(targetLog.id);
      } else {
        await updateIntakeStatus(targetLog.id, status);
      }
    } else {
      const response = await markIntakeByDate(med.id, {
        scheduleId: item.scheduleId,
        date: logDateKey,
        status,
      });
      item.log = {
        id: response.id,
        status: response.status,
        scheduledAt: response.scheduledAt,
        takenAt: response.takenAt,
      };
    }
    refreshMedItems(med);

    // Signal statistics component to refresh data
    try {
      localStorage.setItem("healthmate.intakeMarked", String(Date.now()));
    } catch {}
  } catch (e) {
    // Revert optimistic state if server update failed.
    item.status = prevStatus;
    item.log = prevLog;

    if (typeof prevExactValue === "undefined") {
      delete intakeStore.value.marks[exactKey];
    } else {
      intakeStore.value.marks[exactKey] = prevExactValue;
    }

    if (typeof prevTimeOnlyValue === "undefined") {
      delete intakeStore.value.marks[timeOnlyKey];
    } else {
      intakeStore.value.marks[timeOnlyKey] = prevTimeOnlyValue;
    }

    saveLocalStatuses();
    refreshItemState(med, item);
    errorMessage.value = e?.message || "Не удалось сохранить отметку приёма";
    console.error("Error toggling status:", e);
  }
}

function onMarkDateChange(med, item) {
  refreshItemState(med, item);
}

function setMedicationDay(med, dateKey) {
  med.selectedDate = dateKey;
  med.calendarAnchor = dateKey;
  med.calendarOpen = false;
  refreshMedItems(med);
}

function shiftMedicationMonth(med, delta) {
  med.calendarAnchor = addMonthsToDateKey(
    med.calendarAnchor || med.selectedDate || getTodayKey(),
    delta,
  );
}

function toggleMedicationCalendar(med) {
  med.calendarOpen = !med.calendarOpen;
}

function getMedicationScheduleSummary(med) {
  return uniqueSchedules(med.schedules || []).map((schedule) => ({
    id: schedule.id,
    time: normalizeTime(schedule.timeOfDay),
    days: schedule.daysOfWeek || [],
  }));
}

function buildMedicationCalendar(med) {
  const anchorDate = dateKeyToDate(
    med.calendarAnchor || med.selectedDate || getTodayKey(),
  );
  const startOfMonth = new Date(
    anchorDate.getFullYear(),
    anchorDate.getMonth(),
    1,
  );
  const endOfMonth = new Date(
    anchorDate.getFullYear(),
    anchorDate.getMonth() + 1,
    0,
  );
  const leadingOffset = (startOfMonth.getDay() + 6) % 7;
  const trailingOffset = 6 - ((endOfMonth.getDay() + 6) % 7);
  const startDate = new Date(startOfMonth);
  startDate.setDate(startDate.getDate() - leadingOffset);
  const totalDays = endOfMonth.getDate() + leadingOffset + trailingOffset;
  const scheduleDays = new Set(
    (med.schedules || []).flatMap((schedule) => schedule.daysOfWeek || []),
  );
  const selectedKey = med.selectedDate || getTodayKey();
  const todayKey = getTodayKey();

  return Array.from({ length: totalDays }, (_, index) => {
    const date = new Date(startDate);
    date.setDate(startDate.getDate() + index);
    const dateKey = getTodayKey(date);
    const inMonth = date.getMonth() === anchorDate.getMonth();
    const weekdayIndex = date.getDay() === 0 ? 7 : date.getDay();
    return {
      dateKey,
      day: date.getDate(),
      inMonth,
      selected: dateKey === selectedKey,
      today: dateKey === todayKey,
      scheduled: scheduleDays.size === 0 || scheduleDays.has(weekdayIndex),
      weekdayIndex,
    };
  });
}
</script>

<template>
  <section class="grid two-col">
    <article class="card">
      <h2 class="card-title">Активные лекарства</h2>
      <p class="muted">На данный момент</p>
      <h3 class="big">{{ activeMeds.length }}</h3>
      <ul class="list">
        <li
          v-for="med in activeMeds.slice(0, 4)"
          :key="med.id"
          class="list-item"
        >
          <div style="display: flex; align-items: center; gap: 8px">
            <span style="flex: 1">{{
              med.tradeName || med.customName || "Без названия"
            }}</span>
            <span class="badge ok">{{ med.doseAmount }}{{ med.doseUnit }}</span>
            <!-- no actions here; active meds list shows only name and dose -->
          </div>
        </li>
      </ul>
      <p v-if="activeMeds.length > 4" class="small muted">
        +{{ activeMeds.length - 4 }} еще
      </p>
    </article>

    <article class="card">
      <h2 class="card-title">Ваше здоровье</h2>
      <p class="small">
        Рост: <strong>{{ profile?.heightCm || "-" }} см</strong>
      </p>
      <p class="small">
        Вес: <strong>{{ profile?.weightKg || "-" }} кг</strong>
      </p>
      <p class="small">
        Группа крови: <strong>{{ profile?.bloodType || "-" }}</strong>
      </p>
      <div v-if="bmi" class="health-metric">
        <p class="small">
          BMI: <strong>{{ bmi }}</strong>
        </p>
        <p class="small muted">{{ bmiStatus }}</p>
      </div>
    </article>

    <article class="card">
      <h2 class="card-title">Важная информация</h2>
      <div v-if="profile?.allergies?.length" class="info-block">
        <p class="small"><strong>Аллергии:</strong></p>
        <ul class="list">
          <li
            v-for="allergy in profile.allergies"
            :key="allergy.allergen"
            class="list-item"
          >
            <span>{{ allergy.allergen }}</span>
            <span v-if="allergy.reaction" class="badge warn">{{
              allergy.reaction
            }}</span>
          </li>
        </ul>
      </div>
      <div v-if="profile?.diagnoses?.length" class="info-block">
        <p class="small"><strong>Диагнозы:</strong></p>
        <ul class="list">
          <li
            v-for="diagnosis in profile.diagnoses"
            :key="diagnosis.name"
            class="list-item"
          >
            {{ diagnosis.name }}
          </li>
        </ul>
      </div>
      <p
        v-if="!profile?.allergies?.length && !profile?.diagnoses?.length"
        class="muted"
      >
        Информация не указана
      </p>
    </article>

    <article class="card">
      <h2 class="card-title">Рекомендации</h2>
      <ul class="list">
        <li class="list-item">
          <span>✓ Регулярно принимайте лекарства в назначенное время</span>
        </li>
        <li class="list-item">
          <span>✓ Обновляйте свой медицинский профиль</span>
        </li>
        <li class="list-item">
          <span>✓ Проконсультируйтесь с AI при необходимости</span>
        </li>
      </ul>
    </article>

    <article class="card full-width-card">
      <h2 class="card-title">Отметка приёма лекарств</h2>
      <p class="small muted">
        Выберите день в календаре лекарства. Дни приёма подсвечены, а отметка
        доступна только для этого дня без лишней суеты.
      </p>

      <div class="mark-list">
        <div v-for="med in meds" :key="med.id" class="mark-row full-width-row">
          <div class="med-card-head">
            <div>
              <div class="mark-med-title">
                {{ med.tradeName || med.customName || "Без названия" }}
              </div>
              <p class="small muted">
                {{ med.doseAmount }} {{ med.doseUnit }} ·
                {{ med.description || "Как указано врачом" }}
              </p>
            </div>
            <div class="med-card-meta">
              <span class="badge ok"
                >{{ getMedicationScheduleSummary(med).length }} расписаний</span
              >
              <button
                class="today-chip subtle"
                type="button"
                @click="toggleMedicationCalendar(med)"
              >
                {{
                  med.calendarOpen ? "Скрыть календарь" : "Открыть календарь"
                }}
              </button>
              <button
                class="today-chip"
                type="button"
                @click="setMedicationDay(med, getTodayKey())"
              >
                Сегодня
              </button>
            </div>
          </div>

          <div class="schedule-summary">
            <div class="section-label">Расписание приёма</div>
            <div
              v-if="getMedicationScheduleSummary(med).length"
              class="schedule-chips"
            >
              <span
                v-for="schedule in getMedicationScheduleSummary(med)"
                :key="schedule.id"
                class="schedule-chip"
              >
                {{ schedule.time
                }}<span class="schedule-days"
                  >дни: {{ getScheduleDaysLabel(schedule.days) }}</span
                >
              </span>
            </div>
            <p v-else class="muted small">Расписание ещё не добавлено</p>
          </div>

          <div v-if="med.calendarOpen" class="med-calendar-popover">
            <div class="calendar-top">
              <button
                class="calendar-nav"
                type="button"
                @click="shiftMedicationMonth(med, -1)"
              >
                ‹
              </button>
              <div class="calendar-title">
                {{ formatMonthLabel(med.calendarAnchor || med.selectedDate) }}
              </div>
              <button
                class="calendar-nav"
                type="button"
                @click="shiftMedicationMonth(med, 1)"
              >
                ›
              </button>
            </div>

            <div class="calendar-legend">
              <span><i class="legend-dot scheduled"></i> дни приёма</span>
              <span><i class="legend-dot selected"></i> выбранный день</span>
              <span><i class="legend-dot today"></i> сегодня</span>
            </div>

            <div class="calendar-grid">
              <span
                v-for="dayLabel in weekdayLabels"
                :key="dayLabel"
                class="weekday-label"
                >{{ dayLabel }}</span
              >
              <button
                v-for="cell in buildMedicationCalendar(med)"
                :key="cell.dateKey"
                type="button"
                class="calendar-cell"
                :class="{
                  'out-month': !cell.inMonth,
                  'is-scheduled': cell.scheduled,
                  'is-selected': cell.selected,
                  'is-today': cell.today,
                }"
                @click="setMedicationDay(med, cell.dateKey)"
              >
                <span>{{ cell.day }}</span>
                <i v-if="cell.scheduled" class="cell-mark"></i>
              </button>
            </div>
          </div>

          <div class="day-panel">
            <div class="day-panel-head">
              <div>
                <div class="section-label">Выбранный день</div>
                <div class="day-panel-date">
                  {{ formatSelectedDate(med.selectedDate) }}
                </div>
              </div>
              <div class="day-panel-note">Можно отмечать только этот день</div>
            </div>

            <div v-if="med.dailyItems?.length" class="schedule-list-inline">
              <div
                v-for="item in med.dailyItems"
                :key="item.scheduleId"
                class="schedule-item-inline"
              >
                <div class="schedule-main">
                  <div class="time-row">
                    <div class="time">{{ normalizeTime(item.timeOfDay) }}</div>
                    <div class="status-badge" :class="item.status || 'idle'">
                      {{
                        item.status ? statusLabel(item.status) : "Не отмечено"
                      }}
                    </div>
                  </div>

                  <div v-if="item.status" class="chosen-status compact">
                    <Icon
                      :name="statusIconName(item.status) || 'medStateWaiting'"
                      :size="26"
                    />
                    <span class="status-text">{{
                      statusLabel(item.status)
                    }}</span>
                  </div>

                  <div v-else class="icons">
                    <button
                      class="icon-btn primary"
                      type="button"
                      aria-label="Принял"
                      title="Принял"
                      data-tooltip="Принял"
                      @click="() => toggleStatus(med, item, 'taken')"
                    >
                      <Icon name="medStateActive" :size="22" />
                    </button>
                    <button
                      class="icon-btn warning"
                      type="button"
                      aria-label="Намеренно пропущено"
                      title="Намеренно пропущено"
                      data-tooltip="Намеренно пропущено"
                      @click="() => toggleStatus(med, item, 'skipped')"
                    >
                      <Icon name="medStateCanceled" :size="22" />
                    </button>
                    <button
                      class="icon-btn ghost"
                      type="button"
                      aria-label="Пропущено"
                      title="Пропущено"
                      data-tooltip="Пропущено"
                      @click="() => toggleStatus(med, item, 'missed')"
                    >
                      <Icon name="medStateWaiting" :size="22" />
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="muted small empty-day-state">
              На выбранный день приёма не найдено
            </div>
          </div>
        </div>

        <div v-if="!meds.length" class="muted small empty-day-state">
          Нет препаратов для отметки. Добавьте лекарство в разделе "Мои
          лекарства".
        </div>
      </div>
    </article>
  </section>
</template>

<style scoped>
.full-width-card {
  grid-column: 1 / -1;
}

.mark-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.mark-row {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  justify-content: space-between;
  padding: 12px;
  border: 1px solid #f0f2f6;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f9fbff 100%);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
  position: relative;
}

.mark-med-title {
  font-weight: 700;
  font-size: 16px;
}
.med-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
}
.med-card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.today-chip {
  border: none;
  padding: 9px 12px;
  border-radius: 999px;
  background: #0f172a;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 10px 18px rgba(15, 23, 42, 0.15);
}
.today-chip.subtle {
  background: #e2e8f0;
  color: #0f172a;
  box-shadow: none;
}
.today-chip:hover {
  transform: translateY(-1px);
}
.schedule-summary,
.day-panel,
.med-calendar-shell {
  width: 100%;
}
.section-label {
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6b7280;
  margin-bottom: 8px;
}
.schedule-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.schedule-chip {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: #eff6ff;
  color: #12304d;
  font-weight: 700;
}
.schedule-days {
  font-weight: 500;
  color: #4b5563;
}
.med-calendar-popover {
  position: absolute;
  right: 18px;
  top: 72px;
  width: min(420px, calc(100vw - 48px));
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border-radius: 20px;
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.98) 0%,
    rgba(246, 250, 255, 0.98) 100%
  );
  border: 1px solid rgba(191, 219, 254, 0.9);
  box-shadow: 0 28px 80px rgba(15, 23, 42, 0.22);
  z-index: 10;
}
.calendar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.calendar-title {
  font-weight: 800;
  font-size: 15px;
  color: #0f172a;
  text-transform: capitalize;
}
.calendar-nav {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 999px;
  background: #fff;
  color: #0f172a;
  font-size: 22px;
  line-height: 1;
  box-shadow: 0 6px 14px rgba(15, 23, 42, 0.12);
  cursor: pointer;
}
.calendar-nav:hover {
  transform: translateY(-1px);
}
.calendar-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: #4b5563;
}
.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  margin-right: 6px;
  vertical-align: middle;
}
.legend-dot.scheduled {
  background: #93c5fd;
}
.legend-dot.selected {
  background: #2563eb;
}
.legend-dot.today {
  background: #f59e0b;
}
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
}
.weekday-label {
  text-align: center;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  padding-bottom: 4px;
}
.calendar-cell {
  position: relative;
  min-height: 54px;
  border-radius: 14px;
  border: 1px solid #dce7f7;
  background: #fff;
  color: #0f172a;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 4px;
}
.calendar-cell.out-month {
  opacity: 0.42;
}
.calendar-cell.is-scheduled {
  border-color: #93c5fd;
  background: #eff6ff;
}
.calendar-cell.is-selected {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.14);
}
.calendar-cell.is-today {
  background: #fff7ed;
  border-color: #f59e0b;
}
.cell-mark {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #2563eb;
}
.calendar-cell.is-selected .cell-mark {
  background: #fff;
}
.calendar-cell.is-today .cell-mark {
  background: #f59e0b;
}
.day-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.day-panel-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.day-panel-date {
  font-weight: 800;
  font-size: 16px;
  color: #0f172a;
  text-transform: capitalize;
}
.day-panel-note {
  font-size: 12px;
  color: #64748b;
  background: #f8fafc;
  padding: 8px 10px;
  border-radius: 999px;
}
.day-panel {
  padding-top: 4px;
}
.status-badge {
  font-size: 12px;
  font-weight: 700;
  padding: 8px 10px;
  border-radius: 999px;
  background: #e5e7eb;
  color: #334155;
}
.status-badge.taken {
  background: #dcfce7;
  color: #166534;
}
.status-badge.skipped {
  background: #fef3c7;
  color: #92400e;
}
.status-badge.missed {
  background: #fee2e2;
  color: #991b1b;
}
.status-badge.idle {
  background: #e2e8f0;
  color: #475569;
}
.schedule-list-inline {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}
.schedule-item-inline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  background: linear-gradient(180deg, #fbfcff 0%, #f7f9fe 100%);
  border: 1px solid #e8eef8;
  box-shadow: 0 1px 0 rgba(17, 24, 39, 0.03);
}
.schedule-main {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}
.time-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.schedule-item-inline .time {
  min-width: 72px;
  color: #1f2d3d;
  font-weight: 700;
}
.icons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.icon-btn {
  position: relative;
  background: transparent;
  border: none;
  padding: 6px;
  border-radius: 8px;
  cursor: pointer;
}
.icon-btn.primary {
  background: #ecfdf5;
}
.icon-btn.warning {
  background: #fff7ed;
}
.icon-btn.ghost {
  background: #eff6ff;
}
.icon-btn.active {
  background: rgba(255, 255, 255, 0.06);
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.08);
}
.icon-btn::after {
  content: attr(data-tooltip);
  position: absolute;
  left: 50%;
  top: -34px;
  transform: translateX(-50%);
  white-space: nowrap;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(15, 20, 28, 0.96);
  color: #fff;
  font-size: 12px;
  line-height: 1;
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.22);
}

.icon-btn:hover::after,
.icon-btn:focus-visible::after {
  opacity: 1;
  transform: translateX(-50%) translateY(-2px);
}

.chosen-status {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.08);
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.12);
}
.chosen-status.compact {
  width: auto;
  height: auto;
  align-self: flex-start;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 999px;
}
.chosen-status :deep(img),
.chosen-status :deep(svg) {
  display: block;
}
.chosen-status :deep(svg),
.chosen-status :deep(img) {
  width: 28px;
  height: 28px;
}
.status-text {
  font-size: 13px;
  font-weight: 600;
  color: #17324d;
}
.empty-day-state {
  padding: 12px 2px 4px;
}
.icon-tooltip {
  position: absolute;
  top: -34px;
  left: 50%;
  transform: translateX(-50%);
  white-space: nowrap;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(15, 20, 28, 0.96);
  color: #fff;
  font-size: 12px;
  line-height: 1;
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.22);
}

.chosen-status:hover .icon-tooltip {
  opacity: 1;
  transform: translateX(-50%) translateY(-2px);
}

.mark-btn {
  background: transparent;
  border: none;
  padding: 10px;
  border-radius: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.mark-btn:active {
  transform: scale(0.98);
}

@media (max-width: 900px) {
  .med-card-head {
    flex-direction: column;
    align-items: flex-start;
  }
  .med-card-meta {
    justify-content: flex-start;
  }
  .med-calendar-popover {
    position: static;
    width: 100%;
    margin-top: 8px;
  }
}
</style>
