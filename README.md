# spider_ai
## Scrapy 安装和使用
### 1. 安装Scrapy
` pip install scrapy`
### 2. 创建Scrapy项目
 >创建一个爬虫项目
`scrapy startproject spider_id`

> 创建一个爬虫爬取量子位的数据
`scrapy genspider qbitai  www.qbitai.com`

### 3. 编写spider页面解析
```
class BitaiSpider(scrapy.Spider):
    name = "bitai"
    allowed_domains = ["qbitai.com"]
    start_urls = ["https://qbitai.com"]

    # 请求添加代理
    # def start_requests(self):
    #     yield scrapy.Request(url=self.start_urls[0], meta= {'proxy':'socks5://127.0.0.1:1086'}, callback=self.parse)


    def parse(self, response):
        sel = Selector(response)
        contents = sel.css("div.picture_text")
        for content in contents:
            url = content.css("div.picture a::attr(href)").extract_first()
            if not url:
                continue
            bitai = Bitai()
            bitai['url'] = url
            bitai['title'] = content.css("div.text_box h4 a::text").extract_first()
            bitai['description'] = content.css("div.text_box p::text").extract_first()
            yield bitai
```
### 4. 编写items对数据进行解析
```
class Bitai(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    description = scrapy.Field()
```

### 5. 编写pipeline基于MySQL数据入库
```
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

# 配置对应的 tiem_pipelines 值越小越先执行
ITEM_PIPELINES = { 
   "spider_ai.pipelines.DbPipeline": 300,
}
```
6. 执行蜘蛛程序抓取数据
 `scrapy crawl bitai`

## Scrapyd+ScrapyWeb 安装使用
1. 部署Scrapyd节点

```shell
pip install scrapyd
```

```shell
[scrapyd]
bind_address = 0.0.0.0      # 允许远程访问（必须配合安全策略）
http_port    = 6800
debug        = off
logs_dir     = /var/log/scrapyd/logs
items_dir    =               # 留空，避免本地存储items
jobs_to_keep = 100          # 保留最近100个任务记录

# 若需基础认证（强烈推荐）
username     = admin
password     = your_strong_password
```

```shell
[Unit]
Description=Scrapyd Daemon
After=network.target

[Service]
Type=simple
User=scrapy
Group=scrapy
ExecStart=/usr/local/bin/scrapyd -c /etc/scrapyd/scrapyd.conf
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```shell
sudo systemctl daemon-reload
sudo systemctl enable --now scrapyd
# 验证：curl http://localhost:6800/status.json
```

2. 安装部署ScrapydWeb

```python
pip install scrapydweb
```

```shell
scrapydweb run
# 按 Ctrl+C 停止，然后编辑生成的配置文件
```

```python
# === 数据库配置（生产环境务必使用 MySQL/PostgreSQL）===
DATABASE_URL = 'mysql+pymysql://user:pass@host:3306/scrapydweb'

# === 添加 Scrapyd 节点 ===
SCRAPYD_SERVERS = [
    'admin:your_strong_password@192.168.1.10:6800',   # node-1
    'admin:your_strong_password@192.168.1.11:6800',   # node-2
    # 格式: username:password@host:port
]

# === ScrapydWeb 自身访问控制 ===
USERNAME = 'web_admin'
PASSWORD = 'web_secure_pass'

# === 日志与性能 ===
ENABLE_LOG_STATS = True       # 启用日志解析
LOG_PARSER_INTERVAL = 10      # 日志解析间隔(秒)
DELETE_RUNTIME_DAYS = 30      # 自动清理30天前的运行记录
```

```shell
[Unit]
Description=ScrapydWeb Dashboard
After=network.target mysql.service

[Service]
Type=simple
User=scrapy
Group=scrapy
WorkingDirectory=/home/scrapy
ExecStart=/usr/local/bin/scrapydweb run
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. 使用
+ 在cicd或或者部署机上安装scrapyd-client

```shell
pip install scrapyd-client 
```

+ 使用scrapyd-client 部署爬虫

```shell
[settings]
default = spider_ai.settings

[deploy]
url = http://192.168.0.222:6800/
project = spider_ai
```

```shell
scrapyd-deploy default -p spider_ai --version v20260921_002
```

