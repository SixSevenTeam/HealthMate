<script setup>
import { computed, onMounted, ref, watch, nextTick } from "vue";
import {
  createConversation,
  getConversationMessages,
  getConversations,
  sendMessage,
  deleteConversation,
} from "@/entities/chat/api/chatApi";

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
  if (!confirm("Вы уверены?")) return;

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
        <button
          class="btn small"
          type="button"
          @click="showNewConvForm = !showNewConvForm"
        >
          +
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
          class="btn small danger"
          type="button"
          @click="deleteCurrentConversation"
          v-if="selectedConversationId"
        >
          Удалить диалог
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
          class="btn"
          type="button"
          :disabled="sending || !prompt.trim()"
          @click="submitMessage"
        >
          {{ sending ? "⏳ Отправка..." : "📤 Отправить" }}
        </button>
      </div>
    </article>
  </section>
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
