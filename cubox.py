import dotenv
import requests
import json
import time
from typing import List, Dict
from datetime import datetime, timedelta
from dateutil import parser

import re

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

    def export_engine(self, engine_id: str) -> Dict:
        """导出特定ID的内容"""
        url = f"{self.base_url}/search_engines/export"
        
        # 更新headers
        headers = {
            'authorization': self.token,
            'content-type': 'application/x-www-form-urlencoded',
            'accept': 'text/html,application/json',  # 接受HTML和JSON响应
            'origin': 'https://cubox.pro',
            'referer': f'https://cubox.pro/my/card?id={engine_id}'
        }
        
        # 构建form数据
        data = {
            'engineIds': engine_id,
            'type': 'html',
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
            elif 'text/html' in content_type:
                # 保存HTML内容
                return {
                    'content_type': 'html',
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
    dotenv.load_dotenv()
    
    # 配置
    TOKEN = os.getenv("CUBOX_TOKEN") # 替换为你的token
    OUTPUT_DIR = "cubox_exports"
    
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
            
            # 如果最后一个item超过一周，结束循环
            if not is_within_week(create_time):
                print("已获取到一周前的内容，停止获取")
                break
            
            page += 1
            time.sleep(2)  # 避免请求过快
        
        print(f"共获取到 {len(all_items)} 条���周内的内容")
        
        # 2. 导出每个内容
        print("\n开始导出内容...")
        exports = []
        
        for item in all_items:
            engine_id = item.get('userSearchEngineID')
            title = item.get('title', 'untitled')
            
            if not engine_id:
                print(f"警告: 跳过无效的ID项: {title}")
                continue
                
            print(f"正在导出: {title} (ID: {engine_id})")
            try:
                export_data = exporter.export_engine(str(engine_id))
                
                # 根据内容类型保存到不同文件
                if export_data.get('content_type') == 'html':
                    # 保存HTML到单独的文件
                    html_filename = f"{OUTPUT_DIR}/{engine_id}.html"
                    with open(html_filename, 'w', encoding='utf-8') as f:
                        f.write(export_data['content'])
                    # 在exports中只保存引用
                    export_data['content'] = f"Saved to {html_filename}"
                    
                exports.append({
                    'id': engine_id,
                    'title': title,
                    'data': export_data
                })
                time.sleep(1)
            except Exception as e:
                print(f"导出失败: {e}")
        
        # 3. 保存结果
        import os
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
            
        # 保存导出记录
        with open(f"{OUTPUT_DIR}/export_records.json", 'w', encoding='utf-8') as f:
            json.dump({
                'total_items': len(all_items),
                'successful_exports': len(exports),
                'exports': exports
            }, f, ensure_ascii=False, indent=2)
            
        print(f"\n导出完成！")
        print(f"总共处理: {len(all_items)} 项")
        print(f"成功导出: {len(exports)} 项")
        print(f"结果保存在: {OUTPUT_DIR}")
        
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()
