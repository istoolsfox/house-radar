# -*- coding: utf-8 -*-
"""城市解析测试。"""
from house_radar import cities


def test_chinese():
    assert cities.resolve_city("成都") == "cd"
    assert cities.resolve_city("上海") == "sh"


def test_abbrev():
    assert cities.resolve_city("cd") == "cd"
    assert cities.resolve_city("CD") == "cd"


def test_full_pinyin():
    assert cities.resolve_city("chengdu") == "cd"
    assert cities.resolve_city("shanghai") == "sh"
    assert cities.resolve_city("xian") == "xa"
    assert cities.resolve_city("harbin") == "hrb"


def test_unknown():
    assert cities.resolve_city("威海") == ""
    assert cities.resolve_city("") == ""
    assert cities.resolve_city("  ") == ""
