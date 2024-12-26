import dotenv
import requests
import json
import time
from typing import List, Dict
from datetime import datetime, timedelta
from dateutil import parser

import re
import openai
from openai import OpenAI

class CuboxExporter:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://cubox.pro/c/api"
        self.headers = {
            'authorization': token,
            'content-type': 'application/json',
            'origin': 'https://cubox.pro',
            'referer': f'https://cubox.pro/my/inbox?token={token}'
        }

    def get_inbox_list(self, page: int = 1, asc: bool = False) -> Dict:
        """获取收件箱列表"""
        url = f"{self.base_url}/v2/search_engine/inbox"
        
        params = {
            'asc': str(asc).lower(),
            'page': str(page),
            'filters': '',
            'archiving': 'false'
        }
        
        response = requests.get(url, params=params, headers=self.headers)
        if response.status_code != 200:
            raise Exception(f"获取列表失败: {response.status_code}")
            
        return response.json()

    def export_engine(self, engine_id: str, export_type: str = 'html') -> Dict:
        """
        导出特定ID的内容
        Args:
            engine_id: 要导出的内容ID
            export_type: 导出类型，可选 'html', 'text' 或 'md'（markdown格式）
        """
        url = f"{self.base_url}/search_engines/export"
        
        # 更新headers
        headers = {
            'authorization': self.token,
            'content-type': 'application/x-www-form-urlencoded',
            'accept': 'application/json, text/plain, */*',
            'origin': 'https://cubox.pro',
            'referer': f'https://cubox.pro/my/inbox'
        }
        
        # 构建form数据
        data = {
            'engineIds': engine_id,
            'type': export_type,  # 'html', 'text' 或 'md'
            'snap': 'false',
            'compressed': 'false'
        }
        
        print(f"Debug - 导出请求数据: {data}")
        
        response = requests.post(url, data=data, headers=headers)
        
        # 处理不同类型的响应
        if response.status_code in [200, 201]:
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                return response.json()
            elif 'text/html' in content_type or 'text/plain' in content_type:
                return {
                    'content_type': 'html' if export_type == 'html' else 'markdown',
                    'content': response.text,
                    'status': 'success'
                }
            else:
                return {
                    'content_type': content_type,
                    'content': response.text,
                    'status': 'success'
                }
        else:
            raise Exception(f"导出内容失败: {response.status_code}, {response.text[:100]}")

    def get_tag_list(self) -> Dict:
        """获取标签列表"""
        url = f"{self.base_url}/v2/tag/list"
        
        headers = {
            'authorization': self.token,
            'accept': 'application/json, text/plain, */*',
            'referer': 'https://cubox.pro/my/inbox',
            'origin': 'https://cubox.pro'
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"获取标签列表失败: {response.status_code}")
        
        return response.json()

    def summarize_content(self, content: str, client: OpenAI) -> str:
        """
        使用 DeepSeek API 对内容进行总结
        Args:
            content: 需要总结的内容
            client: OpenAI 客户端实例
        Returns:
            str: 总结后的内容
        """
        try:
            prompt = f"""请对以下内容进行简要总结，包含主要观点和关键信息：

{content}

请用中文总结，控制在300字以内。"""

            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的文章总结助手，善于提取文章重点，并进行清晰的总结。"},
                    {"role": "user", "content": prompt},
                ],
                stream=False
            )
            
            return response.choices[0].message.content
        except Exception as e:
            print(f"总结生成失败: {e}")
            return "内容总结失败"

    def export_and_summarize(self, engine_id: str, client: OpenAI, export_type: str = 'md') -> Dict:
        """
        导出内容并生成总结
        Args:
            engine_id: 要导出的内容ID
            client: OpenAI 客户端实例
            export_type: 导出类型
        """
        # 先导出内容
        export_data = self.export_engine(engine_id, export_type)
        
        # 获取内容
        content = export_data.get('content', '')
        
        # 生成总结
        summary = self.summarize_content(content, client)
        
        # 将总结添加到导出数据中
        export_data['summary'] = summary
        
        return export_data

def parse_custom_time(time_str: str) -> datetime:
    """解析自定义格式的时间字符串"""
    # 使用正则表达式解析时间字符串
    pattern = r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2}):(\d{3})\+(\d{2}):00'
    match = re.match(pattern, time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")
    
    date, time, ms, tz = match.groups()
    # 组合成标准格式的时间字符串
    formatted_time = f"{date} {time}.{ms}+{tz}00"
    return datetime.strptime(formatted_time, "%Y-%m-%d %H:%M:%S.%f%z")

def is_within_week(time_str: str) -> bool:
    """检查时间是否在一周以内"""
    try:
        item_time = parse_custom_time(time_str)
        one_week_ago = datetime.now(item_time.tzinfo) - timedelta(days=7)
        return item_time > one_week_ago
    except Exception as e:
        print(f"时间解析错误: {time_str}, 错误: {e}")
        return False

def main():
    import os
    import dotenv
    from openai import OpenAI
    from datetime import datetime
    
    dotenv.load_dotenv()
    
    # 配置
    TOKEN = os.getenv("CUBOX_TOKEN")
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    OUTPUT_DIR = "cubox_exports"
    
    # 获取当前日期作为文件名
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # 初始化 DeepSeek 客户端
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )
    
    # 创建导出器实例
    exporter = CuboxExporter(TOKEN)
    
    try:
        # 1. 获取列表
        print("正在获取收件箱列表...")
        page = 1
        all_items = []
        
        while True:
            result = exporter.get_inbox_list(page=page)
            items = result.get('data', [])
            if not items:
                break
            
            # 检查最后一个item的时间
            last_item = items[-1]
            create_time = last_item.get('createTime')
            
            # 添加调试信息
            print(f"Debug - 最后一项的创建时间: {create_time}")
            
            # 过滤出一周内的items
            current_items = [
                item for item in items 
                if is_within_week(item.get('createTime'))
            ]
            
            # 如果有符合条件的items，添加到列表中
            if current_items:
                all_items.extend(current_items)
                print(f"已获取第 {page} 页，共 {len(current_items)} 条内容")
            
            # 如果最后一个item超过���周，结束循环
            if not is_within_week(create_time):
                print("已获取到一周前的内容，停止获取")
                break
            
            page += 1
            time.sleep(2)  # 避免请求过快
        
        print(f"共获取到 {len(all_items)} 条周内的内容")
        
        # 用于存储所有文章的总结
        summaries = []
        
        # 导出内容部分的更新
        for item in all_items:
            engine_id = item.get('userSearchEngineID')
            title = item.get('title', 'untitled')
            create_time = item.get('createTime', '')
            
            if not engine_id:
                print(f"警告: 跳过无效的ID项: {title}")
                continue
                
            print(f"正在导出并总结: {title} (ID: {engine_id})")
            try:
                export_data = exporter.export_and_summarize(str(engine_id), client, 'md')
                
                # 将总结添加到列表中
                summary_entry = {
                    'title': title,
                    'create_time': create_time,
                    'summary': export_data['summary']
                }
                summaries.append(summary_entry)
                
                time.sleep(1)  # 避免请求过快
            except Exception as e:
                print(f"导出或总结失败: {e}")
        
        # 创建输出目录
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        
        # 生成汇总的 Markdown 文件
        summary_file = f"{OUTPUT_DIR}/summary_{current_date}.md"
        with open(summary_file, 'w', encoding='utf-8') as f:
            # 写入标题
            f.write(f"# Cubox 文章总结 ({current_date})\n\n")
            
            # 按时间排序
            summaries.sort(key=lambda x: x['create_time'], reverse=True)
            
            # 写入每篇文章的总结
            for idx, summary in enumerate(summaries, 1):
                f.write(f"## {idx}. {summary['title']}\n")
                # f.write(f"创建时间: {summary['create_time']}\n\n")
                f.write(f"{summary['summary']}\n\n")
                f.write("---\n\n")  # 分隔线
        
        print(f"\n总结完成！")
        print(f"总共处理: {len(all_items)} 项")
        print(f"成功总结: {len(summaries)} 项")
        print(f"汇总文件保存在: {summary_file}")
        
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()
