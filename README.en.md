# SysAIFrame

#### Description
SysAIFrame is CTyunOS operating system-level AI service unified framework, providing unified AI model invocation interface.

#### Software Architecture

SysAIFrame uses a layered architecture:
- **API Layer**: OpenAI-compatible REST API
- **Routing Layer**: Intelligent model selection and load balancing
- **LLM Adapter Layer**: Support for multiple model providers
- **D-Bus Service Layer**: System-level D-Bus interface

#### Key Features

- OpenAI API compatible interface
- Support for multiple LLM providers (DeepSeek, GPT, MoonShot, etc.)
- Intelligent routing and load balancing
- D-Bus system service interface
- Health checking and automatic failover
- Multi-language SDK support (Python, Rust, C)

#### Installation

1. Install RPM package: `rpm -ivh sysaiframe-1.0.0-1.el8.x86_64.rpm`
2. Configure models: `cp /etc/sysaiframe/models.yaml.example /etc/sysaiframe/models.yaml`
3. Edit config file to set endpoint and api_key
4. Start service: `systemctl start sysaiframe`

#### Usage

1. API example (curl):
```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "deepseek-chat", "messages": [{"role": "user", "content": "Hello"}]}'
```

2. Python SDK usage:
```python
from sysai import SysAIClient
client = SysAIClient()
response = client.chat(messages=[{"role": "user", "content": "Hello"}])
print(response.content)
```

3. CLI tools:
```bash
ai-config model list
ai-config model add my-model --api http://localhost:8000/v1 --api_key sk-xxx
```

#### Contribution

1.  Fork the repository
2.  Create Feat_xxx branch
3.  Commit your code
4.  Create Pull Request

#### License

MulanPSL-2.0
