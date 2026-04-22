<script setup>
import { computed, onMounted, ref } from 'vue';
import { getProfile } from '@/entities/profile/api/profileApi';
import { getHealth } from '@/entities/health/api/healthApi';
import { getMedications } from '@/entities/medications/api/medicationsApi';
import { toLocalDateString } from '@/shared/utils/date';

const health = ref(null);
const profile = ref(null);
const meds = ref([]);
const loading = ref(true);
const errorMessage = ref('');

const activeMeds = computed(() => meds.value.filter((item) => item.isActive));

onMounted(async () => {
  loading.value = true;
  errorMessage.value = '';

  try {
    const [healthData, profileData, medsData] = await Promise.all([
      getHealth(),
      getProfile(),
      getMedications(0, 20),
    ]);

    health.value = healthData;
    profile.value = profileData;
    meds.value = medsData.active || [];
  } catch (error) {
    errorMessage.value = error.message || 'Не удалось загрузить дашборд';
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <section class="grid two-col">
    <article class="card">
      <h2 class="card-title">Следующий прием</h2>
      <p class="muted">Активные лекарства</p>
      <h3 class="big">{{ activeMeds.length }}</h3>
      <ul class="list">
        <li v-for="med in activeMeds.slice(0, 4)" :key="med.id" class="list-item">
          <span>{{ med.tradeName || med.customName || 'Без названия' }}</span>
          <span class="badge ok">{{ med.safetyStatus || 'ok' }}</span>
        </li>
      </ul>
    </article>

    <article class="card">
      <h2 class="card-title">Состояние сервиса</h2>
      <p class="muted">Backend health-check</p>
      <h3 class="big">{{ health?.status || '-' }}</h3>
      <p class="small">Сервис: {{ health?.service || '-' }}</p>
      <p class="small">{{ toLocalDateString(health?.timestamp) }}</p>
    </article>

    <article class="card">
      <h2 class="card-title">Медпрофиль</h2>
      <p class="small">Рост: {{ profile?.heightCm || '-' }} см</p>
      <p class="small">Вес: {{ profile?.weightKg || '-' }} кг</p>
      <p class="small">Группа крови: {{ profile?.bloodType || '-' }}</p>
      <p class="small">Обновлен: {{ toLocalDateString(profile?.updatedAt) }}</p>
    </article>

    <article class="card">
      <h2 class="card-title">Статус</h2>
      <p v-if="loading" class="muted">Загрузка...</p>
      <p v-else-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      <p v-else class="muted">Данные синхронизированы</p>
    </article>
  </section>
</template>
