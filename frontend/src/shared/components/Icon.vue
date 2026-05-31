<script setup>
import { computed } from 'vue';
import navHome from './healthmate-icons/healthmate-icons/nav-glavnaya.svg';
import navAi from './healthmate-icons/healthmate-icons/ai-assistant.svg';
import navMeds from './healthmate-icons/healthmate-icons/med-preparat.svg';
import navStats from './healthmate-icons/healthmate-icons/nav-statistika.svg';
import navProfile from './healthmate-icons/healthmate-icons/nav-profil.svg';
import brandLogo from './healthmate-icons/healthmate-icons/logo.svg';
import iconClose from './healthmate-icons/healthmate-icons/ui-zakryt.svg';
import iconMenu from './healthmate-icons/healthmate-icons/ui-menu.svg';
import iconAiAssistant from './healthmate-icons/healthmate-icons/ai-assistant.svg';
import iconSecurity from './healthmate-icons/healthmate-icons/prof-bezopasnost.svg';
import iconReminder from './healthmate-icons/healthmate-icons/med-napominanie.svg';
import iconEdit from './healthmate-icons/healthmate-icons/action-redaktirovat.svg';
import iconPersonal from './healthmate-icons/healthmate-icons/prof-lichnye.svg';
import iconHelp from './healthmate-icons/healthmate-icons/prof-pomosh.svg';
import iconNotifChat from './healthmate-icons/healthmate-icons/notif-chat.svg';
import iconDelete from './healthmate-icons/healthmate-icons/action-udalit.svg';
import iconSendAi from './healthmate-icons/healthmate-icons/ai-otpravit.svg';
import iconStateActive from './healthmate-icons/healthmate-icons/state-aktivno.svg';
import iconStatePaused from './healthmate-icons/healthmate-icons/state-priostanovleno.svg';
import iconStateCanceled from './healthmate-icons/healthmate-icons/state-otmeneno.svg';
import iconStateWaiting from './healthmate-icons/healthmate-icons/state-ozhidanie.svg';
import iconStateDone from './healthmate-icons/healthmate-icons/state-vypolneno.svg';

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  size: {
    type: Number,
    default: 24,
  },
  className: {
    type: String,
    default: '',
  },
});

const imageIcons = {
  home: navHome,
  ai: navAi,
  pills: navMeds,
  chart: navStats,
  user: navProfile,
  brandPlus: brandLogo,
  regAi: iconAiAssistant,
  regSecurity: iconSecurity,
  regReminder: iconReminder,
  profilePersonal: iconPersonal,
  profileSecurity: iconSecurity,
  profileHelp: iconHelp,
  edit: iconEdit,
  chatAdd: iconNotifChat,
  chatDelete: iconDelete,
  chatSend: iconSendAi,
  medStateActive: iconStateActive,
  medStatePaused: iconStatePaused,
  medStateCanceled: iconStateCanceled,
  medStateWaiting: iconStateWaiting,
  medStateDone: iconStateDone,
  medDelete: iconDelete,
  closeMenu: iconClose,
  close: iconClose,
  menu: iconMenu,
};

const svgIcons = {
  bell: {
    viewBox: '0 0 24 24',
    content: '<path d="M18 8C18 6.34 16.66 5 15 5c-1.1 0-2.04.71-2.41 1.67C11.84 5.65 10.5 5 9 5 6.24 5 4 7.24 4 10v5h14v-7z" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/><path d="M8 21h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  },
  logout: {
    viewBox: '0 0 24 24',
    content: '<path d="M8 12h8m0 0l-3-3m3 3l-3 3M4 6h12a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V8a2 2 0 012-2z" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  plus: {
    viewBox: '0 0 24 24',
    content: '<path d="M12 5v14m-7-7h14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  },
  alert: {
    viewBox: '0 0 24 24',
    content: '<path d="M12 2L2 20h20L12 2z" stroke="currentColor" stroke-width="2" fill="none" stroke-linejoin="round"/><line x1="12" y1="9" x2="12" y2="13" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="17" r="1" fill="currentColor"/>',
  },
  check: {
    viewBox: '0 0 24 24',
    content: '<path d="M4 12l5 5 11-11" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
  },
  close: {
    viewBox: '0 0 24 24',
    content: '<path d="M5 5l14 14M19 5L5 19" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
  },
  eye: {
    viewBox: '0 0 24 24',
    content: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2" fill="none"/>',
  },
  eyeOff: {
    viewBox: '0 0 24 24',
    content: '<path d="M3 3l18 18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M10.58 10.58A3 3 0 0012 15a3 3 0 003-3 3 3 0 00-.42-1.58" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M4.5 12s3.5-7 7.5-7c1.47 0 2.87.52 4.06 1.31" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/><path d="M9.88 4.6A9.7 9.7 0 0112 4c6.5 0 10 8 10 8a18.9 18.9 0 01-3.31 4.6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>',
  },
};

const iconSrc = computed(() => imageIcons[props.name] || null);
const iconDefinition = computed(() => svgIcons[props.name] || svgIcons.plus);
</script>

<template>
  <img
    v-if="iconSrc"
    :src="iconSrc"
    :width="size"
    :height="size"
    :class="className"
    :alt="`${name} icon`"
    v-bind="$attrs"
  />
  <svg
    v-else
    :width="size"
    :height="size"
    :class="className"
    :viewBox="iconDefinition.viewBox"
    xmlns="http://www.w3.org/2000/svg"
    v-bind="$attrs"
  >
    <g v-html="iconDefinition.content" />
  </svg>
</template>

