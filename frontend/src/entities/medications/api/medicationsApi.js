import { httpRequest } from "@/shared/api/httpClient";

export function getMedications(page = 0, size = 20) {
  return httpRequest(`/api/medications?page=${page}&size=${size}`);
}

export function createMedication(payload) {
  return httpRequest("/api/medications", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function validateMedication(payload) {
  return httpRequest("/api/medications/validate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deactivateMedication(id) {
  return httpRequest(`/api/medications/${id}`, {
    method: "DELETE",
  });
}

export function setMedicationActive(id, isActive) {
  return httpRequest(`/api/medications/${id}/active`, {
    method: "PUT",
    body: JSON.stringify({ isActive }),
  });
}

// Расписания
export function getSchedules(medicationId) {
  return httpRequest(`/api/medications/${medicationId}/schedules`);
}

export function addSchedule(medicationId, payload) {
  return httpRequest(`/api/medications/${medicationId}/schedules`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteSchedule(scheduleId) {
  return httpRequest(`/api/medications/schedules/${scheduleId}`, {
    method: "DELETE",
  });
}

// Логи приема
export function getIntakeLogs(medicationId, from, to) {
  return httpRequest(
    `/api/medications/${medicationId}/intake-logs?from=${from}&to=${to}`,
  );
}

export function confirmIntake(logId) {
  return httpRequest(`/api/medications/intake-logs/${logId}/take`, {
    method: "POST",
  });
}

export function updateIntakeStatus(logId, status) {
  return httpRequest(`/api/medications/intake-logs/${logId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
