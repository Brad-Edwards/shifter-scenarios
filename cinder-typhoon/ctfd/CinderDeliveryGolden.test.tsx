import fs from "node:fs";

import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/api/client";
import { renderRoute } from "@/test/utils";

import { ChallengesPage } from "./ChallengesPage";

vi.mock("@/api/client", () => ({ apiFetch: vi.fn() }));

const mockApi = vi.mocked(apiFetch);
const bundlePath = process.env.CINDER_EVENT_BUNDLE;
if (!bundlePath) throw new Error("CINDER_EVENT_BUNDLE is required");
const bundle = JSON.parse(fs.readFileSync(bundlePath, "utf8"));
const challenges = bundle.challenges.map((challenge: Record<string, unknown>) => ({
  id: challenge.id,
  name: challenge.name,
  category: challenge.category,
  points: challenge.points,
  difficulty: challenge.difficulty,
  order: challenge.order,
  solved: false,
  tags: [],
  topics: [],
}));

beforeEach(() => {
  mockApi.mockReset();
});

describe("Cinder delivery golden catalog", () => {
  it("renders every imported card with its exact score", async () => {
    mockApi.mockResolvedValue(challenges);
    renderRoute(<ChallengesPage />);

    expect(await screen.findByText("0 of 240 solved")).toBeInTheDocument();
    for (const challenge of challenges) {
      const title = screen.getByText(challenge.name as string);
      const card = title.closest("a");
      expect(card).not.toBeNull();
      expect(card).toHaveTextContent(`${challenge.points} pts`);
    }
    expect(screen.getAllByRole("link").filter((link) => link.getAttribute("href")?.startsWith("/ctf/challenges/"))).toHaveLength(240);
  });
});
