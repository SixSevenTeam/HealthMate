<script setup>
import { computed, onMounted, ref } from 'vue';
import { getDashboardSummary } from '@/entities/dashboard/api/dashboardApi';
import { toPercent } from '@/shared/utils/date';

const loading = ref(false);
const errorMessage = ref('');
const summary = ref(null);

function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

const insights = computed(() => summary.value?.insights || []);
const adherence = computed(() => summary.value?.adherence || []);
const averageAdherence = computed(() => {
  if (adherence.value.length === 0) return '0.00';
  const total = adherence.value.reduce((acc, item) => acc + (item.adherencePercent || 0), 0);
  return toPercent(total / adherence.value.length);
});

onMounted(async () => {
  loading.value = true;
  errorMessage.value = '';

  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - 6);

  try {
    summary.value = await getDashboardSummary(formatDate(from), formatDate(to));
  } catch (error) {
    errorMessage.value = error.message || 'Не удалось загрузить статистику';
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <section class="stack">
    <article class="card">
      <h2 class="card-title">Сводка</h2>
      <p v-if="loading" class="muted">Загрузка...</p>
      <p v-else-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <div v-else class="kpi-row">
        <div class="kpi-item">
          <p class="muted">Средняя приверженность</p>
          <p class="big">{{ averageAdherence }}%</p>
        </div>
        <div class="kpi-item">
          <p class="muted">Записей</p>
          <p class="big">{{ adherence.length }}</p>
        </div>
      </div>
    </article>

    <article class="card">
      <h2 class="card-title">Adherence по лекарствам</h2>
      <div class="table-wrap">
        <table class="table">
          <thead>
            <tr>
              <th>Лекарство</th>
              <th>Принято</th>
              <th>Назначено</th>
              <th>%</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in adherence" :key="item.medicationId">
              <td>{{ item.tradeName }}</td>
              <td>{{ item.totalTaken }}</td>
              <td>{{ item.totalScheduled }}</td>
              <td>{{ toPercent(item.adherencePercent) }}%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>

    <article class="card">
      <h2 class="card-title">Инсайты</h2>
      <ul class="list">
        <li v-for="text in insights" :key="text" class="list-item">{{ text }}</li>
      </ul>
    </article>
  </section>
</template>
