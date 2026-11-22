"""Places from GPS, favourites and On this day."""
import datetime as dt

from PIL import Image

from app import places, queries, scope

from test_discovery import library  # noqa: F401  (shared fixture)


def photo_with_gps(path, lat, lon):
    def dms(v):
        v = abs(v)
        d = int(v)
        m = int((v - d) * 60)
        return (float(d), float(m), round((v - d - m / 60) * 3600, 2))
    exif = Image.Exif()
    exif.get_ifd(0x8825).update({1: 'N' if lat >= 0 else 'S', 2: dms(lat), 3: 'E' if lon >= 0 else 'W', 4: dms(lon)})
    Image.new('RGB', (64, 48), 'teal').save(path, exif=exif)


def test_town_names_come_from_the_bundled_list():
    assert places.name_places([(17.385, 78.4867), (51.5072, -0.1276), (-33.8688, 151.2093)]) == [
        'Hyderabad|Telangana|India', 'London|England|United Kingdom', 'Sydney|New South Wales|Australia']
    middle_of_ocean = places.name_places([(-30.0, -120.0)])[0]
    assert middle_of_ocean.startswith('|')  # no town nearby: no town name is made up


def test_photos_get_their_place_and_can_be_found_by_it(library):  # noqa: F811
    c, add, tmp = library
    fid, path = add('trip.jpg', data=b'')
    photo_with_gps(path, 17.4, 78.48)
    st = path.stat()
    c.execute('UPDATE files SET size=?, mtime=? WHERE id=?', (st.st_size, st.st_mtime, fid))
    plain, plain_path = add('plain.jpg', data=b'')
    Image.new('RGB', (10, 10)).save(plain_path)
    assert places.gps(path) == (17.4, 78.48)
    assert places.gps(plain_path) is None
    assert places.update() == {'places': 1, 'checked': 2}
    assert places.update() == {'places': 0}  # each photo is read once
    assert [x['name'] for x in queries.query({'place': 'Hyderabad|Telangana|India'})['items']] == ['trip.jpg']
    assert [x['name'] for x in queries.query({'text': 'hyderabad'})['items']] == ['trip.jpg']
    listing = places.listing()['places']
    assert listing == [{'key': 'Hyderabad|Telangana|India', 'name': 'Hyderabad', 'area': 'Telangana, India', 'count': 1, 'cover': fid}]
    scope.set_owners(['someone-else'])
    assert places.listing()['places'] == []


def test_favourites(library):  # noqa: F811
    c, add, _ = library
    a, _ = add('a.jpg')
    b, _ = add('b.jpg')
    queries.set_favorites([a], True)
    assert [x['name'] for x in queries.query({'fav': True})['items']] == ['a.jpg']
    assert {x['name']: x['fav'] for x in queries.query({})['items']} == {'a.jpg': 1, 'b.jpg': 0}
    queries.set_favorites([a, b], True)
    queries.set_favorites([a], False)
    assert [x['name'] for x in queries.query({'fav': True})['items']] == ['b.jpg']
    c.execute('DELETE FROM files WHERE id=?', (b,))
    assert c.execute('SELECT COUNT(*) FROM favorites').fetchone()[0] == 0


def test_on_this_day(library):  # noqa: F811
    c, add, _ = library
    today = dt.date.today()
    def at(year, kind=None, name=None):
        fid, _ = add(name or f'{year}-{kind}.jpg')
        when = dt.datetime(year, today.month, min(today.day, 28), 12).timestamp()
        if today.day > 28:
            when = dt.datetime(year, today.month, 28, 12).timestamp()
        c.execute('UPDATE files SET ts=?, kind=? WHERE id=?', (when, kind, fid))
        return fid
    if today.day > 28:
        return  # the fixture dates above would not land on today's date
    at(today.year - 1, 'camera')
    at(today.year - 3, 'camera')
    at(today.year - 3, 'screenshot')
    at(today.year, 'camera')
    queries.invalidate()
    years = queries.on_this_day()['years']
    assert [(y['years_ago'], [i['name'] for i in y['items']]) for y in years] == [
        (1, [f'{today.year - 1}-camera.jpg']), (3, [f'{today.year - 3}-camera.jpg'])]


def test_messaging_images_and_screenshots_are_not_opened_for_gps(library, monkeypatch):  # noqa: F811
    c, add, _ = library
    wa, _ = add('IMG-20260101-WA0007.jpg')
    shot, _ = add('Screenshot_20260101-101010.png')
    opened = []
    monkeypatch.setattr(places, 'gps', lambda path: opened.append(path))
    assert places.update() == {'places': 0}
    assert opened == []
    assert {r[0] for r in c.execute('SELECT geo FROM files WHERE id IN (?,?)', (wa, shot))} == {-1}
