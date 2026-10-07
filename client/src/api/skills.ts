import type { ApiEnvelope } from "@/types/auth";
import api from "./client";

export interface Skill {
  name: string;
  aliases?: string[];
}

export async function getSkills(): Promise<Skill[]> {
  const response = await api.get<ApiEnvelope<{ skills: Skill[] }>>("/skills");
  return response.data.data.skills;
}

export async function suggestSkills(q: string): Promise<string[]> {
  const response = await api.get<ApiEnvelope<{ results: string[] }>>(
    "/skills",
    { params: { q } },
  );
  return response.data.data.results;
}
