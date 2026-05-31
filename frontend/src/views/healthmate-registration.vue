<template>
  <div class="reg-page">
    <!-- Left Panel (Hero) -->
    <div class="reg-left">
      <div class="reg-logo">
        <div class="reg-logo-icon">
          <Icon name="brandPlus" size="34" className="reg-logo-mark" />
        </div>
        <span class="reg-logo-text">Health<span>Mate</span></span>
      </div>

      <h1 class="reg-hero-title">Забота о вашем здоровье — наша миссия</h1>
      <p class="reg-hero-sub">
        HealthMate помогает вам следить за приёмом лекарств, получать напоминания и консультации на основе искусственного интеллекта.
      </p>

      <div class="reg-features">
        <div class="reg-feature">
          <div class="reg-feature-icon reg-feature-icon-security">
            <Icon name="regSecurity" size="24" />
          </div>
          <div class="reg-feature-text">
            <div class="reg-feature-title">Безопасность данных</div>
            <div class="reg-feature-sub">Ваши данные защищены и конфиденциальны</div>
          </div>
        </div>
        <div class="reg-feature">
          <div class="reg-feature-icon reg-feature-icon-reminder">
            <Icon name="regReminder" size="24" />
          </div>
          <div class="reg-feature-text">
            <div class="reg-feature-title">Умные напоминания</div>
            <div class="reg-feature-sub">Никогда не пропускайте приём лекарств</div>
          </div>
        </div>
        <div class="reg-feature">
          <div class="reg-feature-icon reg-feature-icon-ai">
            <Icon name="regAi" size="24" />
          </div>
          <div class="reg-feature-text">
            <div class="reg-feature-title">AI-консультант</div>
            <div class="reg-feature-sub">Получайте ответы на вопросы о здоровье</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right Panel (Form) -->
    <div class="reg-right">
      <div class="reg-form-box">
        <h2 class="reg-form-title">Регистрация</h2>
        <p class="reg-form-sub">Создайте аккаунт, чтобы начать пользоваться HealthMate</p>

        <form @submit.prevent="handleRegister">
          <!-- First Name -->
          <div class="reg-field">
            <label class="reg-field-label">Имя *</label>
            <input
              v-model="form.firstName"
              type="text"
              class="reg-field-input"
              placeholder="Ваше имя"
              required
            />
          </div>

          <!-- Last Name -->
          <div class="reg-field">
            <label class="reg-field-label">Фамилия *</label>
            <input
              v-model="form.lastName"
              type="text"
              class="reg-field-input"
              placeholder="Ваша фамилия"
              required
            />
          </div>

          <!-- Email -->
          <div class="reg-field">
            <label class="reg-field-label">Email *</label>
            <input
              v-model="form.email"
              type="email"
              class="reg-field-input"
              placeholder="your@email.com"
              required
            />
          </div>

          <!-- Birth Date -->
          <div class="reg-field">
            <label class="reg-field-label">Дата рождения *</label>
            <input
              v-model="form.birthDate"
              type="date"
              class="reg-field-input"
              required
            />
          </div>

          <!-- Height (optional) -->
          <div class="reg-field">
            <label class="reg-field-label">Рост (см)</label>
            <input
              v-model.number="form.heightCm"
              type="number"
              class="reg-field-input"
              placeholder="180"
            />
          </div>

          <!-- Weight (optional) -->
          <div class="reg-field">
            <label class="reg-field-label">Вес (кг)</label>
            <input
              v-model.number="form.weightKg"
              type="number"
              class="reg-field-input"
              placeholder="75"
              step="0.1"
            />
          </div>

          <!-- Blood Type (optional) -->
          <div class="reg-field">
            <label class="reg-field-label">Группа крови</label>
            <select v-model="form.bloodType" class="reg-field-input">
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

          <!-- Password -->
          <div class="reg-field">
            <label class="reg-field-label">Пароль *</label>
            <div class="reg-input-wrap">
              <input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                class="reg-field-input"
                placeholder="Придумайте пароль"
                required
              />
              <button
                type="button"
                class="reg-eye-btn"
                @click="showPassword = !showPassword"
              >
                <Icon :name="showPassword ? 'eyeOff' : 'eye'" :size="18" />
              </button>
            </div>
          </div>

          <!-- Confirm Password -->
          <div class="reg-field">
            <label class="reg-field-label">Подтвердите пароль *</label>
            <div class="reg-input-wrap">
              <input
                v-model="form.passwordConfirm"
                :type="showPasswordConfirm ? 'text' : 'password'"
                class="reg-field-input"
                placeholder="Повторите пароль"
                required
              />
              <button
                type="button"
                class="reg-eye-btn"
                @click="showPasswordConfirm = !showPasswordConfirm"
              >
                <Icon :name="showPasswordConfirm ? 'eyeOff' : 'eye'" :size="18" />
              </button>
            </div>
          </div>

          <!-- Agreement -->
          <div class="reg-checkbox-row">
            <input
              v-model="agreed"
              type="checkbox"
              class="reg-checkbox"
              required
            />
            <label class="reg-checkbox-label">
              Я принимаю условия <a href="#">Пользовательского соглашения</a> и
              <a href="#">Политики конфиденциальности</a>
            </label>
          </div>

          <!-- Error Message -->
          <div v-if="error" class="reg-error">{{ error }}</div>

          <!-- Submit Button -->
          <button type="submit" class="reg-submit-btn" :disabled="loading">
            {{ loading ? 'Загрузка...' : 'Зарегистрироваться' }}
          </button>
        </form>

        <!-- Login Link -->
        <div class="reg-login-row">
          Уже есть аккаунт?
          <a href="#" @click.prevent="$emit('switchToLogin')">Войти</a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { httpRequest } from '@/shared/api/httpClient';
import Icon from '@/shared/components/Icon.vue';

const emit = defineEmits(['switchToLogin', 'success']);

const form = ref({
  firstName: '',
  lastName: '',
  email: '',
  birthDate: '',
  heightCm: null,
  weightKg: null,
  bloodType: '',
  password: '',
  passwordConfirm: '',
});

const showPassword = ref(false);
const showPasswordConfirm = ref(false);
const agreed = ref(false);
const loading = ref(false);
const error = ref('');

function resetForm() {
  form.value = {
    firstName: '',
    lastName: '',
    email: '',
    birthDate: '',
    heightCm: null,
    weightKg: null,
    bloodType: '',
    password: '',
    passwordConfirm: '',
  };
  showPassword.value = false;
  showPasswordConfirm.value = false;
  agreed.value = false;
  error.value = '';
}

onMounted(resetForm);

async function handleRegister() {
  error.value = '';

  // Validation
  if (!form.value.firstName.trim()) {
    error.value = 'Пожалуйста, введите имя';
    return;
  }
  if (!form.value.lastName.trim()) {
    error.value = 'Пожалуйста, введите фамилию';
    return;
  }
  if (!form.value.email.trim()) {
    error.value = 'Пожалуйста, введите email';
    return;
  }
  if (!form.value.birthDate) {
    error.value = 'Пожалуйста, выберите дату рождения';
    return;
  }
  if (!form.value.password) {
    error.value = 'Пожалуйста, введите пароль';
    return;
  }
  if (form.value.password !== form.value.passwordConfirm) {
    error.value = 'Пароли не совпадают';
    return;
  }
  if (!agreed.value) {
    error.value = 'Пожалуйста, примите условия соглашения';
    return;
  }

  loading.value = true;
  try {
    const payload = {
      firstName: form.value.firstName,
      lastName: form.value.lastName,
      email: form.value.email,
      birthDate: form.value.birthDate,
      password: form.value.password,
    };

    // Add optional fields if provided
    if (form.value.heightCm) payload.heightCm = form.value.heightCm;
    if (form.value.weightKg) payload.weightKg = form.value.weightKg;
    if (form.value.bloodType) payload.bloodType = form.value.bloodType;

    await httpRequest('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    emit('success', {
      email: form.value.email,
      password: form.value.password,
    });
  } catch (err) {
    error.value = err.message || 'Ошибка при регистрации';
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
/* Registration Page */
.reg-page {
  max-width: 1400px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  min-height: 100vh;
}

/* Left Panel */
.reg-left {
  background: linear-gradient(160deg, #f0faf8 0%, #e4f4f0 40%, #ddeef8 100%);
  padding: 36px 52px 52px;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.reg-left::before {
  content: '';
  position: absolute;
  right: -60px;
  bottom: 60px;
  width: 340px;
  height: 260px;
  background: radial-gradient(ellipse, rgba(0, 180, 150, 0.1) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.reg-left::after {
  content: '';
  position: absolute;
  right: 30px;
  bottom: -40px;
  width: 260px;
  height: 200px;
  background: radial-gradient(ellipse, rgba(0, 120, 220, 0.08) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

/* Logo */
.reg-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 64px;
}

.reg-logo-icon {
  width: 40px;
  height: 40px;
  background: linear-gradient(135deg, #00c9a7 0%, #0091ff 100%);
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 14px rgba(0, 180, 150, 0.3);
  overflow: hidden;
}

.reg-logo-mark {
  width: 100%;
  height: 100%;
}

.reg-logo-text {
  font-size: 19px;
  font-weight: 700;
  color: #111;
  letter-spacing: -0.3px;
}

.reg-logo-text span {
  color: #0091ff;
}

/* Hero Text */
.reg-hero-title {
  font-size: 38px;
  font-weight: 800;
  color: #111;
  line-height: 1.15;
  letter-spacing: -0.8px;
  margin-bottom: 20px;
  max-width: 340px;
}

.reg-hero-sub {
  font-size: 15px;
  color: #607080;
  line-height: 1.6;
  max-width: 360px;
  margin-bottom: 52px;
  font-weight: 400;
}

/* Features */
.reg-features {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.reg-feature {
  display: flex;
  align-items: flex-start;
  gap: 18px;
}

.reg-feature-icon {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.reg-feature-icon-security {
  background: #fff;
  color: #0f8f5d;
  border: 1px solid #e6edf5;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
}

.reg-feature-icon-reminder {
  background: #fff;
  color: #1b6bd1;
  border: 1px solid #e6edf5;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
}

.reg-feature-icon-ai {
  background: #fff;
  color: #6f42c1;
  border: 1px solid #e6edf5;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
}

.reg-feature-icon :deep(img),
.reg-feature-icon :deep(svg) {
  width: 24px;
  height: 24px;
}

.reg-feature-title {
  font-size: 15.5px;
  font-weight: 700;
  color: #111;
  margin-bottom: 4px;
}

.reg-feature-sub {
  font-size: 13.5px;
  color: #7a8ea0;
  line-height: 1.4;
  font-weight: 400;
}

/* Right Panel */
.reg-right {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 64px;
}

.reg-form-box {
  width: 100%;
  max-width: 460px;
}

.reg-form-title {
  font-size: 26px;
  font-weight: 700;
  color: #111;
  text-align: center;
  letter-spacing: -0.4px;
  margin-bottom: 8px;
}

.reg-form-sub {
  font-size: 14px;
  color: #8a96a3;
  text-align: center;
  margin-bottom: 32px;
  font-weight: 400;
}

/* Form Fields */
.reg-field {
  margin-bottom: 18px;
}

.reg-field-label {
  display: block;
  font-size: 13.5px;
  font-weight: 500;
  color: #333;
  margin-bottom: 7px;
}

.reg-input-wrap {
  position: relative;
}

.reg-field-input {
  width: 100%;
  height: 48px;
  border: 1.5px solid #dde2e8;
  border-radius: 10px;
  padding: 0 44px 0 14px;
  font-size: 14.5px;
  font-family: 'Nunito', sans-serif;
  color: #111;
  background: #fff;
  outline: none;
  transition: border-color 0.18s, box-shadow 0.18s;
}

.reg-field-input::placeholder {
  color: #aab4be;
}

.reg-field-input:focus {
  border-color: #0079e0;
  box-shadow: 0 0 0 3px rgba(0, 121, 224, 0.12);
}

.reg-eye-btn {
  position: absolute;
  right: 13px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  color: #aab4be;
  padding: 4px;
  display: flex;
  align-items: center;
  transition: color 0.15s;
  font-size: 16px;
}

.reg-eye-btn :deep(img),
.reg-eye-btn :deep(svg) {
  width: 18px;
  height: 18px;
  display: block;
}

.reg-eye-btn:hover {
  color: #555;
}

/* Checkbox */
.reg-checkbox-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 22px;
  margin-top: 4px;
}

.reg-checkbox {
  width: 18px;
  height: 18px;
  cursor: pointer;
  flex-shrink: 0;
  margin-top: 1px;
}

.reg-checkbox-label {
  font-size: 13.5px;
  color: #4a5568;
  line-height: 1.5;
  font-weight: 400;
}

.reg-checkbox-label a {
  color: #0079e0;
  text-decoration: none;
  font-weight: 500;
}

.reg-checkbox-label a:hover {
  text-decoration: underline;
}

/* Error */
.reg-error {
  color: #dc2626;
  font-size: 13.5px;
  margin-bottom: 16px;
  padding: 10px 14px;
  background: #fee2e2;
  border-radius: 8px;
  border: 1px solid #fecaca;
}

/* Submit Button */
.reg-submit-btn {
  width: 100%;
  height: 50px;
  background: #1a65db;
  color: white;
  border: none;
  border-radius: 10px;
  font-size: 15.5px;
  font-weight: 600;
  font-family: 'Nunito', sans-serif;
  cursor: pointer;
  letter-spacing: 0.1px;
  box-shadow: 0 4px 16px rgba(26, 101, 219, 0.28);
  transition: background 0.18s, transform 0.12s, box-shadow 0.18s;
  margin-bottom: 22px;
}

.reg-submit-btn:hover:not(:disabled) {
  background: #1558c4;
  box-shadow: 0 6px 20px rgba(26, 101, 219, 0.35);
  transform: translateY(-1px);
}

.reg-submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Login Link */
.reg-login-row {
  text-align: center;
  font-size: 14px;
  color: #7a8696;
}

.reg-login-row a {
  color: #0079e0;
  font-weight: 600;
  text-decoration: none;
}

.reg-login-row a:hover {
  text-decoration: underline;
}

/* Responsive - Tablet & Mobile */
@media (max-width: 1100px) {
  .reg-page {
    grid-template-columns: 1fr;
  }

  .reg-left {
    padding: 32px 40px 40px;
    display: none; /* Hide on tablet */
  }

  .reg-right {
    padding: 32px 40px;
  }

  .reg-form-box {
    max-width: 100%;
  }
}

@media (max-width: 900px) {
  .reg-page {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .reg-left {
    display: none;
  }

  .reg-right {
    padding: 24px 20px;
    min-height: 100vh;
  }

  .reg-form-box {
    max-width: 100%;
  }

  .reg-form-title {
    font-size: 22px;
  }

  .reg-field-input {
    height: 44px;
    padding: 0 40px 0 12px;
    font-size: 14px;
  }
}

@media (max-width: 600px) {
  .reg-right {
    padding: 16px 16px;
  }

  .reg-form-title {
    font-size: 20px;
  }

  .reg-form-sub {
    font-size: 12px;
  }

  .reg-field-input {
    height: 42px;
    font-size: 13px;
  }

  .reg-field-label {
    font-size: 12px;
  }

  .reg-submit-btn {
    height: 44px;
    font-size: 14px;
  }
}
</style>
