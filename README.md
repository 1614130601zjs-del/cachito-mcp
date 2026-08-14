# Cachito 全线产品万能 MCP

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/你的用户名/cachito-universal-mcp)

- 纯 HTTP Streamable，端点 `/mcp`
- `device_id` 通过 `getRemoteInfo` 实时获取
- 中文指令：吮吸、入体、脉冲、炮机、抽插、震动、秒潮

## MCP 配置

```json
{
  "mcpServers": {
    "cachito": {
      "command": "npx",
      "args": ["-y", "mcp-remote@latest", "https://你的服务.onrender.com/mcp"]
    }
  }
}
