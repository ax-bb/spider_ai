# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
from datetime import datetime
from zoneinfo import ZoneInfo

import pymysql
# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


COLS = ("domain", "url_path", "title", "context", "crate_time")
BATCH_SIZE = 50


class SpiderAiPipeline:
    def process_item(self, item):
        return item


class DbPipeline:

    def __init__(self):
        # 创建MySQL链接
        self.conn = pymysql.connect(host="mysql-dev.office.cn", user="root",
                                    password="Firmoo123!!", database="scrapy_data", port=3307, charset="utf8mb4")
        self.cursor = self.conn.cursor()
        self.data = []
        self.exists = []

    def close_spider(self,spider):
        if len(self.data) > 0:
            self._write_data()
        if len(self.exists) > 0:
            self._update_exists()
        self.conn.close()

    def process_item(self, item, spider):
        url = item["url"]
        title = item["title"]
        description = item["description"]
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        domain = spider.name
        # 单条查重
        self.cursor.execute(
            "SELECT id FROM spider_data WHERE domain = %s AND title = %s LIMIT 1",
            (domain, title)
        )
        result = self.cursor.fetchone()

        if result:
            self.exists.append({
                "id": result[0],
                "domain": domain,
                "url_path": url,
                "title": title,
                "context": description,
                "crate_time": now,
            })
            if len(self.exists) >= BATCH_SIZE:
                self._update_exists()
        else:
            self.data.append((domain, url, title, description, now))
            if len(self.data) >= BATCH_SIZE:
                self._write_data()
        return item

    def _write_data(self):
        if not self.data:
            return
        try:
            self.cursor.executemany(
                'insert into spider_data(domain, url_path, title, context, crate_time) values (%s, %s, %s, %s, %s)',
                self.data
            )
            self.conn.commit()
        except Exception as e:
            print(f"[DbPipeline] 插入数据失败：{e}")
        finally:
            self.data.clear()

    def _update_exists(self):
        if not self.exists:
            return
        try:
            ids = [d["id"] for d in self.exists]
            set_parts = []
            params = []
            for col in COLS:
                case = ", ".join("WHEN %s THEN %s" for _ in self.exists)
                set_parts.append(f"`{col}` = CASE `id` {case} ELSE `{col}` END")
                for d in self.exists:
                    params.extend([d["id"], d[col]])
            in_ph = ",".join(["%s"] * len(ids))
            sql = f"UPDATE `spider_data` SET {', '.join(set_parts)} WHERE `id` IN ({in_ph})"
            params.extend(ids)
            self.cursor.execute(sql, tuple(params))  # 修复5：参数转为 tuple
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"[DbPipeline] CASE WHEN 更新失败：{e}")
        finally:
            self.exists.clear()
