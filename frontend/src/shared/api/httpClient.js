import { API_BASE_URL, USE_MOCK_API } from './config';

const mockState = {
  user: {
    id: 'ca1ae1de-1d9f-5f8b-8840-15821a988dff',
    email: 'demo1@healthmate.local',
    firstName: 'Ольга',
    lastName: 'Козлова',
    birthDate: '1957-11-22',
  },
  profile: {
    heightCm: 178,
    weightKg: 76.5,
    bloodType: 'A+',
    diagnoses: [{ name: 'Hypertension', diagnosedAt: '2020-05-12' }],
    allergies: [{ allergen: 'Penicillin', reaction: 'Rash' }],
    updatedAt: new Date().toISOString(),
  },
  medications: [
    {
      id: '07e715e3-a6c3-55cd-9042-94d3c55228a5',
      tradeName: 'Ибупрофен',
      customName: null,
      doseAmount: 200,
      doseUnit: 'mg',
      instructions: 'После еды',
      doseWarning: null,
      safetyStatus: 'ok',
      safetyWarnings: [],
      isActive: true,
      startDate: '2026-04-01',
      endDate: null,
      schedules: [{ id: 'sch-1', timeOfDay: '08:00:00', daysOfWeek: [1, 2, 3, 4, 5] }],
    },
    {
      id: 'med-2',
      tradeName: null,
      customName: 'Омепразол',
      doseAmount: 20,
      doseUnit: 'mg',
      instructions: 'Утром до еды',
      doseWarning: null,
      safetyStatus: 'ok',
      safetyWarnings: [],
      isActive: true,
      startDate: '2026-04-10',
      endDate: null,
      schedules: [{ id: 'sch-2', timeOfDay: '12:30:00', daysOfWeek: [1, 2, 3, 4, 5] }],
    },
  ],
  conversations: [
    {
      id: 'conv-1',
      title: 'Новая консультация',
      createdAt: new Date().toISOString(),
    },
  ],
  messagesByConversation: {
    'conv-1': [
      {
        id: 'msg-1',
        conversationId: 'conv-1',
        role: 'assistant',
        content: 'Здравствуйте. Опишите ваши симптомы, и я помогу с общими рекомендациями.',
        createdAt: new Date().toISOString(),
      },
    ],
  },
};

function readJsonBody(options) {
  if (!options?.body) return {};
  try {
    return JSON.parse(options.body);
  } catch {
    return {};
  }
}

function uid(prefix) {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
}

function toDashboardSummary() {
  const active = mockState.medications.filter((item) => item.isActive);
  const adherence = active.map((item) => ({
    medicationId: item.id,
    tradeName: item.tradeName || item.customName || 'Medication',
    totalScheduled: 7,
    totalTaken: 6,
    adherencePercent: 85.71,
    missedDates: ['2026-04-03'],
  }));
  return {
    period: {
      from: '2026-04-01',
      to: '2026-04-07',
    },
    adherence,
    insights: [`Overall adherence: ${adherence.length > 0 ? '85.71' : '0.00'}%`],
  };
}

async function mockRequest(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const body = readJsonBody(options);
  const now = new Date().toISOString();

  if (path === '/api/health' && method === 'GET') {
    return { status: 'UP', service: 'healthmate-backend', timestamp: now };
  }

  if (path === '/api/auth/me' && method === 'GET') {
    return mockState.user;
  }

  if (path === '/api/auth/login' && method === 'POST') {
    return mockState.user;
  }

  if (path === '/api/auth/logout' && method === 'POST') {
    return { message: 'Logged out successfully' };
  }

  if (path === '/api/profile' && method === 'GET') {
    return mockState.profile;
  }

  if (path === '/api/profile' && method === 'PUT') {
    mockState.profile = {
      ...mockState.profile,
      ...body,
      updatedAt: now,
    };
    return { updatedAt: mockState.profile.updatedAt };
  }

  if (path.startsWith('/api/medications?page=') && method === 'GET') {
    const active = mockState.medications.filter((item) => item.isActive);
    const inactive = mockState.medications.filter((item) => !item.isActive);
    return {
      active,
      inactive,
      page: 0,
      size: 20,
      total: mockState.medications.length,
    };
  }

  if (path === '/api/medications/validate' && method === 'POST') {
    const warnings = [];
    if ((body.customName || '').toLowerCase().includes('ибупрофен')) {
      warnings.push('Проверьте совместимость с гастропротекцией при длительном приеме.');
    }
    return {
      status: warnings.length > 0 ? 'warning' : 'ok',
      warnings,
      blockers: [],
      metadata: {},
    };
  }

  if (path === '/api/medications' && method === 'POST') {
    const created = {
      id: uid('med'),
      tradeName: null,
      customName: body.customName || 'Новое лекарство',
      doseAmount: body.doseAmount || 0,
      doseUnit: body.doseUnit || 'mg',
      instructions: body.instructions || '',
      doseWarning: null,
      safetyStatus: 'ok',
      safetyWarnings: [],
      isActive: true,
      startDate: body.startDate || '2026-04-01',
      endDate: body.endDate || null,
      schedules: (body.schedules || []).map((schedule) => ({
        id: uid('sch'),
        ...schedule,
      })),
    };
    mockState.medications.unshift(created);
    return created;
  }

  if (path.startsWith('/api/medications/') && method === 'DELETE') {
    const id = path.split('/').at(-1);
    const target = mockState.medications.find((item) => item.id === id);
    if (target) {
      target.isActive = false;
      return { id: target.id, isActive: false };
    }
    throw new Error('Medication not found');
  }

  if (path.endsWith('/active') && method === 'PUT') {
    const id = path.split('/')[3];
    const target = mockState.medications.find((item) => item.id === id);
    if (target) {
      target.isActive = Boolean(body.isActive);
      return { id: target.id, isActive: target.isActive };
    }
    throw new Error('Medication not found');
  }

  if (path.startsWith('/api/conversations?page=') && method === 'GET') {
    return {
      content: mockState.conversations,
      totalElements: mockState.conversations.length,
      number: 0,
      size: 20,
    };
  }

  if (path === '/api/conversations' && method === 'POST') {
    const created = {
      id: uid('conv'),
      title: body.title || 'Новая консультация',
      createdAt: now,
    };
    mockState.conversations.unshift(created);
    mockState.messagesByConversation[created.id] = [];
    return created;
  }

  if (path.includes('/messages') && method === 'GET') {
    const conversationId = path.split('/')[3];
    return mockState.messagesByConversation[conversationId] || [];
  }

  if (path.includes('/messages') && method === 'POST') {
    const conversationId = path.split('/')[3];
    const userMessage = {
      id: uid('msg'),
      conversationId,
      role: 'user',
      content: body.content || '',
      createdAt: now,
    };
    const assistantMessage = {
      id: uid('msg'),
      conversationId,
      role: 'assistant',
      content: 'Тестовая заглушка AI: похоже на легкие симптомы. При ухудшении обратитесь к врачу.',
      createdAt: now,
    };
    const list = mockState.messagesByConversation[conversationId] || [];
    list.push(userMessage, assistantMessage);
    mockState.messagesByConversation[conversationId] = list;
    return {
      userMessage,
      assistantMessage,
      messageType: 'question',
      disclaimer: 'Это тестовые данные для просмотра интерфейса.',
      recommendedDrugs: [],
    };
  }

  if (path.startsWith('/api/dashboard/summary') && method === 'GET') {
    return toDashboardSummary();
  }

  throw new Error(`Mock route is not implemented: ${method} ${path}`);
}

async function parseResponse(response) {
  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const payload = isJson ? await response.json() : null;

  if (response.ok) {
    return payload;
  }

  const error = new Error(payload?.message || 'Request failed');
  error.status = response.status;
  error.code = payload?.error || 'REQUEST_ERROR';
  error.fields = payload?.fields || null;
  throw error;
}

export async function httpRequest(path, options = {}) {
  if (USE_MOCK_API) {
    return mockRequest(path, options);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });

  return parseResponse(response);
}
