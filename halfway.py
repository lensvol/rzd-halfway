# -*- coding: utf-8 -*-

import arrow
import click
import requests
import time
from lxml import etree as ET


human_readable_names = {
    u'Москва': 2000000,
    u'Петрозаводск': 2004300,
    u'Тверь': 2004600,
    u'Нижний Новгород': 2060001,
    u'Вологда': 2010030,
    u'Казань': 2060500,
    u'Санкт-Петербург': 2004000,
    u'Ярославль': 2010000,
    u'Минск': 2100000,
    u'Киев': 2200000,
}


def rzd_async_request(structure_id, layer_id, use_json=False, **kwargs):
    params = {
        'STRUCTURE_ID': structure_id,
        'layer_id': layer_id,
    }
    params.update(kwargs)
    rid = None

    s = requests.Session()
    resp = s.get(
        'http://pass.rzd.ru/timetable/public/ru',
        params=params,
    )
    if not use_json:
        xml = ET.fromstring(resp.content)
        rid = xml.find('rid').text

    time.sleep(3)
    result_params = {
        'STRUCTURE_ID': structure_id,
        'layer_id': layer_id,
        'rid': int(rid),
    }
    resp = s.get(
        'http://pass.rzd.ru/timetable/public/ru',
        params=result_params,
    )

    if not use_json:
        return ET.fromstring(resp.content)
    else:
        return resp.json()


def choose_station(stations):
    click.echo(u'Пожалуйста, уточнитет станцию.')
    for i, s in enumerate(stations):
        click.echo(u'{0}. {1} ({2})'.format(i + 1, s['station'], s['code']))
    choice = click.prompt(u'Номер нужной станции', default=1)
    return stations[choice - 1]


def retrieve_station_code(name):
    resp = requests.get(
        'http://pass.rzd.ru/suggester',
        params={
            'stationNamePart': name.upper(),
            'lang': 'ru',
            'compactMode': 'y',
            'lat': 3, # TODO: прояснить значение параметра
        }
    )

    stations = [dict(code=s['c'], station=s['n']) for s in resp.json()]
    stations = filter(lambda s: s['station'].startswith(name.upper()), stations)

    result_station = choose_station(stations[0:5])
    return result_station[0]


def get_station_code(name):
    if name in human_readable_names:
        return human_readable_names[name]

    return retrieve_station_code(name)


def get_train_route(train, departure, full=True):
    route = rzd_async_request(
        735,
        5451,
        train_num=train,
        date=departure.format('DD.MM.YYYY'),
    )
    stops = []
    for stop in route.xpath('./Routes/Stop'):
        stops.append({
            'code': stop.attrib['Code'],
            'station': stop.attrib['Station'],
        })

    return stops


@click.command()
@click.argument('train')
def processor(train):
    for stop in get_train_route(train, arrow.now()):
        click.echo(
            u'{1} {0}'.format(
                stop['code'],
                stop['station'],
            ))

if __name__ == '__main__':
    processor()
