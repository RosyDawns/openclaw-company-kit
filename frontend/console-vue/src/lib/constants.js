export const ROLE_ORDER = [
  "rd-company",
  "role-product",
  "role-tech-director",
  "role-senior-dev",
  "role-code-reviewer",
  "role-qa-test",
  "role-growth",
];

export const ROLE_LABEL = {
  "rd-company": "研发总监",
  "role-product": "产品经理",
  "role-tech-director": "技术总监",
  "role-senior-dev": "高级程序员",
  "role-code-reviewer": "代码 Reviewer",
  "role-qa-test": "测试工程师",
  "role-growth": "增长运营",
};

export function normalizeRoleId(raw) {
  const text = String(raw || "").trim();
  if (!text) return "";
  return text.startsWith("owner:") ? text.slice(6) : text;
}

export function roleLabel(id) {
  return ROLE_LABEL[id] || id || "未命名角色";
}

export function badgeClassByStatus(input) {
  const s = String(input || "").toLowerCase();
  if (s.includes("done") || s.includes("ok") || s.includes("healthy") || s.includes("on_track")) return "chip-ok";
  if (s.includes("blocked") || s.includes("error") || s.includes("fail")) return "chip-error";
  return "chip-warn";
}
