<template>
  <div v-if="isOpen" class="profile-modal-overlay" @click.self="closeModal">
    <div class="profile-modal">
      <!-- Header -->
      <div class="profile-modal-header">
        <h2 class="profile-modal-title">Профиль</h2>
        <button class="profile-modal-close" @click="closeModal">
          <Icon name="closeMenu" size="20" />
        </button>
      </div>

      <!-- Content -->
      <div class="profile-modal-content">
        <form @submit.prevent="handleSave">
          <div class="profile-section">
            <h3 class="profile-section-title">
              <Icon name="profilePersonal" size="18" />
              <span>Личная информация</span>
            </h3>
            <div class="profile-info-list">
              <div class="profile-info-item">
                <span class="profile-label">Имя:</span>
                <span class="profile-value">{{ userName }}</span>
              </div>
              <div class="profile-info-item">
                <span class="profile-label">Email:</span>
                <span class="profile-value">{{ userEmail }}</span>
              </div>
            </div>
          </div>

          <div class="profile-section">
            <h3 class="profile-section-title">
              <Icon name="profileSecurity" size="18" />
              <span>Медицинские данные</span>
            </h3>

            <div class="profile-field-grid">
              <div class="profile-field">
                <label class="profile-field-label">Рост (см)</label>
                <input
                    v-model.number="formData.heightCm"
                    type="number"
                    class="profile-field-input"
                    placeholder="180"
                />
              </div>

              <div class="profile-field">
                <label class="profile-field-label">Вес (кг)</label>
                <input
                    v-model.number="formData.weightKg"
                    type="number"
                    class="profile-field-input"
                    placeholder="75"
                    step="0.1"
                />
              </div>

              <div class="profile-field profile-field-full">
                <label class="profile-field-label">Группа крови</label>
                <select v-model="formData.bloodType" class="profile-field-input">
                  <option value="">Не указано</option>
                  <option value="A+">A+</option>
                  <option value="A-">A-</option>
                  <option value="B+">B+</option>
                  <option value="B-">B-</option>
                  <option value="AB+">AB+</option>
                  <option value="AB-">AB-</option>
                  <option value="O+">O+</option>
                  <option value="O-">O-</option>
                </select>
              </div>
            </div>

            <!-- Diagnoses Section -->
            <div class="profile-field profile-field-full">
              <label class="profile-field-label">
                Диагнозы
                <span class="profile-field-hint">(дату можно не указывать)</span>
              </label>
              <div class="profile-badges-container">
                <div
                    v-for="(diag, index) in formData.diagnoses"
                    :key="'diag-' + index"
                    class="profile-badge editable"
                >
                  <input
                      v-model="diag.name"
                      class="badge-input"
                      placeholder="Название (напр. Гипертония)"
                      required
                  />
                  <input
                      v-model="diag.diagnosedAt"
                      type="date"
                      class="badge-input date-input"
                      title="Дата постановки диагноза (необязательно)"
                  />
                  <button type="button" class="badge-remove" @click="removeDiagnosis(index)" title="Удалить">×</button>
                </div>
              </div>
              <button type="button" class="profile-btn-add" @click="addDiagnosis">
                + Добавить диагноз
              </button>
            </div>

            <!-- Allergies Section -->
            <div class="profile-field profile-field-full">
              <label class="profile-field-label">Аллергии</label>
              <div class="profile-badges-container">
                <div
                    v-for="(allergy, index) in formData.allergies"
                    :key="'allergy-' + index"
                    class="profile-badge editable allergy"
                >
                  <input
                      v-model="allergy.allergen"
                      class="badge-input"
                      placeholder="Аллерген (напр. Пенициллин)"
                  />
                  <input
                      v-model="allergy.reaction"
                      class="badge-input"
                      placeholder="Реакция (напр. Сыпь)"
                  />
                  <button type="button" class="badge-remove" @click="removeAllergy(index)" title="Удалить">×</button>
                </div>
              </div>
              <button type="button" class="profile-btn-add" @click="addAllergy">
                + Добавить аллергию
              </button>
            </div>

            <div v-if="error" class="profile-error">{{ error }}</div>
            <div v-if="success" class="profile-success">{{ success }}</div>

            <div class="profile-modal-actions">
              <button
                  type="submit"
                  class="profile-btn profile-btn-primary"
                  :disabled="loading"
              >
                <Icon name="edit" size="18" />
                <span>{{ loading ? 'Сохранение...' : 'Сохранить' }}</span>
              </button>
              <button
                  type="button"
                  class="profile-btn profile-btn-secondary"
                  @click="closeModal"
                  :disabled="loading"
              >
                Отмена
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useProfile } from '@/shared/composables/useProfile';
import { useSession } from '@/features/session/useSession';
import Icon from '@/shared/components/Icon.vue';

const props = defineProps({
  isOpen: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['close']);

const { profile: profileData, loading, error, success, fetchProfile, updateProfile } = useProfile();
const { user } = useSession();

const formData = ref({
  heightCm: null,
  weightKg: null,
  bloodType: '',
  diagnoses: [],
  allergies: []
});

const userName = computed(() => {
  if (!user.value) return 'Гость';
  return `${user.value.firstName || ''} ${user.value.lastName || ''}`.trim();
});

const userEmail = computed(() => user.value?.email || 'не указан');

// Sync form data with profile data (deep copy to avoid mutating store directly)
watch(
    () => profileData.value,
    (newProfile) => {
      if (newProfile) {
        formData.value.heightCm = newProfile.heightCm;
        formData.value.weightKg = newProfile.weightKg;
        formData.value.bloodType = newProfile.bloodType || '';
        formData.value.diagnoses = JSON.parse(JSON.stringify(newProfile.diagnoses || []));
        formData.value.allergies = JSON.parse(JSON.stringify(newProfile.allergies || []));
      }
    },
    { deep: true, immediate: true }
);

// Load profile when modal opens
watch(
    () => props.isOpen,
    async (newIsOpen) => {
      if (newIsOpen) {
        await fetchProfile();
      }
    }
);

// --- Diagnosis Handlers ---
const addDiagnosis = () => {
  formData.value.diagnoses.push({
    name: '',
    diagnosedAt: null // Дата теперь по умолчанию пустая (null)
  });
};

const removeDiagnosis = (index) => {
  formData.value.diagnoses.splice(index, 1);
};

// --- Allergy Handlers ---
const addAllergy = () => {
  formData.value.allergies.push({
    allergen: '',
    reaction: ''
  });
};

const removeAllergy = (index) => {
  formData.value.allergies.splice(index, 1);
};

async function handleSave() {
  try {
    await updateProfile({
      heightCm: formData.value.heightCm,
      weightKg: formData.value.weightKg,
      bloodType: formData.value.bloodType,
      // Очищаем и приводим к корректному виду
      diagnoses: formData.value.diagnoses
          .filter(d => d.name.trim() !== '')
          .map(d => ({
            name: d.name.trim(),
            diagnosedAt: d.diagnosedAt || null // Если пусто, отправляем null
          })),
      allergies: formData.value.allergies
          .filter(a => a.allergen.trim() !== '')
          .map(a => ({
            allergen: a.allergen.trim(),
            reaction: a.reaction.trim() || null
          }))
    });

    closeModal();
  } catch (err) {
    // Error is already set in useProfile
  }
}

function closeModal() {
  emit('close');
}
</script>

<style scoped>
/* ... (Твои старые стили остаются без изменений, добавляем только новые ниже) ... */

/* Overlay, Modal Container, Header, Content, Sections, Info Items, Form Fields - оставляем как было */

.profile-modal-overlay {
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
  padding: 20px;
}

.profile-modal {
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.profile-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 28px;
  border-bottom: 1px solid #e8ecf0;
  flex-shrink: 0;
}

.profile-modal-title {
  font-size: 20px;
  font-weight: 700;
  color: #111;
  letter-spacing: -0.3px;
  margin: 0;
}

.profile-modal-close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8a93a2;
  transition: color 0.15s;
  border-radius: 6px;
}

.profile-modal-close:hover {
  color: #111;
  background: #f0f4f8;
}

.profile-modal-content {
  flex: 1;
  padding: 24px 28px;
  overflow-y: auto;
}

.profile-section {
  margin-bottom: 32px;
}

.profile-section:last-child {
  margin-bottom: 0;
}

.profile-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: #111;
  margin: 0 0 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e8ecf0;
}

.profile-info-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.profile-info-item {
  display: flex;
  gap: 12px;
  font-size: 14px;
}

.profile-label {
  min-width: 100px;
  color: #6b7280;
  font-weight: 500;
}

.profile-value {
  color: #111;
}

.profile-field {
  margin-bottom: 16px;
}

.profile-field:last-child {
  margin-bottom: 0;
}

.profile-field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #333;
  margin-bottom: 6px;
}

.profile-field-input {
  width: 100%;
  height: 40px;
  border: 1.5px solid #dde2e8;
  border-radius: 8px;
  padding: 0 12px;
  font-size: 14px;
  font-family: 'Nunito', sans-serif;
  color: #111;
  background: #fff;
  outline: none;
  transition: border-color 0.18s, box-shadow 0.18s;
}

.profile-field-input:focus {
  border-color: #0079e0;
  box-shadow: 0 0 0 3px rgba(0, 121, 224, 0.12);
}

.profile-field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.profile-field-full {
  grid-column: 1 / -1;
}

/* --- NEW STYLES FOR EDITABLE BADGES --- */
.profile-badges-container {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.profile-badge.editable {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  transition: border-color 0.2s;
}

.profile-badge.editable:hover {
  border-color: #cbd5e1;
}

.profile-badge.editable.allergy {
  background: #fef2f2;
  border-color: #fecaca;
}

.badge-input {
  border: none;
  background: transparent;
  font-size: 13px;
  color: #111;
  outline: none;
  min-width: 80px;
  font-family: 'Nunito', sans-serif;
}

.badge-input::placeholder {
  color: #94a3b8;
}

.badge-input.date-input {
  min-width: 110px;
  color: #64748b;
}

.badge-remove {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  padding: 0 4px;
  border-radius: 4px;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.badge-remove:hover {
  background: #fee2e2;
  color: #dc2626;
}

.profile-btn-add {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1.5px dashed #cbd5e1;
  color: #64748b;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  font-family: 'Nunito', sans-serif;
}

.profile-btn-add:hover {
  border-color: #0079e0;
  color: #0079e0;
  background: #f0f7ff;
}

/* Messages & Actions (оставляем как было) */
.profile-error {
  color: #dc2626;
  font-size: 13px;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #fee2e2;
  border-radius: 8px;
  border: 1px solid #fecaca;
}

.profile-success {
  color: #16a34a;
  font-size: 13px;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #dcfce7;
  border-radius: 8px;
  border: 1px solid #bbf7d0;
}

.profile-modal-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
  border-top: 1px solid #e8ecf0;
  padding-top: 24px;
}

.profile-btn {
  flex: 1;
  height: 44px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  font-family: 'Nunito', sans-serif;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.profile-btn-primary {
  background: #1a65db;
  color: white;
}

.profile-btn-primary:hover:not(:disabled) {
  background: #1558c4;
  transform: translateY(-1px);
}

.profile-btn-secondary {
  background: #f0f4f8;
  color: #333;
  border: 1.5px solid #e0e6f0;
}

.profile-btn-secondary:hover:not(:disabled) {
  background: #e8ecf2;
}

.profile-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.profile-field-hint {
  font-size: 12px;
  font-weight: 400;
  color: #94a3b8;
  margin-left: 4px;
}

/* Responsive */
@media (max-width: 900px) {
  .profile-field-grid {
    grid-template-columns: 1fr;
  }
  .profile-modal-overlay { padding: 16px; }
  .profile-modal { max-height: 95vh; border-radius: 12px; }
  .profile-modal-header, .profile-modal-content { padding: 20px; }
}

@media (max-width: 600px) {
  .profile-modal-overlay { padding: 12px; }
  .profile-modal { border-radius: 12px; max-width: 100%; }
  .profile-modal-header, .profile-modal-content { padding: 16px; }
  .profile-badge.editable { flex-direction: column; align-items: stretch; gap: 4px; }
  .badge-input { width: 100%; }
  .badge-remove { align-self: flex-end; margin-top: -20px; margin-right: -4px; }
}
</style>