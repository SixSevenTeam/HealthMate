<script setup>
import { ref } from "vue";

const API_BASE = "http://localhost:8080/healthmate";
const token = ref(localStorage.getItem("hm_token") || "");

const registerForm = ref({
  email: "",
  password: "",
  firstName: "",
  lastName: "",
  birthDate: "",
  heightCm: "",
  weightKg: "",
  bloodType: "",
  diagnosesText: "",
  allergiesText: "",
});

const loginForm = ref({ email: "", password: "" });
const statusText = ref("");
const currentUser = ref(null);
const conversationId = ref("");
const chatInput = ref("");
const chatLog = ref([]);

function authHeaders(withJson = true) {
  const headers = {};
  if (withJson) headers["Content-Type"] = "application/json";
  if (token.value) headers.Authorization = `Bearer ${token.value}`;
  return headers;
}

async function registerAndInitProfile() {
  statusText.value = "Регистрация...";
  const reg = await fetch(`${API_BASE}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: registerForm.value.email,
      password: registerForm.value.password,
      firstName: registerForm.value.firstName,
      lastName: registerForm.value.lastName,
      birthDate: registerForm.value.birthDate || null,
    }),
  });

  if (!reg.ok) {
    statusText.value = `Ошибка регистрации: ${await reg.text()}`;
    return;
  }

  const login = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: registerForm.value.email,
      password: registerForm.value.password,
    }),
  });
  const loginData = await login.json();
  token.value = loginData.token || "";
  localStorage.setItem("hm_token", token.value);

  const diagnoses = registerForm.value.diagnosesText
    ? [{ name: registerForm.value.diagnosesText, diagnosedAt: "2024-01" }]
    : [];
  const allergies = registerForm.value.allergiesText
    ? [{ allergen: registerForm.value.allergiesText, reaction: "не указано" }]
    : [];

  await fetch(`${API_BASE}/api/profile`, {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify({
      heightCm: registerForm.value.heightCm
        ? Number(registerForm.value.heightCm)
        : null,
      weightKg: registerForm.value.weightKg
        ? Number(registerForm.value.weightKg)
        : null,
      bloodType: registerForm.value.bloodType || null,
      diagnoses,
      allergies,
    }),
  });

  statusText.value = "Регистрация и первичный анамнез сохранены.";
  await loadMe();
}

async function login() {
  statusText.value = "Вход...";
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(loginForm.value),
  });
  const data = await res.json();
  if (!res.ok || !data.token) {
    statusText.value = `Ошибка входа: ${JSON.stringify(data)}`;
    return;
  }
  token.value = data.token;
  localStorage.setItem("hm_token", token.value);
  statusText.value = "Вход выполнен.";
  await loadMe();
}

async function loadMe() {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    headers: authHeaders(false),
  });
  if (!res.ok) {
    statusText.value = "Нужно войти в кабинет.";
    return;
  }
  currentUser.value = await res.json();
}

async function createConversation() {
  const res = await fetch(`${API_BASE}/api/conversations`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ title: "Диалог с ИИ" }),
  });
  if (!res.ok) {
    const errorText = await res.text();
    statusText.value = `Ошибка создания диалога: ${errorText}`;
    conversationId.value = "";
    return false;
  }
  const data = await res.json();
  if (!data?.id) {
    statusText.value = "Ошибка создания диалога: не получен conversationId";
    conversationId.value = "";
    return false;
  }
  conversationId.value = data.id;
  chatLog.value = [];
  return true;
}

async function sendMessage() {
  if (!conversationId.value) {
    const created = await createConversation();
    if (!created) return;
  }
  const content = chatInput.value.trim();
  if (!content) return;

  const res = await fetch(
    `${API_BASE}/api/conversations/${conversationId.value}/messages`,
    {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ content }),
    },
  );
  const data = await res.json();
  if (!res.ok) {
    statusText.value = `Ошибка чата: ${JSON.stringify(data)}`;
    return;
  }

  const userMsg = data.userMessage?.content || content;
  const assistantContent = data.assistantMessage?.content || "Нет ответа";
  const recommendedDrugs = data.assistantMessage?.recommendedDrugs || [];

  chatLog.value.push({ role: "user", content: userMsg });
  chatLog.value.push({
    role: "assistant",
    content: assistantContent,
    drugs: recommendedDrugs,
    messageType: data.assistantMessage?.messageType || "normal",
  });
  chatInput.value = "";
}

loadMe();
</script>

<template>
  <div class="page">
    <h1>HealthMate MVP</h1>
    <p class="status">{{ statusText }}</p>

    <section class="card">
      <h2>Регистрация + первичный анамнез</h2>
      <div class="grid">
        <input v-model="registerForm.email" placeholder="Email" />
        <input
          v-model="registerForm.password"
          type="password"
          placeholder="Пароль"
        />
        <input v-model="registerForm.firstName" placeholder="Имя" />
        <input v-model="registerForm.lastName" placeholder="Фамилия" />
        <input
          v-model="registerForm.birthDate"
          type="date"
          placeholder="Дата рождения"
        />
        <input
          v-model="registerForm.heightCm"
          type="number"
          placeholder="Рост (см)"
        />
        <input
          v-model="registerForm.weightKg"
          type="number"
          step="0.1"
          placeholder="Вес (кг)"
        />
        <input v-model="registerForm.bloodType" placeholder="Группа крови" />
        <input
          v-model="registerForm.diagnosesText"
          placeholder="Основной диагноз"
        />
        <input v-model="registerForm.allergiesText" placeholder="Аллергия" />
      </div>
      <button @click="registerAndInitProfile">Зарегистрироваться</button>
    </section>

    <section class="card">
      <h2>Вход</h2>
      <div class="grid two">
        <input v-model="loginForm.email" placeholder="Email" />
        <input
          v-model="loginForm.password"
          type="password"
          placeholder="Пароль"
        />
      </div>
      <button @click="login">Войти</button>
      <p v-if="currentUser">
        Пользователь: {{ currentUser.firstName }} ({{ currentUser.email }})
      </p>
    </section>

    <section class="card" v-if="token">
      <h2>ИИ помощник (сбор анамнеза + RAG)</h2>
      <div class="chat">
        <div v-for="(msg, i) in chatLog" :key="i" :class="['msg', msg.role]">
          <strong>{{ msg.role === "user" ? "Вы" : "ИИ" }}:</strong>
          <p>{{ msg.content }}</p>
          <div v-if="msg.drugs && msg.drugs.length > 0" class="drugs-section">
            <strong>📋 Рекомендуемые препараты:</strong>
            <ul>
              <li v-for="(drug, idx) in msg.drugs" :key="idx" class="drug-item">
                <strong>{{ drug.title }}</strong>
                <p v-if="drug.description">{{ drug.description }}</p>
                <small v-if="drug.relevance_score">
                  Релевантность: {{ (drug.relevance_score * 100).toFixed(0) }}%
                </small>
              </li>
            </ul>
          </div>
        </div>
      </div>
      <div class="chat-input">
        <input
          v-model="chatInput"
          placeholder="Опишите симптом..."
          @keyup.enter="sendMessage"
        />
        <button @click="sendMessage">Отправить</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page {
  max-width: 980px;
  margin: 0 auto;
  padding: 24px;
  font-family: "Segoe UI", sans-serif;
}

h1 {
  margin-bottom: 8px;
}

.status {
  color: #555;
}

.card {
  border: 1px solid #ddd;
  border-radius: 12px;
  padding: 16px;
  margin-top: 16px;
  background: #fff;
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

input {
  border: 1px solid #ccc;
  border-radius: 8px;
  padding: 10px;
}

button {
  border: none;
  border-radius: 8px;
  padding: 10px 14px;
  background: #0d6efd;
  color: #fff;
  cursor: pointer;
}

.chat {
  border: 1px solid #eee;
  border-radius: 8px;
  min-height: 180px;
  max-height: 300px;
  overflow: auto;
  padding: 8px;
  margin-bottom: 10px;
  background: #fafafa;
}

.msg {
  padding: 8px;
  border-radius: 8px;
  margin-bottom: 8px;
}

.msg.user {
  background: #e8f0ff;
}

.msg.assistant {
  background: #edf8ef;
}

.msg p {
  margin: 4px 0;
}

.drugs-section {
  margin-top: 12px;
  padding: 10px;
  background: #fff9e6;
  border-left: 3px solid #ffc107;
  border-radius: 4px;
}

.drugs-section strong {
  display: block;
  margin-bottom: 8px;
}

.drugs-section ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.drug-item {
  padding: 8px;
  margin-bottom: 8px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #ffd699;
}

.drug-item strong {
  display: block;
  color: #d39e00;
}

.drug-item p {
  margin: 4px 0;
  font-size: 0.9em;
  color: #555;
}

.drug-item small {
  display: block;
  color: #888;
  font-size: 0.85em;
}

.chat-input {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}

@media (max-width: 800px) {
  .grid,
  .grid.two {
    grid-template-columns: 1fr;
  }
}
</style>
