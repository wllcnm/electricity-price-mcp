import asyncio
import logging
import os
import json
from typing import List
import aiomysql
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# 日志配置
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("electricity_price_mcp_server")

class ElectricityPriceMCPServer:
    def __init__(self):
        logger.info("Initializing Electricity Price MCP server...")
        self.app = Server("electricity_price_mcp_server")
        self.setup_tools()
        self.pool = None
        logger.info("Server initialized successfully")

    async def ensure_db_pool(self):
        """确保数据库连接池已创建"""
        if self.pool is None:
            logger.debug("Creating database connection pool")
            self.pool = await aiomysql.create_pool(
                host=os.environ.get("MYSQL_HOST", "localhost"),
                port=int(os.environ.get("MYSQL_PORT", 3306)),
                user=os.environ.get("MYSQL_USER", "root"),
                password=os.environ.get("MYSQL_PASSWORD", ""),
                db=os.environ.get("MYSQL_DATABASE", "electricity"),
                autocommit=True
            )

    async def query_electricity_prices(self, region_name: str = None, price_date: str = None) -> List[dict]:
        """查询电价数据"""
        await self.ensure_db_pool()
        
        query = "SELECT * FROM electricity_prices WHERE 1=1"
        params = []
        
        if region_name:
            query += " AND region_name = %s"
            params.append(region_name)
        
        if price_date:
            query += " AND price_date = %s"
            params.append(price_date)
        
        logger.debug(f"Executing query: {query} with params: {params}")
        
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                result = await cur.fetchall()
                return result

    def setup_tools(self):
        logger.info("Setting up tools...")
        
        @self.app.list_tools()
        async def list_tools() -> List[Tool]:
            logger.debug("Listing available tools")
            tools = [
                Tool(
                    name="query_electricity_prices",
                    description="查询电价数据。当用户询问某个地区或某个时间段的电价信息时使用此工具。"
                              "支持按地区名称和日期（格式：2024年12月）进行查询。"
                              "返回的数据包括：峰谷电价、电压等级、用电类型等信息。"
                              "适用场景：查询特定地区的电价、比较不同时期的电价变化、了解峰谷电价差异等。"
                              "示例查询：查询北京2024年1月的电价、获取上海最新的峰谷电价等。",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "region_name": {
                                "type": "string",
                                "description": "地区名称，例如：北京、上海等"
                            },
                            "price_date": {
                                "type": "string",
                                "description": "价格日期，格式必须为：2024年12月"
                            }
                        }
                    }
                )
            ]
            logger.debug(f"Available tools: {[tool.name for tool in tools]}")
            return tools

        @self.app.call_tool()
        async def call_tool(name: str, arguments: dict) -> List[TextContent]:
            logger.info(f"Calling tool: {name} with arguments: {arguments}")
            
            try:
                if name == "query_electricity_prices":
                    region_name = arguments.get("region_name")
                    price_date = arguments.get("price_date")
                    
                    logger.debug(f"Querying electricity prices for region: {region_name}, date: {price_date}")
                    results = await self.query_electricity_prices(region_name, price_date)
                    
                    if not results:
                        return [TextContent(type="text", text="未找到符合条件的电价数据")]
                    
                    formatted_results = []
                    for row in results:
                        formatted_result = {
                            "地区": row["region_name"],
                            "日期": row["price_date"],
                            "用电类型1": {
                                "值": row["electricity_type1_value"],
                                "描述": row["electricity_type1_desc"]
                            },
                            "用电类型2": {
                                "值": row["electricity_type2_value"],
                                "描述": row["electricity_type2_desc"]
                            },
                            "电压等级": {
                                "值": row["voltage_level_value"],
                                "描述": row["voltage_level_desc"]
                            },
                            "电价信息": {
                                "峰时电价": float(row["peak_price"]) if row["peak_price"] else None,
                                "尖峰电价": float(row["sharp_peak_price"]) if row["sharp_peak_price"] else None,
                                "谷时电价": float(row["valley_price"]) if row["valley_price"] else None,
                                "平时电价": float(row["normal_price"]) if row["normal_price"] else None,
                                "深谷电价": float(row["deep_valley_price"]) if row["deep_valley_price"] else None
                            }
                        }
                        formatted_results.append(formatted_result)
                    
                    response = {
                        "total": len(formatted_results),
                        "data": formatted_results
                    }
                    
                    return [TextContent(type="text", text=f"查询结果：{json.dumps(response, ensure_ascii=False, indent=2)}")]
                
                else:
                    logger.warning(f"Unknown tool: {name}")
                    return [TextContent(type="text", text=f"未知的工具: {name}")]
                    
            except Exception as e:
                logger.error(f"Error calling tool {name}: {str(e)}", exc_info=True)
                return [TextContent(type="text", text=f"查询出错: {str(e)}")]

    async def run(self):
        logger.info("Starting Electricity Price MCP server...")
        
        async with stdio_server() as (read_stream, write_stream):
            try:
                logger.debug("Initializing MCP server")
                await self.app.run(
                    read_stream,
                    write_stream,
                    self.app.create_initialization_options()
                )
            except Exception as e:
                logger.error(f"Server error: {str(e)}", exc_info=True)
                raise
            finally:
                if self.pool:
                    logger.debug("Closing database connection pool")
                    self.pool.close()
                    await self.pool.wait_closed()

def main():
    logger.info("Starting main function")
    server = ElectricityPriceMCPServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main() 