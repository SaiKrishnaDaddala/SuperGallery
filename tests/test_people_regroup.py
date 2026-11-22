"""One person split into several People groups is brought back together, carefully."""
import numpy as np

from app import people

from test_discovery import library  # noqa: F401  (shared fixture)

RNG = np.random.default_rng(7)


def unit(v):
    v = np.asarray(v, dtype='float32')
    return v / np.linalg.norm(v)


def identity():
    return unit(RNG.normal(size=128))


def near(base, similarity):
    """A face whose similarity to `base` is about `similarity`."""
    other = RNG.normal(size=128)
    other -= (other @ base) * base
    return unit(similarity * base + np.sqrt(1 - similarity ** 2) * unit(other))


def group(c, add, faces, name='', owner='alice', photos=None):
    """A People group with one face per photo (or in the given photos)."""
    proto = unit(np.mean(faces, axis=0))
    pid = c.execute('INSERT INTO people(owner,name,prototype,created) VALUES(?,?,?,1)', (owner, name, proto.tobytes())).lastrowid
    for i, f in enumerate(faces):
        if photos:
            fid = photos[i]
        else:
            fid, _ = add(f'{owner}-{pid}-{i}.jpg', owner)
        r = c.execute('SELECT * FROM files WHERE id=?', (fid,)).fetchone()
        c.execute("INSERT OR REPLACE INTO face_index VALUES(?,?,?,?,'done',0)", (fid, r['path'], r['mtime'], r['size']))
        c.execute('INSERT INTO faces(file_id,person_id,embedding,crop,score) VALUES(?,?,?,?,1)', (fid, pid, unit(f).tobytes(), b''))
    return pid


def person_of(c, pid):
    row = c.execute('SELECT id FROM people WHERE id=?', (pid,)).fetchone()
    return row[0] if row else None


def test_split_groups_of_one_person_are_joined(library):  # noqa: F811
    c, add, _ = library
    me = identity()
    big = group(c, add, [near(me, .8) for _ in range(6)])
    glasses = group(c, add, [near(me, .8) for _ in range(3)])
    stranger = group(c, add, [near(identity(), .8) for _ in range(4)])
    result = people.regroup()
    assert result['people_joined'] == 1
    assert person_of(c, glasses) is None
    assert c.execute('SELECT COUNT(*) FROM faces WHERE person_id=?', (big,)).fetchone()[0] == 9
    assert c.execute('SELECT COUNT(*) FROM faces WHERE person_id=?', (stranger,)).fetchone()[0] == 4
    proto = np.frombuffer(c.execute('SELECT prototype FROM people WHERE id=?', (big,)).fetchone()[0], dtype='float32')
    assert float(proto @ me) > .9  # average of all nine faces


def test_people_in_the_same_photo_are_never_joined(library):  # noqa: F811
    c, add, _ = library
    twin = identity()
    shared, _ = add('together.jpg')
    a = group(c, add, [near(twin, .8), near(twin, .8)], photos=[shared, add('a2.jpg')[0]])
    b = group(c, add, [near(twin, .8), near(twin, .8)], photos=[shared, add('b2.jpg')[0]])
    assert people.regroup()['people_joined'] == 0
    assert person_of(c, a) and person_of(c, b)


def test_names_and_answers_are_respected(library):  # noqa: F811
    c, add, _ = library
    look = identity()
    ravi = group(c, add, [near(look, .8) for _ in range(3)], name='Ravi')
    kiran = group(c, add, [near(look, .8) for _ in range(3)], name='Kiran')
    unnamed = group(c, add, [near(look, .8) for _ in range(3)])
    people.not_same(unnamed, ravi)
    people.not_same(unnamed, kiran)
    assert people.regroup()['people_joined'] == 0
    assert person_of(c, ravi) and person_of(c, kiran) and person_of(c, unnamed)


def test_a_named_group_takes_in_its_unnamed_parts(library):  # noqa: F811
    c, add, _ = library
    look = identity()
    small_named = group(c, add, [near(look, .8) for _ in range(2)], name='Amma')
    larger = group(c, add, [near(look, .8) for _ in range(5)])
    people.regroup()
    assert person_of(c, larger) is None
    assert c.execute('SELECT name FROM people WHERE id=?', (small_named,)).fetchone()[0] == 'Amma'
    assert c.execute('SELECT COUNT(*) FROM faces WHERE person_id=?', (small_named,)).fetchone()[0] == 7


def test_libraries_stay_separate(library):  # noqa: F811
    c, add, _ = library
    look = identity()
    mine = group(c, add, [near(look, .8) for _ in range(3)], owner='alice')
    theirs = group(c, add, [near(look, .8) for _ in range(3)], owner='bob')
    assert people.regroup()['people_joined'] == 0
    assert person_of(c, mine) and person_of(c, theirs)


def test_unsure_pairs_are_asked_not_joined(library):  # noqa: F811
    c, add, _ = library
    look = identity()
    fa = [near(look, .95) for _ in range(4)]
    # Faces about 0.5 alike across the two groups: between LINK_ASK and LINK_JOIN.
    centre = near(look, .55)
    fb = [near(centre, .95) for _ in range(4)]
    link = float(np.mean(np.stack(fa) @ np.stack(fb).T))
    assert people.LINK_ASK <= link < people.LINK_JOIN, link
    a, b = group(c, add, fa), group(c, add, fb)
    assert people.regroup()['people_joined'] == 0
    items = people.suggestions()['items']
    assert [{x['a']['id'], x['b']['id']} for x in items] == [{a, b}]
    people.not_same(a, b)
    assert people.suggestions()['items'] == []
    # "Yes, same person" is a merge; the answer about other groups follows the survivor.
    people.merge(b, a)
    assert person_of(c, b) is None


def test_one_photo_groups_are_hidden_until_asked(library):  # noqa: F811
    c, add, _ = library
    group(c, add, [identity() for _ in range(1)])
    keep = group(c, add, [near(identity(), .9) for _ in range(1)], name='Named once')
    two = group(c, add, [near(identity(), .9) for _ in range(2)])
    shown = people.listing()
    assert {p['id'] for p in shown['items']} == {keep, two} and shown['hidden'] == 1 and shown['total'] == 2
    assert people.listing(small=True)['total'] == 3


def test_a_face_matching_two_halves_of_one_person_joins_the_best(library):  # noqa: F811
    look = identity()
    side = near(look, 0)
    halves = np.stack([unit(look + .4 * side), unit(look - .4 * side)])
    assert float(halves[0] @ halves[1]) >= people.JOIN
    assert people.choose_person(look, halves, [1, 2]) in (1, 2)
    # Two genuinely different people that both resemble the face stay ambiguous: a new group is safer.
    pair = np.stack([unit(.8 * look + .6 * side), unit(.8 * look - .6 * side)])
    assert float(pair[0] @ pair[1]) < people.JOIN
    assert people.choose_person(look, pair, [1, 2]) is None



def test_repair_moves_strangers_out_of_unnamed_groups_only(library):  # noqa: F811
    c, add, _ = library
    me, stranger, ravi = identity(), identity(), identity()
    mixed = group(c, add, [near(me, .85) for _ in range(6)] + [near(stranger, .85) for _ in range(2)])
    named = group(c, add, [near(ravi, .85) for _ in range(4)] + [near(stranger, .85)], name='Ravi')
    result = people.regroup(repair=True)
    assert result['faces_moved_out'] == 2
    kept = [np.frombuffer(e, dtype='float32') for (e,) in c.execute('SELECT embedding FROM faces WHERE person_id=?', (mixed,))]
    assert len(kept) == 6 and all(float(v @ me) > .7 for v in kept)
    assert c.execute('SELECT COUNT(*) FROM faces WHERE person_id=?', (named,)).fetchone()[0] == 5  # the user named it
    # The two stranger faces found each other again as their own person.
    others = c.execute('SELECT person_id, COUNT(*) FROM faces WHERE person_id NOT IN (?,?) GROUP BY person_id', (mixed, named)).fetchall()
    assert [n for _, n in others] == [2]


def test_big_groups_do_not_swallow_noisy_faces(library):  # noqa: F811
    """A large group's average face looks generic; a blurry stranger can resemble it without resembling any real face."""
    c, add, _ = library
    me = identity()
    big = group(c, add, [near(me, .75) for _ in range(40)])
    proto = unit(np.frombuffer(c.execute('SELECT prototype FROM people WHERE id=?', (big,)).fetchone()[0], dtype='float32'))
    blurry = near(proto, .66)  # close to the average...
    link = float(np.mean([blurry @ np.frombuffer(e, dtype='float32') for (e,) in c.execute('SELECT embedding FROM faces WHERE person_id=?', (big,))]))
    assert float(blurry @ proto) >= people.JOIN and link < people.LINK_JOIN  # ...but not like the actual faces
    lone = group(c, add, [blurry])
    assert people.regroup()['people_joined'] == 0
    assert person_of(c, lone)
