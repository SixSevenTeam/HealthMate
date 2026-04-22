import { httpRequest } from '@/shared/api/httpClient';

export function getMedications(page = 0, size = 20) {
  return httpRequest(`/api/medications?page=${page}&size=${size}`);
}

export function createMedication(payload) {
  return httpRequest('/api/medications', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function validateMedication(payload) {
  return httpRequest('/api/medications/validate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function deactivateMedication(id) {
  return httpRequest(`/api/medications/${id}`, {
    method: 'DELETE',
  });
}

export function setMedicationActive(id, isActive) {
  return httpRequest(`/api/medications/${id}/active`, {
    method: 'PUT',
    body: JSON.stringify({ isActive }),
  });
}
