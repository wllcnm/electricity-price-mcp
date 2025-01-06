# Electricity Price MCP Server

这是一个基于 MCP (Model Control Protocol) 的电价查询服务器实现。它提供了查询各地区电价信息的功能，支持按地区和时间进行查询。

## 功能特性

- 按地区查询电价
- 按月份查询电价
- 支持查询峰谷电价
- 支持查询不同用电类型
- 支持查询不同电压等级

## 环境要求

- Python 3.10+
- MCP 0.1.0+
- aiomysql 0.2.0+
- MySQL 5.7+
- Docker

## 环境变量配置

使用前需要设置以下环境变量：

- `MYSQL_HOST`: MySQL 服务器地址（默认：localhost）
- `MYSQL_PORT`: MySQL 服务器端口（默认：3306）
- `MYSQL_USER`: MySQL 用户名（默认：root）
- `MYSQL_PASSWORD`: MySQL 密码
- `MYSQL_DATABASE`: MySQL 数据库名（默认：electricity）

## 在 Claude 客户端中使用

1. 在你的 `claude_desktop_config.json` 中添加以下配置：

### Windows 版本
```json
{
  "mcpServers": {
    "electricity": {
      "command": "cmd",
      "args": [
        "/c",
        "for /f \"tokens=1\" %i in ('docker ps -a --filter name^=mcp-electricity-price --format {{.ID}}') do docker rm -f %i 2>nul & docker pull ghcr.io/你的用户名/mcp-electricity-price:latest & docker run -i --rm --name mcp-electricity-price -e MYSQL_HOST=你的主机地址 -e MYSQL_PORT=3306 -e MYSQL_USER=你的用户名 -e MYSQL_PASSWORD=你的密码 -e MYSQL_DATABASE=electricity ghcr.io/你的用户名/mcp-electricity-price:latest"
      ]
    }
  }
}
```

### Mac/Linux 版本
```json
{
  "mcpServers": {
    "electricity": {
      "command": "sh",
      "args": [
        "-c",
        "docker ps -a --filter name=mcp-electricity-price -q | xargs -r docker rm -f; docker pull ghcr.io/你的用户名/mcp-electricity-price:latest && docker run -i --rm --name mcp-electricity-price -e MYSQL_HOST=你的主机地址 -e MYSQL_PORT=3306 -e MYSQL_USER=你的用户名 -e MYSQL_PASSWORD=你的密码 -e MYSQL_DATABASE=electricity ghcr.io/你的用户名/mcp-electricity-price:latest"
      ]
    }
  }
}
```

2. 重启 Claude 客户端

## 本地开发

### 安装

```bash
pip install -r requirements.txt
```

### 运行

直接运行服务器：
```bash
python src/server.py
```

使用 Docker 运行：

Windows:
```cmd
REM 清理旧容器
for /f "tokens=1" %i in ('docker ps -a --filter name^=mcp-electricity-price --format {{.ID}}') do docker rm -f %i

REM 构建并运行新容器
docker build -t electricity-price-mcp .
docker run -i --rm --name mcp-electricity-price ^
  -e MYSQL_HOST=你的主机地址 ^
  -e MYSQL_PORT=3306 ^
  -e MYSQL_USER=你的用户名 ^
  -e MYSQL_PASSWORD=你的密码 ^
  -e MYSQL_DATABASE=electricity ^
  electricity-price-mcp
```

Mac/Linux:
```bash
# 清理旧容器
docker ps -a --filter name=mcp-electricity-price -q | xargs -r docker rm -f

# 构建并运行新容器
docker build -t electricity-price-mcp .
docker run -i --rm --name mcp-electricity-price \
  -e MYSQL_HOST=你的主机地址 \
  -e MYSQL_PORT=3306 \
  -e MYSQL_USER=你的用户名 \
  -e MYSQL_PASSWORD=你的密码 \
  -e MYSQL_DATABASE=electricity \
  electricity-price-mcp
```

## API 工具

### query_electricity_prices
查询电价数据
- 参数：
  - region_name: 地区名称（可选）
  - price_date: 价格日期（可选，格式：2024年12月）
- 返回：
  - total: 查询结果总数
  - data: 电价数据列表
    - 地区: 地区名称
    - 日期: 价格日期
    - 用电类型1: 用电类型信息
    - 用电类型2: 用电类型信息
    - 电压等级: 电压等级信息
    - 电价信息:
      - 峰时电价
      - 尖峰电价
      - 谷时电价
      - 平时电价
      - 深谷电价

## 使用示例

在 Claude 中，你可以这样使用工具：

```json
{
  "tool": "query_electricity_prices",
  "arguments": {
    "region_name": "北京",
    "price_date": "2024年01月"
  }
}
```

## 注意事项

1. 安全性
   - 请妥善保管数据库凭证
   - 不要在公共场合分享配置文件
   - 建议使用环境变量而不是硬编码凭证

2. 故障排除
   - 检查数据库连接是否正常
   - 确保数据库中有数据
   - 查看日志输出了解详细错误信息
   - Windows 和 Mac 的命令有所不同，请使用对应系统的命令

## 许可证

MIT
