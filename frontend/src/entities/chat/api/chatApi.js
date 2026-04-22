import { httpRequest } from '@/shared/api/httpClient';

export function getConversations(page = 0, size = 20) {
  return httpRequest(`/api/conversations?page=${page}&size=${size}`);
}

export function createConversation(title) {
  return httpRequest('/api/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  });
}

export function getConversationMessages(conversationId) {
  return httpRequest(`/api/conversations/${conversationId}/messages`);
}

export function sendMessage(conversationId, content) {
  return httpRequest(`/api/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

export function deleteConversation(conversationId) {
  return httpRequest(`/api/conversations/${conversationId}`, {
    method: 'DELETE',
  });
}
