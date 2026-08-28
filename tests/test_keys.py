"""Key naming, serialization and the sequence/combo parsers."""

import pytest
from pynput.keyboard import Key, KeyCode

from kenansautoclicker.keys import (NAMED_KEYS, key_from_str, key_to_label,
                                    key_to_str, parse_combo, parse_sequence,
                                    parse_token)


def test_named_keys_skip_platform_specific_members():
    """Key.insert does not exist on macOS. Building the table eagerly used to
    crash the app on launch there, so the table must only hold real members."""
    for name, key in NAMED_KEYS.items():
        assert key is not None, name


def test_function_keys_present():
    assert NAMED_KEYS["f6"] is Key.f6
    assert parse_token("f6") is Key.f6


@pytest.mark.parametrize("key", [Key.f6, Key.space, Key.enter,
                                 KeyCode.from_char("a"), KeyCode.from_char("Z")])
def test_key_codec_round_trip(key):
    assert key_from_str(key_to_str(key)) == key


def test_key_from_str_falls_back_on_garbage():
    assert key_from_str("total nonsense") == Key.f6
    assert key_from_str("") == Key.f6


def test_key_to_label_is_readable():
    assert key_to_label(KeyCode.from_char("a")) == "A"
    assert key_to_label(Key.f6) == "F6"
    assert key_to_label(None) == "None"


def test_parse_sequence_space_and_comma():
    assert len(parse_sequence("q w e r")) == 4
    assert len(parse_sequence("q,w,e")) == 3
    assert len(parse_sequence("q, w ,  e")) == 3


def test_parse_sequence_empty():
    assert parse_sequence("") == []
    assert parse_sequence("   ") == []


def test_parse_combo():
    combo = parse_combo("ctrl+shift+a")
    assert len(combo) == 3
    assert combo[0] is Key.ctrl
    assert combo[1] is Key.shift


def test_parse_combo_tolerates_spaces_and_trailing_plus():
    assert len(parse_combo(" ctrl + a ")) == 2
    assert len(parse_combo("ctrl+")) == 1


def test_named_keys_are_case_insensitive():
    assert parse_token("CTRL") is Key.ctrl
    assert parse_token("Enter") is Key.enter
