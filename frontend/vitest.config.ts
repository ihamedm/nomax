import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: { alias: { "@": "/src" } },
  test: {
    environment: "jsdom",
    coverage: {
      provider: "v8",
      include: ["src/lib/digits.ts", "src/lib/format.ts", "src/lib/jalali.ts"],
      thresholds: { lines: 60, functions: 60, statements: 60, branches: 50 },
    },
  },
});
