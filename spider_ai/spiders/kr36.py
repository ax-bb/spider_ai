import os
from pathlib import Path

import scrapy
from scrapy_playwright.page import PageMethod


class Kr36Spider(scrapy.Spider):
    name = "kr36"
    allowed_domains = ["36kr.com"]

    # 与 settings.py 的 _AUTH_FILE 一致，指向项目根，保证 Cookie 保存/读取闭环
    auth_file = str(Path(__file__).resolve().parents[2] / "auth_state.json")

    async def start(self):
        # Scrapy 2.13+ 引擎只调用 start()，旧式 start_requests() 不再被调用
        self.logger.info("[kr36] start() called")
        url = "https://36kr.com/information/AI"

        if self._has_valid_auth():
            # ✅ 有Cookie：仍走Playwright Handler，但不打开页面（纯HTTP模式）
            # scrapy-playwright 在未设置 playwright=True 时，会自动退化为普通HTTP请求
            yield scrapy.Request(url=url, callback=self.parse, dont_filter=True)
        else:
            # ✅ 无Cookie：走浏览器验证流程
            yield scrapy.Request(
                url=url,
                callback=self.parse_with_verification,
                meta={
                    "playwright": True,
                    "playwright_context": "default",
                    "playwright_include_page": True,
                    # 在 scrapy-playwright 取 response body 之前等待 JS 渲染完成，
                    # 这样 response.text 才包含 div.information-flow-item 列表
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "div.information-flow-item", timeout=20000),
                    ],
                },
            )


    async def parse_with_verification(self, response):
        """首次请求：用浏览器过验证并保存Cookie"""
        page = response.meta["playwright_page"]
        try:
            # 等待真实内容已在 playwright_page_methods 中完成
            self.logger.info("[kr36] 验证通过，保存Cookie...")

            # 保存完整认证状态（Cookie + LocalStorage）
            await page.context.storage_state(path=self.auth_file)
        finally:
            await page.close()

        for item in self._extract_articles(response):
            yield item

    def parse(self, response):
        """后续请求：纯Scrapy解析，若被拦截则自动降级"""
        # ✅ 检测是否被反爬拦截（返回了验证页而非真实内容）
        if not response.css("div.information-flow-item"):
            self.logger.warning("[kr36] Cookie失效，降级到浏览器重新验证...")
            # 删除旧Cookie文件
            if os.path.exists(self.auth_file):
                os.remove(self.auth_file)
            # 重新发起浏览器验证请求
            yield scrapy.Request(
                url=response.url,
                callback=self.parse_with_verification,
                meta={
                    "playwright": True,
                    "playwright_context": "default",
                    "playwright_include_page": True,
                    "playwright_page_methods": [
                        PageMethod("wait_for_selector", "div.information-flow-item", timeout=20000),
                    ],
                },
                dont_filter=True,
            )
            return

        yield from self._extract_articles(response)

    def _extract_articles(self, response):
        """统一提取逻辑"""
        for article in response.css("div.information-flow-item"):
            url = article.css("a.article-item-title::attr(href)").get("")
            title = article.css("a.article-item-title::text").get("").strip()
            desc = article.css("a.article-item-description::text").get("").strip()
            if url and title:
                yield {
                    "url": response.urljoin(url),
                    "title": title,
                    "description": desc,
                }

    def _has_valid_auth(self):
        """检查auth_state.json是否存在且非空"""
        return os.path.exists(self.auth_file) and os.path.getsize(self.auth_file) > 10