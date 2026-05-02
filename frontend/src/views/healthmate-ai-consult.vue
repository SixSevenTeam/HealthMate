<script setup>
import { computed, onMounted, ref, watch, nextTick } from "vue";
import {
  createConversation,
  getConversationMessages,
  getConversations,
  sendMessage,
  deleteConversation,
} from "@/entities/chat/api/chatApi";
import Icon from "@/shared/components/Icon.vue";

const conversations = ref([]);
const selectedConversationId = ref("");
const messages = ref([]);
const prompt = ref("");
const loading = ref(false);
const sending = ref(false);
const errorMessage = ref("");
const messagesContainer = ref(null);
const newConvTitle = ref("");
const showNewConvForm = ref(false);
const showDeleteModal = ref(false);

const selectedConversation = computed(() =>
  conversations.value.find((c) => c.id === selectedConversationId.value),
);

async function loadConversations() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const page = await getConversations(0, 20);
    conversations.value = page.content || [];

    if (!selectedConversationId.value && conversations.value.length > 0) {
      selectedConversationId.value = conversations.value[0].id;
    }

    if (!selectedConversationId.value) {
      const created = await createConversation("Новая консультация");
      conversations.value.unshift(created);
      selectedConversationId.value = created.id;
    }
  } catch (error) {
    errorMessage.value = error.message || "Не удалось загрузить диалоги";
  } finally {
    loading.value = false;
  }
}

async function loadMessages() {
  if (!selectedConversationId.value) {
    return;
  }

  try {
    messages.value = await getConversationMessages(
      selectedConversationId.value,
    );
    await nextTick();
    scrollToBottom();
  } catch (error) {
    errorMessage.value = error.message || "Не удалось получить сообщения";
  }
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
}

async function submitMessage() {
  if (!prompt.value.trim() || !selectedConversationId.value) {
    return;
  }

  sending.value = true;
  errorMessage.value = "";
  const userPrompt = prompt.value.trim();
  prompt.value = "";

  try {
    const result = await sendMessage(selectedConversationId.value, userPrompt);
    messages.value.push(result.userMessage);
    messages.value.push(result.assistantMessage);
    await nextTick();
    scrollToBottom();
  } catch (error) {
    errorMessage.value = error.message || "Ошибка отправки сообщения";
    prompt.value = userPrompt;
  } finally {
    sending.value = false;
  }
}

async function createNewConversation() {
  const title = newConvTitle.value.trim() || "Новая консультация";
  try {
    const created = await createConversation(title);
    conversations.value.unshift(created);
    selectedConversationId.value = created.id;
    newConvTitle.value = "";
    showNewConvForm.value = false;
  } catch (error) {
    errorMessage.value = "Не удалось создать диалог";
  }
}

async function deleteCurrentConversation() {
  if (!selectedConversationId.value) return;

  try {
    await deleteConversation(selectedConversationId.value);
    conversations.value = conversations.value.filter(
      (c) => c.id !== selectedConversationId.value,
    );
    if (conversations.value.length > 0) {
      selectedConversationId.value = conversations.value[0].id;
    } else {
      const created = await createConversation("Новая консультация");
      conversations.value.unshift(created);
      selectedConversationId.value = created.id;
    }
  } catch (error) {
    errorMessage.value = "Не удалось удалить диалог";
  } finally {
    showDeleteModal.value = false;
  }
}

function requestDeleteConversation() {
  if (!selectedConversationId.value) return;
  showDeleteModal.value = true;
}

function closeDeleteModal() {
  showDeleteModal.value = false;
}

watch(selectedConversationId, loadMessages);
onMounted(loadConversations);
</script>

<template>
  <section class="chat-layout">
    <aside class="card chat-aside">
      <div class="row-between">
        <h2 class="card-title">Диалоги</h2>
        <button
          class="btn small conv-add-icon-btn"
          type="button"
          @click="showNewConvForm = !showNewConvForm"
          aria-label="Добавить диалог"
          title="Добавить диалог"
        >
          <Icon name="chatAdd" :size="20" className="icon-btn-mark" />
        </button>
      </div>

      <div v-if="showNewConvForm" class="new-conv-form">
        <input
          v-model="newConvTitle"
          class="input small"
          placeholder="Название диалога"
          @keydown.enter="createNewConversation"
        />
        <div class="button-group">
          <button class="btn small" @click="createNewConversation">
            Создать
          </button>
          <button class="btn small secondary" @click="showNewConvForm = false">
            Отмена
          </button>
        </div>
      </div>

      <p v-if="loading" class="muted">Загрузка...</p>
      <div class="conv-list" v-else>
        <button
          v-for="conversation in conversations"
          :key="conversation.id"
          class="conv-btn"
          :class="{ active: selectedConversationId === conversation.id }"
          type="button"
          @click="selectedConversationId = conversation.id"
        >
          <span class="conv-title">{{
            conversation.title || "Без названия"
          }}</span>
          <span class="conv-date">{{
            new Date(conversation.createdAt).toLocaleDateString("ru-RU")
          }}</span>
        </button>
      </div>
    </aside>

    <article class="card chat-main">
      <div class="chat-header">
        <div>
          <h2 class="card-title">
            {{ selectedConversation?.title || "AI-Консультация" }}
          </h2>
          <p v-if="selectedConversation" class="small muted">
            Создано:
            {{
              new Date(selectedConversation.createdAt).toLocaleString("ru-RU")
            }}
          </p>
        </div>
        <button
          class="btn small icon-action-btn"
          type="button"
          @click="requestDeleteConversation"
          v-if="selectedConversationId"
          aria-label="Удалить диалог"
          title="Удалить диалог"
        >
          <Icon name="chatDelete" :size="20" className="icon-btn-mark" />
        </button>
      </div>

      <p v-if="errorMessage" class="error-text">❌ {{ errorMessage }}</p>

      <div class="message-list" ref="messagesContainer">
        <div v-if="messages.length === 0" class="empty-state">
          <p class="muted">
            Начните беседу, описав ваши симптомы или задав вопрос
          </p>
        </div>
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message"
          :class="msg.role === 'user' ? 'message-user' : 'message-assistant'"
        >
          <div class="message-role">
            {{ msg.role === "user" ? "👤 Вы" : "🤖 AI" }}
          </div>
          <p class="message-text">{{ msg.content }}</p>
          <span class="message-time">
            {{
              new Date(msg.createdAt).toLocaleTimeString("ru-RU", {
                hour: "2-digit",
                minute: "2-digit",
              })
            }}
          </span>
        </div>
      </div>

      <div class="chat-input-row">
        <input
          v-model="prompt"
          class="input"
          placeholder="Опишите ваши симптомы или задайте вопрос..."
          @keydown.enter="submitMessage"
          :disabled="sending"
        />
        <button
          class="btn send-icon-btn"
          type="button"
          :disabled="sending || !prompt.trim()"
          @click="submitMessage"
          aria-label="Отправить сообщение"
          :title="sending ? 'Отправка...' : 'Отправить сообщение'"
        >
          <Icon name="chatSend" :size="22" className="icon-btn-mark send-icon-flip" />
        </button>
      </div>
    </article>
  </section>

  <div
    v-if="showDeleteModal"
    class="modal-overlay"
    @click.self="closeDeleteModal"
  >
    <div class="modal-dialog">
      <div class="modal-header">
        <h3 class="modal-title">Удалить диалог?</h3>
        <button
          type="button"
          class="modal-close"
          @click="closeDeleteModal"
          aria-label="Закрыть окно"
        >
          ×
        </button>
      </div>

      <div class="modal-body">
        <p class="modal-text">
          Диалог
          <strong>{{ selectedConversation?.title || "Без названия" }}</strong>
          будет удален без возможности восстановления.
        </p>
      </div>

      <div class="modal-footer">
        <button type="button" class="btn secondary" @click="closeDeleteModal">
          Отмена
        </button>
        <button type="button" class="btn danger" @click="deleteCurrentConversation">
          Удалить
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  height: 600px;
}

.chat-aside {
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow: hidden;
}

.chat-aside .row-between {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.new-conv-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 4px;
}

.new-conv-form .button-group {
  display: flex;
  gap: 6px;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.conv-btn {
  padding: 10px;
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
}

.conv-btn:hover {
  border-color: #0066cc;
  box-shadow: 0 1px 3px rgba(0, 102, 204, 0.1);
}

.conv-btn.active {
  background: #0066cc;
  color: white;
  border-color: #0066cc;
}

.conv-title {
  display: block;
  font-weight: 500;
}

.conv-date {
  display: block;
  font-size: 12px;
  opacity: 0.7;
}

.chat-main {
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow: hidden;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  border-bottom: 1px solid #eee;
  padding-bottom: 12px;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
  padding-right: 8px;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}

.message {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border-radius: 8px;
  max-width: 80%;
}

.message-user {
  align-self: flex-end;
  background: #0066cc;
  color: white;
}

.message-assistant {
  align-self: flex-start;
  background: #f0f0f0;
  color: black;
}

.message-role {
  font-size: 12px;
  font-weight: 600;
  opacity: 0.8;
}

.message-text {
  margin: 0;
  word-wrap: break-word;
}

.message-time {
  font-size: 11px;
  opacity: 0.6;
}

.chat-input-row {
  display: flex;
  gap: 8px;
}

.chat-input-row input {
  flex: 1;
}

.conv-add-icon-btn {
  min-width: 38px;
  width: 38px;
  height: 38px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  color: var(--primary);
  border: 1px solid #7da8ff;
  box-shadow: none;
}

.conv-add-icon-btn:hover {
  background: #f3f7ff;
  border-color: #4f86f5;
}

.icon-action-btn {
  min-width: 42px;
  height: 42px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  color: #cc3344;
  border: 1px solid #f2cdd3;
  box-shadow: none;
}

.icon-action-btn:hover {
  background: #fff3f5;
  border-color: #e9aeb8;
}

.send-icon-btn {
  width: 48px;
  min-width: 48px;
  height: 48px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: #fff;
  color: var(--primary);
  border: 1px solid #7da8ff;
  box-shadow: none;
}

.send-icon-btn:hover:not(:disabled) {
  background: #f3f7ff;
  border-color: #4f86f5;
}

.send-icon-btn:disabled {
  opacity: 0.6;
}

.icon-btn-mark {
  display: block;
}

.send-icon-flip {
  transform: scaleX(-1);
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1200;
}

.modal-dialog {
  width: min(92vw, 440px);
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e3e8f3;
  box-shadow: 0 20px 45px rgba(0, 25, 60, 0.22);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid #edf1f7;
}

.modal-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #1a2433;
}

.modal-close {
  border: none;
  background: transparent;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 24px;
  line-height: 1;
  color: #5a6b85;
}

.modal-close:hover {
  background: #f1f5fb;
  color: #24344f;
}

.modal-body {
  padding: 16px 18px;
}

.modal-text {
  margin: 0;
  color: #2c3b53;
  line-height: 1.45;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 18px 18px;
}

@media (max-width: 768px) {
  .chat-layout {
    grid-template-columns: 1fr;
    height: auto;
  }

  .chat-aside {
    display: none;
  }

  .message {
    max-width: 95%;
  }
}
</style>
