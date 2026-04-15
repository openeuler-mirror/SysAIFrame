# SysAIFrame

#### 介绍
SysAIFrame 是 CTyunOS 操作系统级 AI 服务统一框架，提供统一的 AI 模型调用接口。

#### 软件架构

SysAIFrame 采用分层架构设计：
- **API 层**：提供 OpenAI 兼容的 REST API
- **路由层**：智能模型选择和负载均衡
- **LLM 适配层**：支持多种模型提供商
- **D-Bus 服务层**：提供系统级 D-Bus 接口

#### 主要特性

- OpenAI API 兼容接口
- 支持多种 LLM 提供商（DeepSeek、GPT、MoonShot 等）
- 智能路由和负载均衡
- D-Bus 系统服务接口
- 健康检查和自动故障转移
- 多语言 SDK 支持（Python、Rust、C）

#### 安装教程

1. 安装 RPM 包：`rpm -ivh sysaiframe-1.0.0-1.el8.x86_64.rpm`
2. 配置模型：`cp /etc/sysaiframe/models.yaml.example /etc/sysaiframe/models.yaml`
3. 修改配置文件中的 endpoint 和 api_key
4. 启动服务：`systemctl start sysaiframe`

#### 使用说明

1. API 调用示例（curl）：
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-chat", "messages": [{"role": "user", "content": "Hello"}]}'
```

2. Python SDK 使用：
```python
from sysai import SysAIClient
client = SysAIClient()
response = client.chat(messages=[{"role": "user", "content": "Hello"}])
print(response.content)
```

3. CLI 工具：
```bash
ai-config model list
ai-config model add my-model --api http://localhost:8000/v1 --api_key sk-xxx
```

#### 参与贡献

1.  Fork 本仓库
2.  新建 Feat_xxx 分支
3.  提交代码
4.  新建 Pull Request

#### 许可证

MulanPSL-2.0
