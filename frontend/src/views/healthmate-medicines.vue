<script setup>
import { onMounted, ref } from 'vue';
import {
  createMedication,
  deactivateMedication,
  getMedications,
  setMedicationActive,
  validateMedication,
} from '@/entities/medications/api/medicationsApi';

const meds = ref([]);
const page = ref(0);
const size = ref(20);
const total = ref(0);
const loading = ref(false);
const errorMessage = ref('');
const notice = ref('');

const form = ref({
  customName: '',
  doseAmount: 0,
  doseUnit: 'mg',
  instructions: '',
  startDate: new Date().toISOString().slice(0, 10),
  endDate: null,
});

async function loadMedications() {
  loading.value = true;
  errorMessage.value = '';
  try {
    const data = await getMedications(page.value, size.value);
    meds.value = [...(data.active || []), ...(data.inactive || [])];
    total.value = data.total || meds.value.length;
  } catch (error) {
    errorMessage.value = error.message || 'Не удалось загрузить лекарства';
  } finally {
    loading.value = false;
  }
}

async function onCreate() {
  notice.value = '';
  errorMessage.value = '';
  try {
    const validation = await validateMedication({
      customName: form.value.customName,
      doseAmount: Number(form.value.doseAmount),
      doseUnit: form.value.doseUnit,
      instructions: form.value.instructions,
      startDate: form.value.startDate,
      endDate: form.value.endDate,
    });

    if ((validation?.warnings || []).length > 0) {
      notice.value = validation.warnings.join('; ');
    }

    await createMedication({
      drugId: null,
      customName: form.value.customName,
      doseAmount: Number(form.value.doseAmount),
      doseUnit: form.value.doseUnit,
      instructions: form.value.instructions,
      startDate: form.value.startDate,
      endDate: form.value.endDate,
      schedules: [{ timeOfDay: '08:00:00', daysOfWeek: [1, 2, 3, 4, 5] }],
    });

    form.value.customName = '';
    form.value.doseAmount = 0;
    form.value.instructions = '';
    await loadMedications();
  } catch (error) {
    errorMessage.value = error.message || 'Не удалось добавить лекарство';
  }
}

async function onToggle(item) {
  try {
    await setMedicationActive(item.id, !item.isActive);
    await loadMedications();
  } catch (error) {
    errorMessage.value = error.message || 'Не удалось изменить статус';
  }
}

async function onDeactivate(item) {
  try {
    await deactivateMedication(item.id);
    await loadMedications();
  } catch (error) {
    errorMessage.value = error.message || 'Не удалось деактивировать лекарство';
  }
}

onMounted(loadMedications);
</script>

<template>
  <section class="stack">
    <article class="card">
      <h2 class="card-title">Добавить лекарство</h2>
      <div class="form-grid">
        <input v-model="form.customName" class="input" placeholder="Название" />
        <input v-model.number="form.doseAmount" class="input" type="number" placeholder="Доза" />
        <input v-model="form.doseUnit" class="input" placeholder="Единица" />
        <input v-model="form.instructions" class="input" placeholder="Инструкция" />
        <input v-model="form.startDate" class="input" type="date" />
        <button class="btn" type="button" @click="onCreate">Сохранить</button>
      </div>
      <p v-if="notice" class="small warning">{{ notice }}</p>
    </article>

    <article class="card">
      <h2 class="card-title">Список лекарств</h2>
      <p v-if="loading" class="muted">Загрузка...</p>
      <p v-else-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <div v-else class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Доза</th>
              <th>Статус</th>
              <th>Действие</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in meds" :key="item.id">
              <td>{{ item.tradeName || item.customName }}</td>
              <td>{{ item.doseAmount }} {{ item.doseUnit }}</td>
              <td>
                <span class="badge" :class="item.isActive ? 'ok' : 'warn'">
                  {{ item.isActive ? 'Активно' : 'Неактивно' }}
                </span>
              </td>
              <td>
                <button class="text-btn" type="button" @click="onToggle(item)">
                  {{ item.isActive ? 'Отключить' : 'Включить' }}
                </button>
                <button class="text-btn danger" type="button" @click="onDeactivate(item)">Удалить</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="small">Всего: {{ total }}</p>
    </article>
  </section>
</template>
