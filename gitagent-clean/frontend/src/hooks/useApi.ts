import { useState, useCallback } from 'react';
import axios from 'axios';
import type { Agent, FileInfo } from '@/types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';
const api = axios.create({ baseURL: API_BASE_URL });

export function useCloneRepository() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const clone = useCallback(async (repoUrl: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.post('/api/clone', { repoUrl });
      setLoading(false);
      return response.data;
    } catch (err: any) {
      const message = err.response?.data?.detail || err.message;
      setError(message);
      setLoading(false);
      throw new Error(message);
    }
  }, []);

  return { clone, loading, error };
}

export function useChat() {
  const [loading, setLoading] = useState(false);

  const sendMessage = useCallback(async (sessionId: string, agentId: string, message: string) => {
    setLoading(true);
    try {
      const response = await api.post('/api/chat', { sessionId, agentId, message });
      setLoading(false);
      return response.data;
    } catch (err: any) {
      setLoading(false);
      throw err;
    }
  }, []);

  return { sendMessage, loading };
}

export function useGetFiles() {
  const [loading, setLoading] = useState(false);

  const getFiles = useCallback(async (sessionId: string) => {
    setLoading(true);
    try {
      const response = await api.get(`/api/files/${sessionId}`);
      setLoading(false);
      return response.data.files as FileInfo[];
    } catch (err) {
      setLoading(false);
      throw err;
    }
  }, []);

  return { getFiles, loading };
}

export function useDownload() {
  const [loading, setLoading] = useState(false);

  const download = useCallback(async (sessionId: string) => {
    setLoading(true);
    try {
      const response = await api.get(`/api/download/${sessionId}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `gitagent-${sessionId}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setLoading(false);
    } catch (err) {
      setLoading(false);
      throw err;
    }
  }, []);

  return { download, loading };
}

export function useDeleteSession() {
  const deleteSession = useCallback(async (sessionId: string) => {
    await api.delete(`/api/session/${sessionId}`);
  }, []);

  return { deleteSession };
}
