import { computed, ref } from 'vue';
import { login, logout, me } from '@/entities/auth/api/authApi';

const user = ref(null);
const loading = ref(false);
const initialized = ref(false);
const sessionError = ref('');

export function useSession() {
  const isAuthenticated = computed(() => Boolean(user.value));

  async function initSession() {
    if (initialized.value) {
      return;
    }

    loading.value = true;
    sessionError.value = '';
    try {
      user.value = await me();
    } catch {
      user.value = null;
    } finally {
      loading.value = false;
      initialized.value = true;
    }
  }

  async function signIn(email, password) {
    loading.value = true;
    sessionError.value = '';
    try {
      user.value = await login({ email, password });
      return true;
    } catch (error) {
      sessionError.value = error.message || 'Login failed';
      user.value = null;
      return false;
    } finally {
      loading.value = false;
    }
  }

  async function signOut() {
    loading.value = true;
    sessionError.value = '';
    try {
      await logout();
      user.value = null;
    } catch (error) {
      sessionError.value = error.message || 'Logout failed';
    } finally {
      loading.value = false;
    }
  }

  return {
    user,
    loading,
    sessionError,
    isAuthenticated,
    initSession,
    signIn,
    signOut,
  };
}
