"""Pure tests for pan_self_learning/monitor.py (no Odoo needed).

    python -m pytest -q tests/
"""
import importlib.util
import pathlib
from urllib.parse import parse_qs, urlsplit

_PATH = pathlib.Path(__file__).resolve().parents[1] / 'pan_self_learning' / 'monitor.py'
_spec = importlib.util.spec_from_file_location('monitor', _PATH)
monitor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(monitor)


def test_no_drift_when_versions_match():
    assert monitor.find_drift([('base', '19.0.1.3', '19.0.1.3')]) == []


def test_drift_of_26_november():
    # Juffermans prod: database on 40.2.2, Mail Pro code on disk 42.1.0.
    drift = monitor.find_drift([
        ('pan_mail_pro', '19.0.40.2.2', '19.0.42.1.0'),
        ('base', '19.0.1.3', '19.0.1.3'),
    ])
    assert drift == [('pan_mail_pro', '19.0.40.2.2', '19.0.42.1.0')]


def test_missing_code_counts_as_drift():
    assert monitor.find_drift([('gone', '19.0.1.0', None)]) == [('gone', '19.0.1.0', '')]


def test_drift_sorted_by_name():
    drift = monitor.find_drift([('b', '1', '2'), ('a', '1', '2')])
    assert [d[0] for d in drift] == ['a', 'b']


def test_describe():
    assert monitor.describe([]) == 'ok'
    assert monitor.describe([('pan_mail_pro', '19.0.40.2.2', '19.0.42.1.0')]) == \
        'drift: pan_mail_pro 19.0.40.2.2->19.0.42.1.0'
    assert monitor.describe([('gone', '19.0.1.0', '')]) == 'drift: gone 19.0.1.0->missing'


def test_describe_is_capped():
    many = [('module_%03d' % i, '19.0.1.0', '19.0.2.0') for i in range(50)]
    text = monitor.describe(many)
    assert len(text) <= monitor.MAX_MSG
    assert text.endswith('...')


def test_push_url_up_and_down():
    base = 'https://kuma.example/api/push/abc123?status=up&msg=OK&ping='
    up = parse_qs(urlsplit(monitor.push_url(base, [])).query)
    assert up['status'] == ['up'] and up['msg'] == ['ok']
    down = parse_qs(urlsplit(monitor.push_url(base, [('m', '1', '2')])).query)
    assert down['status'] == ['down'] and down['msg'] == ['drift: m 1->2']
    assert urlsplit(monitor.push_url(base, [])).path == '/api/push/abc123'


def test_push_url_keeps_other_params():
    url = monitor.push_url('https://kuma.example/api/push/t?extra=1', [])
    assert parse_qs(urlsplit(url).query)['extra'] == ['1']


def test_valid_push_url():
    assert monitor.valid_push_url('https://kuma.example/api/push/t')
    assert monitor.valid_push_url('http://10.0.0.5:3001/api/push/t')
    assert not monitor.valid_push_url('')
    assert not monitor.valid_push_url(None)
    assert not monitor.valid_push_url('kuma.example/api/push/t')
    assert not monitor.valid_push_url('file:///etc/passwd')
