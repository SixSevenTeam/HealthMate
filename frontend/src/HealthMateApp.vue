<script setup>
import { computed, onMounted, ref } from 'vue';
import { useSession } from '@/features/session/useSession';
import Icon from '@/shared/components/Icon.vue';
import AppLayout from '@/widgets/layout/AppLayout.vue';
import HomeView from '@/views/healthmate.vue';
import MedicationsView from '@/views/healthmate-medicines.vue';
import AiConsultView from '@/views/healthmate-ai-consult.vue';
import StatisticsView from '@/views/healthmate-statistics.vue';
import RegistrationView from '@/views/healthmate-registration.vue';

const currentView = ref('home');
const authMode = ref('register');
const email = ref('');
const password = ref('');

const { user, loading, sessionError, isAuthenticated, initSession, signIn, signOut } = useSession();

const currentViewComponent = computed(() => {
	if (currentView.value === 'meds') return MedicationsView;
	if (currentView.value === 'ai') return AiConsultView;
	if (currentView.value === 'stats') return StatisticsView;
	return HomeView;
});

const userName = computed(() => {
	if (!user.value) return 'User';
	const firstName = user.value.firstName || '';
	const lastName = user.value.lastName || '';
	return `${firstName} ${lastName}`.trim() || user.value.email || 'User';
});

async function onLogin() {
	await signIn(email.value, password.value);
}

function switchToRegistration() {
	authMode.value = 'register';
}

function switchToLogin() {
	authMode.value = 'login';
}

function onRegistrationSuccess(credentials) {
	// Auto-fill login form with registered credentials
	email.value = credentials.email;
	password.value = credentials.password;
	// Switch to login
	authMode.value = 'login';
}

onMounted(initSession);
</script>

<template>
	<div class="app-root">
		<div v-if="loading && !isAuthenticated" class="center-card">
			<h2 class="card-title">Проверка сессии...</h2>
		</div>

		<div v-else-if="!isAuthenticated" class="auth-wrap">
			<div v-if="authMode === 'login'" class="auth-page">
				<div class="auth-left">
					<div class="auth-logo">
						<div class="auth-logo-icon">
							<Icon name="brandPlus" size="34" className="auth-logo-mark" />
						</div>
						<span class="auth-logo-text">Health<span>Mate</span></span>
					</div>

					<h1 class="auth-hero-title">Добро пожаловать обратно в HealthMate</h1>
					<p class="auth-hero-sub">
						Войдите в аккаунт, чтобы продолжить контроль приёма лекарств, напоминаний и консультаций.
					</p>

					<div class="auth-features">
						<div class="auth-feature">
							<div class="auth-feature-icon auth-feature-icon-security">
								<Icon name="regSecurity" size="24" />
							</div>
							<div class="auth-feature-text">
								<div class="auth-feature-title">Безопасность данных</div>
								<div class="auth-feature-sub">Ваши данные защищены и конфиденциальны</div>
							</div>
						</div>
						<div class="auth-feature">
							<div class="auth-feature-icon auth-feature-icon-reminder">
								<Icon name="regReminder" size="24" />
							</div>
							<div class="auth-feature-text">
								<div class="auth-feature-title">Умные напоминания</div>
								<div class="auth-feature-sub">Не пропускайте важные приёмы лекарств</div>
							</div>
						</div>
						<div class="auth-feature">
							<div class="auth-feature-icon auth-feature-icon-ai">
								<Icon name="regAi" size="24" />
							</div>
							<div class="auth-feature-text">
								<div class="auth-feature-title">AI-консультант</div>
								<div class="auth-feature-sub">Получайте подсказки о здоровье и лекарствах</div>
							</div>
						</div>
					</div>
				</div>

				<div class="auth-right">
					<form class="auth-card" @submit.prevent="onLogin">
						<h1 class="auth-title">Вход в аккаунт</h1>
						<p class="muted">Авторизация через cookie-only flow</p>

						<input v-model="email" class="input" type="email" placeholder="Email" required />
						<input v-model="password" class="input" type="password" placeholder="Password" required />

						<p v-if="sessionError" class="error-text">{{ sessionError }}</p>

						<button class="btn auth-btn" type="submit" :disabled="loading">
							{{ loading ? 'Вход...' : 'Войти' }}
						</button>

						<p class="auth-switch">
							Нет аккаунта?
							<a href="#" @click.prevent="switchToRegistration">Зарегистрироваться</a>
						</p>
					</form>
				</div>
			</div>

			<!-- Registration Form -->
			<RegistrationView
				v-else-if="authMode === 'register'"
				@switchToLogin="switchToLogin"
				@success="onRegistrationSuccess"
			/>
		</div>

		<AppLayout
			v-else
			:active-view="currentView"
			:user-name="userName"
			@navigate="currentView = $event"
			@logout="signOut"
		>
			<component :is="currentViewComponent" />
		</AppLayout>
	</div>
</template>
