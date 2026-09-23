import scrapy
from scrapy import Selector

from spider_ai.items import Bitai


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
