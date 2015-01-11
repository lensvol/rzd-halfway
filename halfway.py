# -*- coding: utf-8 -*-

import arrow
import click
import requests
import time
from lxml import etree as ET


class RZDException(Exception):
    pass


human_readable_names = {
    u'Москва': ('МОСКВА', 2000000),
    u'Петрозаводск': ('ПЕТРОЗАВОДСК-ПАСС', 2004300),
    u'Тверь': ('ТВЕРЬ', 2004600),
    u'Нижний Новгород': ('НИЖНИЙ НОВГОРОД МОСКОВ', 2060001),
    u'Вологда': ('ВОЛОГДА 1', 2010030),
    u'Казань': ('КАЗАНЬ ПАСС', 2060500),
    u'Санкт-Петербург': ('САНКТ-ПЕТЕРБУРГ', 2004000),
    u'Ярославль': ('ЯРОСЛАВЛЬ-ГОРОД', 2010000),
    u'Минск': ('МИНСК', 2100000),
    u'Киев': ('КИЕВ', 2200000),
}


def rzd_async_request(structure_id, layer_id, use_json=False, **kwargs):
    rid = None
    session_id = None
    params = {
        'STRUCTURE_ID': structure_id,
        'layer_id': layer_id,
    }
    params.update(kwargs)

    s = requests.Session()
    resp = s.get(
        'http://pass.rzd.ru/timetable/public/ru',
        params=params,
    )

    if not use_json:
        xml = ET.fromstring(resp.content)
        rid = xml.find('rid').text
    else:
        json_resp = resp.json()
        if json_resp['result'] == 'Error':
            raise RZDException(json_resp['message'])
        rid = json_resp['rid']
        session_id = json_resp.get('SESSION_ID')

    result_params = dict(params)
    result_params['rid'] = rid
    if session_id:
        result_params['SESSION_ID'] = session_id

    time.sleep(3)
    resp = s.get(
        'http://pass.rzd.ru/timetable/public/ru',
        params=result_params,
    )
    if not use_json:
        xml_resp = ET.fromstring(resp.content)
        error_node = xml_resp.find('./Error')
        if error_node is not None:
            raise RZDException(error_node.text)
        return xml_resp
    else:
        json_resp = resp.json()
        if json_resp['result'] == 'Error':
            raise RZDException(json_resp['message'])
        return json_resp


def choose_station(stations):
    click.echo(u'Пожалуйста, уточнитет станцию.')
    for i, s in enumerate(stations):
        click.echo(u'{0}. {1} ({2})'.format(i + 1, s['station'], s['code']))
    choice = click.prompt(u'Номер нужной станции', default=1)
    return stations[choice - 1]


def retrieve_station(name):
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
    return result_station


def get_station(name):
    if name in human_readable_names:
        station, code = human_readable_names[name]
        return dict(station=station, code=code)
    return retrieve_station(name)


def get_train_route(train, departure, full=True):
    route = rzd_async_request(
        735,
        5451,
        train_num=train,
        date=departure.format('DD.MM.YYYY'),
    )
    stops = []
    for stop in route.xpath('./Routes/Stop'):
        wt_node = stop.find('./WaitingTime')

        stops.append({
            'code': stop.attrib['Code'],
            'station': stop.attrib['Station'],
            'waiting_time': wt_node is not None and int(wt_node.text) or 0,
        })

    return stops


def get_trip_variants(from_station, to_station, departure=None):
    if departure is None:
        departure = arrow.now()

    from_code = get_station(from_station)['code']
    to_code = get_station(to_station)['code']

    variants = {}
    raw_variants = rzd_async_request(
        735,
        5371,
        use_json=True,
        dir=0,
        tfl=3,
        checkSeats=1,
        st0=from_station.upper(),
        code0=from_code,
        dt0=departure.format('DD.MM.YYYY'),
        st1=to_station.upper(),
        code1=to_code,
        dt1=departure.replace(days=1).format('DD.MM.YYYY'),
    )
    trains = raw_variants['tp'][0]['list']

    for train in trains:
        variants[train['number']] = {
            car['typeLoc']: (car['freeSeats'], car['tariff']) for car in train['cars']
        }
    return variants


@click.command()
@click.argument('train')
def processor(train):
    stations = []
    for stop in get_train_route(train, arrow.now()):
        click.echo(
            u'{1} {0}'.format(
                stop['code'],
                stop['station'],
            ))
        stations.append(stop['station'])


if __name__ == '__main__':
    try:
        processor()
    except RZDException as e:
        click.secho(u'Ошибка: ', nl=False, fg='red')
        click.echo(e.message)
