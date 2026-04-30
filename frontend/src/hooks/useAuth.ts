import { create } from "zustand";
import { authApi } from "../api/auth";
import type { User } from "../types";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string, webhookUrl?: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  error: null,

  login: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const token = await authApi.login({ email, password });
      localStorage.setItem("access_token", token);
      const user = await authApi.me();
      set({ user, isLoading: false });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Login failed";
      set({ error: msg, isLoading: false });
      throw err;
    }
  },

  register: async (email, username, password, webhookUrl) => {
    set({ isLoading: true, error: null });
    try {
      const token = await authApi.register({ email, username, password, webhook_url: webhookUrl });
      localStorage.setItem("access_token", token);
      const user = await authApi.me();
      set({ user, isLoading: false });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Registration failed";
      set({ error: msg, isLoading: false });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem("access_token");
    set({ user: null });
  },

  fetchMe: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) return;
    set({ isLoading: true });
    try {
      const user = await authApi.me();
      set({ user, isLoading: false });
    } catch {
      localStorage.removeItem("access_token");
      set({ user: null, isLoading: false });
    }
  },
}));
