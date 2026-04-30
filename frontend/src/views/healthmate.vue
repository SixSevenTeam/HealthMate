<script setup>
import { computed, onMounted, ref } from 'vue';
import { getProfile } from '@/entities/profile/api/profileApi';
import { getMedications, getSchedules, getIntakeLogs, confirmIntake, updateIntakeStatus } from '@/entities/medications/api/medicationsApi';
import { toLocalDateString } from '@/shared/utils/date';
import Icon from '@/shared/components/Icon.vue';

const profile = ref(null);
const meds = ref([]);
const intakeStore = ref({ marks: {}, history: [] });
const loading = ref(true);
const errorMessage = ref('');

const activeMeds = computed(() => meds.value.filter((item) => item.isActive));

const bmi = computed(() => {
  if (!profile.value?.heightCm || !profile.value?.weightKg) return null;
  const heightM = profile.value.heightCm / 100;
  return (profile.value.weightKg / (heightM * heightM)).toFixed(1);
});

const bmiStatus = computed(() => {
  const val = parseFloat(bmi.value);
  if (val < 18.5) return 'Недостаточный вес';
  if (val < 25) return 'Нормальный вес';
  if (val < 30) return 'Избыточный вес';
  return 'Ожирение';
});

onMounted(async () => {
  loading.value = true;
  errorMessage.value = '';

  try {
    const [profileData, medsData] = await Promise.all([
      getProfile(),
      getMedications(0, 20),
    ]);

    profile.value = profileData;
    meds.value = medsData.active || [];

    loadLocalStatuses();

    // Load schedules + today's intake logs per medication
    for (const med of meds.value) {
      med.dailyItems = buildDailyItemsFromSchedules(med.schedules || []);
      try {
        const schedules = await getSchedules(med.id);
        const logsResp = await getIntakeLogs(med.id, '', '');
        const logs = logsResp?.logs || logsResp || [];

        med.dailyItems = buildDailyItemsFromSchedules(schedules || [], logs, med.id);
      } catch (e) {
        // keep the fallback built from med.schedules so UI still shows times/icons
      }
    }
  } catch (error) {
    errorMessage.value = error.message || 'Не удалось загрузить дашборд';
  } finally {
    loading.value = false;
  }
});

async function markTaken(med) {
  if (!med.latestLog?.id) return;
  try {
    const res = await confirmIntake(med.latestLog.id);
    med.latestLog.status = res.status || 'taken';
  } catch (e) {
    console.error(e);
  }
}

async function setLogStatus(med, status) {
  if (!med.latestLog?.id) return;
  try {
    const res = await updateIntakeStatus(med.latestLog.id, status);
    med.latestLog.status = res.status;
  } catch (e) {
    console.error(e);
  }
}

function loadLocalStatuses() {
  try {
    const raw = localStorage.getItem('intakeStatusStore');
    const legacyRaw = localStorage.getItem('localIntakeStatuses');
    const parsed = raw ? JSON.parse(raw) : {};

    if (!raw && legacyRaw) {
      const legacyParsed = JSON.parse(legacyRaw);
      intakeStore.value = {
        marks: legacyParsed.marks || legacyParsed.dayStatus || legacyParsed || {},
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
    localStorage.setItem('intakeStatusStore', JSON.stringify(intakeStore.value || {}));
  } catch {}
}

function getTodayKey() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function buildMarkKey(dayKey, medId, scheduleId, timeOfDay) {
  return `${dayKey}::${medId}::${scheduleId || ''}::${normalizeTime(timeOfDay)}`;
}

function getStatusBucket(dayKey = getTodayKey(), medId = null) {
  if (!medId) return null;
  return intakeStore.value.marks;
}

function getSavedStatus(medId, scheduleId, timeOfDay, dayKey = getTodayKey()) {
  const exactKey = buildMarkKey(dayKey, medId, scheduleId, timeOfDay);
  const timeOnlyKey = buildMarkKey(dayKey, medId, '', timeOfDay);
  return intakeStore.value.marks?.[exactKey] || intakeStore.value.marks?.[timeOnlyKey] || null;
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
  if (!timeOfDay) return '00:00';
  return String(timeOfDay).slice(0, 5);
}

function statusIconName(status) {
  if (status === 'taken') return 'medStateActive';
  if (status === 'skipped') return 'medStateCanceled';
  if (status === 'missed') return 'medStateWaiting';
  return null;
}

function statusLabel(status) {
  if (status === 'taken') return 'Принял';
  if (status === 'skipped') return 'Намеренно пропущено';
  if (status === 'missed') return 'Пропущено';
  return '';
}

function buildDailyItemsFromSchedules(schedules, logs = [], medId = null) {
  const todayWeekday = new Date().getDay();
  const todayIndex = todayWeekday === 0 ? 7 : todayWeekday;
  const todayKey = getTodayKey();

  return (schedules || [])
    .filter((sch) => {
      const days = sch.daysOfWeek || [];
      return days.length === 0 || days.includes(todayIndex);
    })
    .map((sch) => {
      const matched = (logs || []).find((l) => {
        if (!l.scheduledAt) return false;
        return l.scheduledAt.includes(sch.timeOfDay || '');
      });

      const saved = medId ? getSavedStatus(medId, sch.id, sch.timeOfDay, todayKey) : null;

      return {
        scheduleId: sch.id,
        timeOfDay: sch.timeOfDay || '00:00:00',
        log: matched || null,
        status: saved || (matched && matched.status) || null,
      };
    });
}

async function toggleStatus(med, item, status) {
  // Immediately update UI and persist locally, call API in background.
  try {
    const dayKey = getTodayKey();
    const exactKey = buildMarkKey(dayKey, med.id, item.scheduleId, item.timeOfDay);
    const timeOnlyKey = buildMarkKey(dayKey, med.id, '', item.timeOfDay);

    // Optimistically set status on the item so icon appears immediately
    item.status = status;

    // Persist to local store
    intakeStore.value.marks[exactKey] = status;
    intakeStore.value.marks[timeOnlyKey] = status;
    upsertHistoryEntry({
      date: dayKey,
      medId: med.id,
      scheduleId: item.scheduleId,
      status,
      scheduledAt: item.timeOfDay || null,
      takenAt: status === 'taken' ? new Date().toISOString() : null,
    });
    saveLocalStatuses();

    // Fire-and-forget API call: don't block UI or overwrite optimistic state
    (async () => {
      try {
        if (item.log && item.log.id) {
          if (status === 'taken') {
            await confirmIntake(item.log.id);
          } else {
            await updateIntakeStatus(item.log.id, status);
          }
        } else {
          // No server log exists; attempt to call confirmIntake if API supports creating
          // a log via confirmIntake with null id is not supported here, so skip.
        }
      } catch (e) {
        // Keep optimistic UI; log the error for debugging
        console.error('Background API error while toggling intake status', e);
      }
    })();
  } catch (e) {
    console.error('Error toggling status:', e);
  }
}
</script>

<template>
  <section class="grid two-col">
    <article class="card">
      <h2 class="card-title">Активные лекарства</h2>
      <p class="muted">На данный момент</p>
      <h3 class="big">{{ activeMeds.length }}</h3>
      <ul class="list">
        <li v-for="med in activeMeds.slice(0, 4)" :key="med.id" class="list-item">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="flex:1">{{ med.tradeName || med.customName || 'Без названия' }}</span>
            <span class="badge ok">{{ med.doseAmount }}{{ med.doseUnit }}</span>
            <!-- no actions here; active meds list shows only name and dose -->
          </div>
        </li>
      </ul>
      <p v-if="activeMeds.length > 4" class="small muted">+{{ activeMeds.length - 4 }} еще</p>
    </article>

    <article class="card">
      <h2 class="card-title">Ваше здоровье</h2>
      <p class="small">Рост: <strong>{{ profile?.heightCm || '-' }} см</strong></p>
      <p class="small">Вес: <strong>{{ profile?.weightKg || '-' }} кг</strong></p>
      <p class="small">Группа крови: <strong>{{ profile?.bloodType || '-' }}</strong></p>
      <div v-if="bmi" class="health-metric">
        <p class="small">BMI: <strong>{{ bmi }}</strong></p>
        <p class="small muted">{{ bmiStatus }}</p>
      </div>
    </article>

    <article class="card">
      <h2 class="card-title">Важная информация</h2>
      <div v-if="profile?.allergies?.length" class="info-block">
        <p class="small"><strong>Аллергии:</strong></p>
        <ul class="list">
          <li v-for="allergy in profile.allergies" :key="allergy.allergen" class="list-item">
            <span>{{ allergy.allergen }}</span>
            <span v-if="allergy.reaction" class="badge warn">{{ allergy.reaction }}</span>
          </li>
        </ul>
      </div>
      <div v-if="profile?.diagnoses?.length" class="info-block">
        <p class="small"><strong>Диагнозы:</strong></p>
        <ul class="list">
          <li v-for="diagnosis in profile.diagnoses" :key="diagnosis.name" class="list-item">
            {{ diagnosis.name }}
          </li>
        </ul>
      </div>
      <p v-if="!profile?.allergies?.length && !profile?.diagnoses?.length" class="muted">
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
      <p class="small muted">Отметьте каждый приём за сегодня. После выбора останется только одна иконка рядом со временем.</p>

      <div class="mark-list">
        <div v-for="med in meds" :key="med.id" class="mark-row full-width-row">
          <div class="mark-med-title">{{ med.tradeName || med.customName || 'Без названия' }}</div>
          <div v-if="med.dailyItems?.length" class="schedule-list-inline">
            <div v-for="item in med.dailyItems" :key="item.scheduleId" class="schedule-item-inline">
              <div class="time">{{ normalizeTime(item.timeOfDay) }}</div>

              <div v-if="item.status" class="chosen-status">
                <span class="icon-tooltip">{{ statusLabel(item.status) }}</span>
                <Icon :name="statusIconName(item.status) || 'medStateWaiting'" :size="28" />
              </div>

              <div v-else class="icons">
                <button class="icon-btn" type="button" aria-label="Принял" title="Принял" data-tooltip="Принял" @click="() => toggleStatus(med, item, 'taken')">
                  <Icon name="medStateActive" :size="22" />
                </button>
                <button class="icon-btn" type="button" aria-label="Намеренно пропущено" title="Намеренно пропущено" data-tooltip="Намеренно пропущено" @click="() => toggleStatus(med, item, 'skipped')">
                  <Icon name="medStateCanceled" :size="22" />
                </button>
                <button class="icon-btn" type="button" aria-label="Пропущено" title="Пропущено" data-tooltip="Пропущено" @click="() => toggleStatus(med, item, 'missed')">
                  <Icon name="medStateWaiting" :size="22" />
                </button>
              </div>
            </div>
          </div>
          <div v-else class="muted small">На сегодня приёмов нет</div>
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
  display:flex;
  flex-direction:column;
  gap:8px;
  margin-top:8px;
}

.mark-row {
  display:flex;
  flex-direction:column;
  align-items:flex-start;
  gap:10px;
  justify-content:space-between;
  padding:12px;
  border:1px solid #f0f2f6;
  border-radius:8px;
  background: transparent;
}

.mark-med-title { font-weight:700; font-size:16px }
.schedule-list-inline { display:flex; flex-direction:column; gap:10px; width:100% }
.schedule-item-inline { display:flex; align-items:center; justify-content:space-between; gap:12px; width:100%; padding:10px 12px; border-radius:12px; background:#fafbfd; border:1px solid #edf1f7 }
.schedule-item-inline .time { min-width:72px; color:#1f2d3d; font-weight:700 }
.icons { display:flex; gap:8px }
.icon-btn { position:relative; background:transparent; border:none; padding:6px; border-radius:8px; cursor:pointer }
.icon-btn.active { background:rgba(255,255,255,0.06); box-shadow:0 4px 10px rgba(0,0,0,0.08) }
.icon-btn::after {
  content: attr(data-tooltip);
  position:absolute;
  left:50%;
  top:-34px;
  transform:translateX(-50%);
  white-space:nowrap;
  padding:5px 9px;
  border-radius:999px;
  background:rgba(15,20,28,0.96);
  color:#fff;
  font-size:12px;
  line-height:1;
  opacity:0;
  pointer-events:none;
  transition:opacity 0.15s ease, transform 0.15s ease;
  box-shadow:0 10px 24px rgba(0,0,0,0.22);
}

.icon-btn:hover::after,
.icon-btn:focus-visible::after {
  opacity:1;
  transform:translateX(-50%) translateY(-2px);
}

.chosen-status { position:relative; display:flex; align-items:center; justify-content:center; width:44px; height:44px; border-radius:999px; background:rgba(255,255,255,0.06); box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08) }
.chosen-status :deep(img), .chosen-status :deep(svg) { display:block }
.chosen-status :deep(svg), .chosen-status :deep(img) { width:28px; height:28px }
.icon-tooltip {
  position:absolute;
  top:-34px;
  left:50%;
  transform:translateX(-50%);
  white-space:nowrap;
  padding:5px 9px;
  border-radius:999px;
  background:rgba(15,20,28,0.96);
  color:#fff;
  font-size:12px;
  line-height:1;
  opacity:0;
  pointer-events:none;
  transition:opacity 0.15s ease, transform 0.15s ease;
  box-shadow:0 10px 24px rgba(0,0,0,0.22);
}

.chosen-status:hover .icon-tooltip {
  opacity:1;
  transform:translateX(-50%) translateY(-2px);
}

.mark-btn { background:transparent; border:none; padding:10px; border-radius:12px; cursor:pointer; display:flex; align-items:center; justify-content:center }
.mark-btn:active { transform:scale(0.98) }

</style>
