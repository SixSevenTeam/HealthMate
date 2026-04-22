<script setup>
import { onMounted, ref, watch } from 'vue';
import {
  createConversation,
  getConversationMessages,
  getConversations,
  sendMessage,
} from '@/entities/chat/api/chatApi';

const conversations = ref([]);
const selectedConversationId = ref('');
const messages = ref([]);
const prompt = ref('');
const loading = ref(false);
const sending = ref(false);
const errorMessage = ref('');

async function loadConversations() {
  loading.value = true;
  errorMessage.value = '';
  try {
    const page = await getConversations(0, 20);
    conversations.value = page.content || [];

    if (!selectedConversationId.value && conversations.value.length > 0) {
      selectedConversationId.value = conversations.value[0].id;
    }

    if (!selectedConversationId.value) {
      const created = await createConversation('Новая консультация');
      conversations.value.unshift(created);
      selectedConversationId.value = created.id;
    }
  } catch (error) {
    errorMessage.value = error.message || 'Не удалось загрузить диалоги';
  } finally {
    loading.value = false;
  }
}

async function loadMessages() {
  if (!selectedConversationId.value) {
    return;
  }

  try {
    messages.value = await getConversationMessages(selectedConversationId.value);
  } catch (error) {
    errorMessage.value = error.message || 'Не удалось получить сообщения';
  }
}

async function submitMessage() {
  if (!prompt.value.trim() || !selectedConversationId.value) {
    return;
  }

  sending.value = true;
  errorMessage.value = '';
  try {
    const result = await sendMessage(selectedConversationId.value, prompt.value.trim());
    prompt.value = '';
    messages.value.push(result.userMessage, result.assistantMessage);
  } catch (error) {
    errorMessage.value = error.message || 'Ошибка отправки';
  } finally {
    sending.value = false;
  }
}

watch(selectedConversationId, loadMessages);
onMounted(loadConversations);
</script>

<template>
  <section class="chat-layout">
    <aside class="card chat-aside">
      <div class="row-between">
        <h2 class="card-title">Диалоги</h2>
      </div>
      <p v-if="loading" class="muted">Загрузка...</p>
      <div class="stack-sm" v-else>
        <button
          v-for="conversation in conversations"
          :key="conversation.id"
          class="conv-btn"
          :class="{ active: selectedConversationId === conversation.id }"
          type="button"
          @click="selectedConversationId = conversation.id"
        >
          {{ conversation.title || 'Без названия' }}
        </button>
      </div>
    </aside>

    <article class="card chat-main">
      <h2 class="card-title">AI-Консультация</h2>
      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

      <div class="message-list">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message"
          :class="msg.role === 'user' ? 'message-user' : 'message-assistant'"
        >
          <p>{{ msg.content }}</p>
          <span class="message-time">{{ msg.role === 'user' ? 'Вы' : 'AI' }}</span>
        </div>
      </div>

      <div class="chat-input-row">
        <input
          v-model="prompt"
          class="input"
          placeholder="Опишите симптомы"
          @keydown.enter="submitMessage"
        />
        <button class="btn" type="button" :disabled="sending" @click="submitMessage">
          {{ sending ? 'Отправка...' : 'Отправить' }}
        </button>
      </div>
    </article>
  </section>
</template>
