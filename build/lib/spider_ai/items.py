# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

from dataclasses import dataclass

import scrapy


@dataclass
class SpiderAiItem:
    # define the fields for your item here like:
    # name: str | None = None
    pass


class Bitai(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    description = scrapy.Field()