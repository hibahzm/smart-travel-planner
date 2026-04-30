import { apiClient } from "./client";
import type { User } from "../types";

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  username: string;
  password: string;
  webhook_url?: string;
}

export const authApi = {
  login: async (data: LoginPayload): Promise<string> => {
    const res = await apiClient.post<{ access_token: string }>("/api/auth/login", data);
    return res.data.access_token;
  },

  register: async (data: RegisterPayload): Promise<string> => {
    const res = await apiClient.post<{ access_token: string }>("/api/auth/register", data);
    return res.data.access_token;
  },

  me: async (): Promise<User> => {
    const res = await apiClient.get<User>("/api/auth/me");
    return res.data;
  },

  updateWebhook: async (webhook_url: string): Promise<User> => {
    const res = await apiClient.patch<User>("/api/auth/webhook", { webhook_url });
    return res.data;
  },
};
