import asyncio
import logging
import os
import json
import re
from typing import List, Tuple
import aiomysql
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
from difflib import get_close_matches

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
        
        # 初始化用电类型映射
        self.electricity_types = {
            "type1": {
                "两部制": "两部制",
                "单一制": "单一制"
            },
            "type2": {
                "大工业": "大工业",
                "工商业": "工商业",
                "一般工商业": "一般工商业"
            }
        }
        
        # 初始化地区映射
        self.region_mapping = {
            "珠三角": "广东省珠三角五市",
            "惠州": "广东省惠州市",
            "东西两翼": "广东省东西两翼地区",
            "粤北": "广东省粤北山区",
            "江门": "广东省江门市",
            "深圳": "广东省深圳市",
            "江苏": "江苏省",
            "浙江": "浙江省",
            "上海": "上海市",
            "安徽": "安徽省",
            "北京": "北京市",
            "重庆": "重庆市",
            "福建": "福建省",
            "甘肃": "甘肃省",
            "广西": "广西壮族自治区",
            "贵州": "贵州省",
            "河北北部": "河北省北部",
            "河北南部": "河北省南部",
            "湖北": "湖北省",
            "黑龙江": "黑龙江省",
            "河南": "河南省",
            "海南": "海南省",
            "湖南": "湖南省",
            "吉林": "吉林省",
            "江西": "江西省",
            "辽宁": "辽宁省",
            "内蒙古东部": "内蒙古东部地区",
            "宁夏": "宁夏回族自治区",
            "青海": "青海省",
            "四川": "四川省",
            "山东": "山东省",
            "榆林": "陕西省榆林地区",
            "山西": "山西省",
            "陕西": "陕西省",
            "天津": "天津市",
            "新疆": "新疆维吾尔自治区",
            "云南": "云南省"
        }
        logger.info("Server initialized successfully")

    def get_similar_regions(self, region_name: str, num_matches: int = 3) -> List[str]:
        """获取相似的地区名称"""
        if not region_name:
            return []
            
        # 合并简称和全称列表
        all_names = list(self.region_mapping.keys()) + list(self.region_mapping.values())
        
        # 使用 difflib 获取相似的地区名称
        similar_regions = get_close_matches(region_name, all_names, n=num_matches, cutoff=0.4)
        return similar_regions

    def normalize_region_name(self, region_name: str) -> Tuple[str, List[str]]:
        """规范化地区名称，返回规范化后的名称和相似地区列表"""
        if not region_name:
            return None, []
            
        # 移除空白字符
        region_name = region_name.strip()
        
        # 如果已经是标准名称，直接返回
        for standard_name in self.region_mapping.values():
            if region_name == standard_name:
                return region_name, []
        
        # 尝试从简称映射到标准名称
        normalized = self.region_mapping.get(region_name)
        if normalized:
            return normalized, []
            
        # 尝试从部分匹配映射到标准名称
        for key, value in self.region_mapping.items():
            if key in region_name or region_name in key:
                return value, []
                
        # 如果找不到匹配，返回相似的地区建议
        logger.warning(f"无法找到匹配的地区名称: {region_name}")
        similar_regions = self.get_similar_regions(region_name)
        return None, similar_regions

    def normalize_date(self, date_str: str) -> Tuple[str, bool]:
        """规范化日期格式，返回规范化后的日期和是否有效
        支持的输入格式：
        - 2024年12月（标准格式）
        - 2024-12
        - 2024/12
        返回格式：2024年12月
        """
        if not date_str:
            return None, False
            
        # 移除空白字符
        date_str = date_str.strip()
        
        # 匹配年月格式
        patterns = [
            r"(\d{4})年(\d{1,2})月",  # 2024年12月
            r"(\d{4})-(\d{1,2})",     # 2024-12
            r"(\d{4})/(\d{1,2})"      # 2024/12
        ]
        
        for pattern in patterns:
            match = re.match(pattern, date_str)
            if match:
                year, month = match.groups()
                month_int = int(month)
                if 1 <= month_int <= 12:
                    # 保持两位数月份格式
                    return f"{year}年{month_int:02d}月", True
                else:
                    return None, False
                
        logger.warning(f"无法解析日期格式: {date_str}")
        return None, False

    async def ensure_db_pool(self):
        """确保数据库连接池已创建"""
        if self.pool is None:
            logger.debug("Creating database connection pool")
            self.pool = await aiomysql.create_pool(
                host=os.environ.get("MYSQL_HOST", "localhost"),
                port=int(os.environ.get("MYSQL_PORT", 3306)),
                user=os.environ.get("MYSQL_USER", "root"),
                password=os.environ.get("MYSQL_PASSWORD", ""),
                db=os.environ.get("MYSQL_DATABASE", "price_db"),
                autocommit=True
            )

    async def query_electricity_prices(self, region_name: str = None, price_date: str = None) -> Tuple[List[dict], str]:
        """查询电价数据，返回查询结果和提示信息"""
        await self.ensure_db_pool()
        
        # 规范化输入
        normalized_region, similar_regions = self.normalize_region_name(region_name)
        normalized_date, is_valid_date = self.normalize_date(price_date)
        
        # 构建提示信息
        hints = []
        if not region_name and not price_date:
            return [], "请提供查询的地区或月份。例如：查询北京的电价、查询2024年3月的电价。"
            
        if not normalized_region and region_name:
            if similar_regions:
                regions_str = "、".join(similar_regions)
                hints.append(f'未找到地区"{region_name}"，您是否想查询：{regions_str}？')
            else:
                hints.append(f'未找到地区"{region_name}"，请检查地区名称是否正确。')
                
        if price_date and not is_valid_date:
            hints.append("日期格式不正确，请使用以下格式：2024年3月、2024-3、2024/3")
            
        if hints:
            return [], "\n".join(hints)
        
        logger.debug(f"规范化后的查询参数: region={normalized_region}, date={normalized_date}")
        
        query = "SELECT * FROM electricity_prices WHERE 1=1"
        params = []
        
        if normalized_region:
            query += " AND region_name = %s"
            params.append(normalized_region)
        
        if normalized_date:
            query += " AND price_date = %s"
            params.append(normalized_date)
        
        logger.debug(f"Executing query: {query} with params: {params}")
        
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                result = await cur.fetchall()
                return result, None

    def setup_tools(self):
        logger.info("Setting up tools...")
        
        @self.app.list_tools()
        async def list_tools() -> List[Tool]:
            logger.debug("Listing available tools")
            tools = [
                Tool(
                    name="query_electricity_prices",
                    description="查询电价数据。当用户询问某个地区或某个时间段的电价信息时使用此工具。\n"
                              "支持的地区名称格式：\n"
                              "1. 标准行政区划全称（如：广东省深圳市、江苏省、北京市）\n"
                              "2. 地区简称（如：深圳=广东省深圳市，江苏=江苏省）\n"
                              "3. 特殊地区（如：珠三角=广东省珠三角五市，粤北=广东省粤北山区）\n\n"
                              "支持的日期格式：\n"
                              "1. 标准格式：2024年12月\n"
                              "2. 短横线：2024-12\n"
                              "3. 斜杠：2024/12\n\n"
                              "用电类型说明：\n"
                              "1. 用电类型1：两部制、单一制\n"
                              "2. 用电类型2：大工业、工商业、一般工商业\n\n"
                              "工具会自动将输入转换为标准格式（2024年12月）。\n"
                              "返回的数据包括：峰谷电价、电压等级、用电类型等信息。\n"
                              "适用场景：查询特定地区的电价、比较不同时期的电价变化、了解峰谷电价差异等。\n"
                              "示例查询：查询深圳2024年12月的两部制（大工业）电价。",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "region_name": {
                                "type": "string",
                                "description": "地区名称，支持标准行政区划全称、地区简称和特殊地区名称"
                            },
                            "price_date": {
                                "type": "string",
                                "description": "价格日期，标准格式：2024年12月（也支持 2024-12 或 2024/12）"
                            },
                            "electricity_type1": {
                                "type": "string",
                                "description": "用电类型1，可选值：两部制、单一制"
                            },
                            "electricity_type2": {
                                "type": "string",
                                "description": "用电类型2，可选值：大工业、工商业、一般工商业"
                            }
                        }
                    }
                ),
                Tool(
                    name="list_available_regions",
                    description="获取所有可查询的地区列表。\n"
                              "当用户想了解支持查询哪些地区的电价时使用此工具。\n"
                              "返回的数据包括所有支持查询的地区名称及其标准全称。",
                    inputSchema={
                        "type": "object",
                        "properties": {}
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
                    results, hint = await self.query_electricity_prices(region_name, price_date)
                    
                    if hint:
                        return [TextContent(type="text", text=hint)]
                        
                    if not results:
                        return [TextContent(type="text", text="未找到符合条件的电价数据")]
                    
                    # 构建 Markdown 表格
                    table_header = "| 地区 | 日期 | 用电类型 | 电压等级 | 峰时电价 | 尖峰电价 | 谷时电价 | 平时电价 | 深谷电价 |\n"
                    table_separator = "|------|------|----------|----------|----------|-----------|----------|-----------|----------|\n"
                    table_rows = []
                    
                    for row in results:
                        # 格式化电价数据，保留小数点后 4 位
                        peak_price = f"{float(row['peak_price']):.4f}" if row['peak_price'] else "-"
                        sharp_peak_price = f"{float(row['sharp_peak_price']):.4f}" if row['sharp_peak_price'] else "-"
                        valley_price = f"{float(row['valley_price']):.4f}" if row['valley_price'] else "-"
                        normal_price = f"{float(row['normal_price']):.4f}" if row['normal_price'] else "-"
                        deep_valley_price = f"{float(row['deep_valley_price']):.4f}" if row['deep_valley_price'] else "-"
                        
                        # 组合用电类型
                        electricity_type = f"{row['electricity_type1_desc']}"
                        if row['electricity_type2_desc']:
                            electricity_type += f"/{row['electricity_type2_desc']}"
                            
                        # 构建表格行
                        table_row = f"| {row['region_name']} | {row['price_date']} | {electricity_type} | {row['voltage_level_desc']} | {peak_price} | {sharp_peak_price} | {valley_price} | {normal_price} | {deep_valley_price} |\n"
                        table_rows.append(table_row)
                    
                    # 组合完整的表格
                    table = f"\n查询结果（共 {len(results)} 条记录）：\n\n" + table_header + table_separator + "".join(table_rows)
                    
                    # 添加说明
                    explanation = "\n\n说明：\n" + \
                                "1. 电价单位：元/千瓦时\n" + \
                                "2. '-' 表示该时段无电价数据\n" + \
                                "3. 峰谷时段的具体划分请参考当地电力部门规定"
                    
                    return [TextContent(type="text", text=table + explanation)]
                
                elif name == "list_available_regions":
                    # 构建地区列表表格
                    table_header = "| 地区简称 | 标准全称 |\n"
                    table_separator = "|----------|----------|\n"
                    table_rows = []
                    
                    for short_name, full_name in sorted(self.region_mapping.items()):
                        table_row = f"| {short_name} | {full_name} |\n"
                        table_rows.append(table_row)
                    
                    table = f"\n支持查询的地区列表：\n\n" + table_header + table_separator + "".join(table_rows)
                    return [TextContent(type="text", text=table)]
                
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