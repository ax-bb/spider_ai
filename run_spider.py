from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

if __name__ == '__main__':
    settings = get_project_settings()
    process = CrawlerProcess(settings=settings)

    # 'kr36' 必须与 scrapy list 输出的名称完全一致
    print("正在尝试加载爬虫...")
    process.crawl('kr36')
    print("爬虫加载成功，开始运行...")

    process.start()
