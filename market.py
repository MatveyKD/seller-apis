import datetime
import logging.config
from environs import Env
from seller import download_stock

import requests

from seller import divide, price_conversion

logger = logging.getLogger(__file__)


def get_product_list(page, campaign_id, access_token):
    """Получить список товаров с сайта yandex market

    Аргументы:
        page (str): номер страницы
        campaign_id (str): идентификатор компании-продавца
        access_token (str): ключ доступа для маркетплейса

    Возвращаемые значения:
        dict: ответ от сайта
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {
        "page_token": page,
        "limit": 200,
    }
    url = endpoint_url + f"campaigns/{campaign_id}/offer-mapping-entries"
    response = requests.get(url, headers=headers, params=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def update_stocks(stocks, campaign_id, access_token):
    """Загрузить данные об остатках на сайт yandex market

        Аргументы:
            stocks (list): данные об остатках
            campaign_id (str): идентификатор компании-продавца
            access_token (str): ключ доступа для маркетплейса

        Возвращаемые значения:
            dict: ответ от сайта
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"skus": stocks}
    url = endpoint_url + f"campaigns/{campaign_id}/offers/stocks"
    response = requests.put(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def update_price(prices, campaign_id, access_token):
    """Загрузить данные об остатках на сайт yandex market

        Аргументы:
            prices (str): данные о ценах
            campaign_id (str): идентификатор компании-продавца
            access_token (str): ключ доступа для маркетплейса

        Возвращаемые значения:
            dict: ответ от сайта
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"offers": prices}
    url = endpoint_url + f"campaigns/{campaign_id}/offer-prices/updates"
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def get_offer_ids(campaign_id, market_token):
    """Получить артикулы товаров магазина яндекс маркет.

    Из общего списка товаров магазина яндекс маркет получить список артикулов.

    Аргументы:
        campaign_id (str): идентификатор компании-продавца
        market_token (str): ключ доступа для маркетплейса

    Возвращаемые значения:
        list: список артикулов
    """
    page = ""
    product_list = []
    while True:
        some_prod = get_product_list(page, campaign_id, market_token)
        product_list.extend(some_prod.get("offerMappingEntries"))
        page = some_prod.get("paging").get("nextPageToken")
        if not page:
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer").get("shopSku"))
    return offer_ids


def create_stocks(watch_remnants, offer_ids, warehouse_id):
    """Структуризовать список остатков.

    Структуризовать список остатков, добавить недостающее и привести список к единому виду.

    Аргументы:
        watch_remnants (list): данные об остатках с сайта
        offer_ids (list): список артикулов
        warehouse_id (str): ключ доступа для FBS или DBS

    Возвращаемые значения:
        list: дополненный список остатков

    Исключения:
        HTTPSConnectionPool(host='api-seller.ozon.ru', port=443): Max retries exceeded with url: /v2/product/list (Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object at 0x000001743C7C53D0>: Failed to establish a new connection: [Errno 11001] getaddrinfo failed')) Ошибка соединения.
    """
    # Уберем то, что не загружено в market
    stocks = list()
    date = str(datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z")
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append(
                {
                    "sku": str(watch.get("Код")),
                    "warehouseId": warehouse_id,
                    "items": [
                        {
                            "count": stock,
                            "type": "FIT",
                            "updatedAt": date,
                        }
                    ],
                }
            )
            offer_ids.remove(str(watch.get("Код")))
    # Добавим недостающее из загруженного:
    for offer_id in offer_ids:
        stocks.append(
            {
                "sku": offer_id,
                "warehouseId": warehouse_id,
                "items": [
                    {
                        "count": 0,
                        "type": "FIT",
                        "updatedAt": date,
                    }
                ],
            }
        )
    return stocks


def create_prices(watch_remnants, offer_ids):
    """Получить список цен.

    Из общего списка данных получить список цен в нужной форме

    Аргументы:
        watch_remnants (list): общий список данных
        offer_ids (list): список артикулов

    Возвращаемые значения:
        list: структурированный список цен

    Исключения:
        HTTPSConnectionPool(host='api-seller.ozon.ru', port=443): Max retries exceeded with url: /v2/product/list (Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object at 0x000001743C7C53D0>: Failed to establish a new connection: [Errno 11001] getaddrinfo failed')) Ошибка соединения.
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "id": str(watch.get("Код")),
                # "feed": {"id": 0},
                "price": {
                    "value": int(price_conversion(watch.get("Цена"))),
                    # "discountBase": 0,
                    "currencyId": "RUR",
                    # "vat": 0,
                },
                # "marketSku": 0,
                # "shopSku": "string",
            }
            prices.append(price)
    return prices


async def upload_prices(watch_remnants, campaign_id, market_token):
    """Структурировать список цен и отправить их на сайт озон

    Аргументы:
        watch_remnants (list): общий список данных
        client_id (str): уникальный идентификатор клиента озон
        market_token (str): уникальный идентификатор маркетплейса
    Возвращаемые значения:
        list: структурированный список цен

    Исключения:
        HTTPSConnectionPool(host='api-seller.ozon.ru', port=443): Max retries exceeded with url: /v2/product/list (Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object at 0x000001743C7C53D0>: Failed to establish a new connection: [Errno 11001] getaddrinfo failed')) Ошибка соединения.
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_prices in list(divide(prices, 500)):
        update_price(some_prices, campaign_id, market_token)
    return prices


async def upload_stocks(watch_remnants, campaign_id, market_token, warehouse_id):
    """Структурировать список остатков и отправить их на сайт яндекс маркет

    Аргументы:
        watch_remnants (list): общий список данных
        campaign_id (str): идентификатор компании-продавца
        market_token (str): уникальный идентификатор маркетплейса
        warehouse_id (str): ключ доступа для FBS или DBS
    Возвращаемые значения:
        list: список товаров с положительными остатками
        list: структурированный список остатков

    Исключения:
        HTTPSConnectionPool(host='api-seller.ozon.ru', port=443): Max retries exceeded with url: /v2/product/list (Caused by NewConnectionError('<urllib3.connection.HTTPSConnection object at 0x000001743C7C53D0>: Failed to establish a new connection: [Errno 11001] getaddrinfo failed')) Ошибка соединения.
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    stocks = create_stocks(watch_remnants, offer_ids, warehouse_id)
    for some_stock in list(divide(stocks, 2000)):
        update_stocks(some_stock, campaign_id, market_token)
    not_empty = list(
        filter(lambda stock: (stock.get("items")[0].get("count") != 0), stocks)
    )
    return not_empty, stocks


def main():
    env = Env()
    market_token = env.str("MARKET_TOKEN")
    campaign_fbs_id = env.str("FBS_ID")
    campaign_dbs_id = env.str("DBS_ID")
    warehouse_fbs_id = env.str("WAREHOUSE_FBS_ID")
    warehouse_dbs_id = env.str("WAREHOUSE_DBS_ID")

    watch_remnants = download_stock()
    try:
        # FBS
        offer_ids = get_offer_ids(campaign_fbs_id, market_token)
        # Обновить остатки FBS
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_fbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_fbs_id, market_token)
        # Поменять цены FBS
        upload_prices(watch_remnants, campaign_fbs_id, market_token)

        # DBS
        offer_ids = get_offer_ids(campaign_dbs_id, market_token)
        # Обновить остатки DBS
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_dbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_dbs_id, market_token)
        # Поменять цены DBS
        upload_prices(watch_remnants, campaign_dbs_id, market_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
