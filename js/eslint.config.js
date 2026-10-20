import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      camelcase: ["error", { properties: "never" }],
      eqeqeq: ["error", "always", { null: "ignore" }],
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
);
