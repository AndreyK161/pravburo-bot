from state import USER_ACTIVITY, touch


def test_touch_starts_at_one_for_new_user():
    assert touch(1) == 1
    assert USER_ACTIVITY[1] == 1


def test_touch_increments_on_each_call():
    touch(2)
    touch(2)
    assert touch(2) == 3


def test_touch_tracks_users_independently():
    touch(1)
    touch(1)
    touch(2)
    assert USER_ACTIVITY[1] == 2
    assert USER_ACTIVITY[2] == 1
