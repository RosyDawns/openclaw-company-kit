# OpenClaw Console UI (Vue3 + TailwindCSS)

独立前端工程（保留在同一仓库内），用于重构配置中心与驾驶舱 UI/UE。

## 本地开发

```bash
cd frontend/console-vue
npm install
npm run dev
```

默认地址：`http://127.0.0.1:5177/ui/setup`

## 构建

```bash
cd frontend/console-vue
npm run build
```

输出目录：`frontend/console-vue/dist`

## 与 control_server.py 集成

- 当 `dist` 存在时：
  - `/setup` 自动跳转到 `/ui/setup`
  - `/dashboard` 自动跳转到 `/ui/dashboard`
  - `/dashboard/<role-id>` 自动跳转到 `/ui/dashboard/<role-id>`
- 当 `dist` 不存在时：
  - 继续使用旧版 `web/setup.html` 与 `dashboard/rd-dashboard/index.html`（降级兜底）
