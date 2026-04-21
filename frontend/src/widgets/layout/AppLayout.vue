<script setup>
import { ref } from 'vue';
import Icon from '@/shared/components/Icon.vue';

const menuOpen = ref(false);

const props = defineProps({
  activeView: {
    type: String,
    required: true,
  },
  userName: {
    type: String,
    default: 'User',
  },
});

const emit = defineEmits(['navigate', 'logout']);

const navItems = [
  { id: 'home', label: 'Главная', icon: 'home' },
  { id: 'ai', label: 'AI-Консультация', icon: 'ai' },
  { id: 'meds', label: 'Лекарства', icon: 'pills' },
  { id: 'stats', label: 'Статистика', icon: 'chart' },
];

function handleNavigate(id) {
  emit('navigate', id);
  menuOpen.value = false;
}

function handleLogout() {
  emit('logout');
  menuOpen.value = false;
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-icon">
          <Icon name="brandPlus" size="34" />
        </span>
        <span>HealthMate</span>
      </div>

      <nav class="nav-list">
        <button
          v-for="item in navItems"
          :key="item.id"
          class="nav-item"
          :class="{ active: item.id === props.activeView }"
          type="button"
          @click="handleNavigate(item.id)"
        >
          <Icon :name="item.icon" size="20" class="nav-icon-svg" />
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <button class="logout-btn" type="button" @click="handleLogout">Выйти</button>
    </aside>

    <!-- Mobile Menu Overlay -->
    <div v-if="menuOpen" class="mobile-menu-overlay" @click="menuOpen = false" />

    <!-- Mobile Menu -->
    <div :class="['mobile-menu', { open: menuOpen }]">
      <div class="mobile-menu-header">
        <span class="brand-icon-mobile">
          <Icon name="brandPlus" size="30" />
        </span>
        <span>HealthMate</span>
      </div>

      <nav class="mobile-nav-list">
        <button
          v-for="item in navItems"
          :key="item.id"
          class="mobile-nav-item"
          :class="{ active: item.id === props.activeView }"
          type="button"
          @click="handleNavigate(item.id)"
        >
          <Icon :name="item.icon" size="24" class="mobile-nav-icon" />
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <button class="mobile-logout-btn" type="button" @click="handleLogout">Выйти</button>
    </div>

    <section class="content-wrap">
      <header class="topbar">
        <button class="mobile-menu-btn" type="button" @click="menuOpen = true">
          <Icon name="menu" size="20" />
        </button>
        <h1 class="top-title">{{ navItems.find((item) => item.id === props.activeView)?.label }}</h1>
        <div class="top-user">
          <Icon name="user" size="20" class="avatar-icon" />
          <span>{{ props.userName }}</span>
        </div>
      </header>

      <main class="content">
        <slot />
      </main>
    </section>
  </div>
</template>
