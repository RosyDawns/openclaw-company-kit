# 生产部署

## 方式一：Caddy TLS 反向代理（推荐）

适合已有服务器，OpenClaw 以原生方式运行。

```bash
# 1. 安装 Caddy (https://caddyserver.com/docs/install)
sudo apt install -y caddy   # Debian/Ubuntu
# brew install caddy         # macOS

# 2. 确保域名 DNS 已指向服务器，80/443 端口可达

# 3. 启动
DOMAIN=your-domain.com caddy run --config deploy/Caddyfile
```

Caddy 会自动申请并续期 Let's Encrypt 证书，无需额外配置。

## 方式二：Docker Compose 一键部署

适合全新服务器，无需手动安装 Node.js / OpenClaw。

```bash
# 1. 拷贝并修改 .env
cp .env.example .env
# 编辑 .env 填入所有必需变量

# 2. 设置域名（可选，默认 localhost 自签名）
export DOMAIN=your-domain.com

# 3. 启动全部服务
cd deploy
docker compose -f docker-compose.prod.yml up -d

# 4. 查看状态
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DOMAIN` | `localhost` | Caddy 绑定域名 |
| `GATEWAY_PORT` | `3000` | OpenClaw Gateway 端口 |
| `DASHBOARD_PORT` | `8788` | Dashboard 端口 |
| `OPENCLAW_PROFILE` | `company` | OpenClaw 配置隔离 |

## 注意事项

- Docker 方式下 `openclaw-data` volume 持久化 agent 数据
- 内网/开发环境 `DOMAIN=localhost` 会生成自签名证书
- 生产环境确保防火墙放通 80/443
