<script setup>
import { computed, onMounted, ref } from 'vue';
import { useSession } from '@/features/session/useSession';
import AppLayout from '@/widgets/layout/AppLayout.vue';
import HomeView from '@/views/healthmate.vue';
import MedicationsView from '@/views/healthmate-medicines.vue';
import AiConsultView from '@/views/healthmate-ai-consult.vue';
import StatisticsView from '@/views/healthmate-statistics.vue';

const currentView = ref('home');
const email = ref('demo1@healthmate.local');
const password = ref('Demo331Pass!');

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

onMounted(initSession);
</script>

<template>
	<div class="app-root">
		<div v-if="loading && !isAuthenticated" class="center-card">
			<h2 class="card-title">Проверка сессии...</h2>
		</div>

		<div v-else-if="!isAuthenticated" class="auth-wrap">
			<form class="auth-card" @submit.prevent="onLogin">
				<h1 class="auth-title">HealthMate Login</h1>
				<p class="muted">Авторизация через cookie-only flow</p>

				<input v-model="email" class="input" type="email" placeholder="Email" required />
				<input v-model="password" class="input" type="password" placeholder="Password" required />

				<p v-if="sessionError" class="error-text">{{ sessionError }}</p>

				<button class="btn auth-btn" type="submit" :disabled="loading">
					{{ loading ? 'Вход...' : 'Войти' }}
				</button>
			</form>
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
