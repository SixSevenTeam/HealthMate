import { ref, computed } from 'vue';
import { httpRequest } from '@/shared/api/httpClient';

export function useProfile() {
  const profile = ref({
    heightCm: null,
    weightKg: null,
    bloodType: '',
    diagnoses: [],
    allergies: [],
    updatedAt: null,
  });

  const loading = ref(false);
  const error = ref('');
  const success = ref('');

  async function fetchProfile() {
    loading.value = true;
    error.value = '';
    try {
      const data = await httpRequest('/api/profile', { method: 'GET' });
      profile.value = data;
    } catch (err) {
      error.value = err.message || 'Ошибка при загрузке профиля';
    } finally {
      loading.value = false;
    }
  }

  async function updateProfile(updates) {
    loading.value = true;
    error.value = '';
    success.value = '';
    try {
      const payload = {
        heightCm: updates.heightCm !== undefined ? updates.heightCm : profile.value.heightCm,
        weightKg: updates.weightKg !== undefined ? updates.weightKg : profile.value.weightKg,
        bloodType: updates.bloodType !== undefined ? updates.bloodType : profile.value.bloodType,
        diagnoses: updates.diagnoses || profile.value.diagnoses,
        allergies: updates.allergies || profile.value.allergies,
      };

      const response = await httpRequest('/api/profile', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });

      // Update local state
      profile.value = {
        ...profile.value,
        ...payload,
        updatedAt: response.updatedAt || new Date().toISOString(),
      };

      success.value = 'Профиль успешно обновлён';
      return profile.value;
    } catch (err) {
      error.value = err.message || 'Ошибка при обновлении профиля';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  const hasProfile = computed(() => {
    return profile.value.heightCm || profile.value.weightKg || profile.value.bloodType;
  });

  return {
    profile,
    loading,
    error,
    success,
    fetchProfile,
    updateProfile,
    hasProfile,
  };
}
