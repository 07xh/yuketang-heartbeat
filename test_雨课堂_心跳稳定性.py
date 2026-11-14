"""Offline regression tests. No requests reach Changjiang Yuketang."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests

os.environ['YKT_HOME'] = tempfile.mkdtemp(prefix='ykt-test-log-')
MODULE_FILE = Path(__file__).with_name('main.py')
spec = importlib.util.spec_from_file_location('ykt_fixed', MODULE_FILE)
ykt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ykt)

class FakeResponse:
    def __init__(self, status=200, data=None, json_error=False, chunks=()):
        self.status_code = status
        self.data = data
        self.json_error = json_error
        self.chunks = chunks
    def json(self):
        if self.json_error:
            raise ValueError('invalid JSON')
        return self.data
    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError('unexpected status')
    def iter_content(self, chunk_size):
        yield from self.chunks
    def __enter__(self): return self
    def __exit__(self, *_): return False

class HeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.obj = ykt.YuketangHeartbeat(cookies={'csrftoken':'test-only'})

    def test_http_ok_without_business_success_is_not_success(self):
        self.obj.session.post = Mock(return_value=FakeResponse(data={'code': 4001, 'msg': 'invalid session'}))
        self.assertIsNone(self.obj.send_heartbeat([{'et':'play'}]))

    def test_http_ok_without_clear_ack_is_not_success(self):
        self.obj.session.post = Mock(return_value=FakeResponse(data={'message':'ok'}))
        self.assertIsNone(self.obj.send_heartbeat([{'et':'play'}]))

    def test_valid_business_success(self):
        self.obj.session.post = Mock(return_value=FakeResponse(data={'code': 0}))
        self.assertEqual(self.obj.send_heartbeat([{'et':'play'}]), {'code':0})
        self.assertEqual(self.obj.session.post.call_count,1)

    def test_redirect_and_auth_failure(self):
        for status in (302,401,403):
            with self.subTest(status=status):
                self.obj.session.post = Mock(return_value=FakeResponse(status=status))
                self.assertIsNone(self.obj.send_heartbeat([{'et':'play'}]))

    def test_html_http_200_is_not_success(self):
        self.obj.session.post = Mock(return_value=FakeResponse(json_error=True))
        self.assertIsNone(self.obj.send_heartbeat([{'et':'play'}]))

    def test_timeout_not_retried(self):
        self.obj.session.post = Mock(side_effect=requests.Timeout('mocked'))
        self.assertIsNone(self.obj.send_heartbeat([{'et':'play'}]))
        self.obj.session.post.assert_called_once()

    def test_read_only_progress_verification(self):
        self.obj.video_params={'course_id':1,'user_id':2,'classroom_id':3,'video_id':4}
        self.obj.session.get = Mock(return_value=FakeResponse(data={'code': 0,'data':{'4': {'rate':0.4}}}))
        self.assertEqual(self.obj.get_video_progress()['code'],0)
        self.obj.session.get = Mock(return_value=FakeResponse(json_error=True))
        self.assertIsNone(self.obj.get_video_progress())

    def setup_leaf(self, duration):
        self.obj.get_leaf_info = Mock(return_value={'success':True,'data':{
            'user_id':1,'course_id':2,'sku_id':3,'university_id':4,
            'name':'test video','content_info':{'media':{'ccid':'ccid-1','duration':duration}}
        }})
        self.obj.get_classroom_info=Mock(return_value=None)
        self.obj.get_video_drag_permission=Mock(return_value=None)
        self.obj.get_watermark_config=Mock(return_value=None)
        self.obj.get_video_play_url=Mock(return_value=None)

    def test_custom_completion_threshold(self):
        with patch.dict(os.environ, {'COMPLETION_THRESHOLD': '95'}):
            obj = ykt.YuketangHeartbeat(cookies={'csrftoken': 'test-only'})
        self.assertEqual(obj.completion_threshold, 0.95)
        obj.video_params = {'duration': 20, 'video_id': 123, 'user_id': 1,
                            'course_id': 2, 'sku_id': 3, 'classroom_id': 4, 'cc_id': 'cc'}
        obj.send_heartbeat = Mock(return_value={'code': 0})
        obj.get_video_progress = Mock(return_value={'code': 0, 'data': {'123': {'rate': 0.94}}})
        self.assertFalse(obj.simulate_video_watching(total_duration=20, start_position=20))
        obj.get_video_progress = Mock(return_value={'code': 0, 'data': {'123': {'rate': 0.96}}})
        self.assertTrue(obj.simulate_video_watching(total_duration=20, start_position=20))

    def test_invalid_completion_threshold(self):
        for raw in ('-1', '101', 'abc', 'nan', 'inf'):
            with self.subTest(raw=raw), patch.dict(os.environ, {'COMPLETION_THRESHOLD': raw}):
                with self.assertRaises(ValueError):
                    ykt.YuketangHeartbeat()

    def test_duration_from_leaf_data_without_playurl(self):
        self.setup_leaf(100)
        self.assertTrue(self.obj.auto_configure_from_ids(999,123,None))
        self.assertEqual(self.obj.video_params['duration'],100.0)
        self.obj.get_video_play_url.assert_not_called()

    def test_missing_playurl_fails_without_unbound_crash(self):
        self.setup_leaf(None)
        self.assertFalse(self.obj.auto_configure_from_ids(999,123,None))

    def test_elapsed_clock_not_claimed_as_completion(self):
        self.obj.video_params={'duration':20,'video_id':123,'user_id':1,'course_id':2,'sku_id':3,'classroom_id':4,'cc_id':'cc'}
        self.obj.send_heartbeat=Mock(return_value={'code':0})
        self.obj.get_video_progress=Mock(return_value={'code':0,'data':{'123': {'rate':0.4}}})
        self.assertFalse(self.obj.simulate_video_watching(total_duration=20,start_position=20))

class DurationTests(unittest.TestCase):
    def test_mvhd_v0_cross_chunk_boundary(self):
        data=(28).to_bytes(4,'big')+b'mvhd'+b'\x00\x00\x00\x00'+b'\x00'*8+(1000).to_bytes(4,'big')+(152000).to_bytes(4,'big')
        fake = FakeResponse(chunks=[data[:7],data[7:18],data[18:]])
        with patch.object(ykt.requests,'get', return_value=fake):
            self.assertEqual(ykt.getVideoDuration('https://example.test/video.mp4'),152.0)

    def test_mvhd_v1(self):
        data=b'0000mvhd'+b'\x01\x00\x00\x00'+b'\x00'*16+(1000).to_bytes(4,'big')+(152000).to_bytes(8,'big')
        fake=FakeResponse(chunks=[data])
        with patch.object(ykt.requests,'get', return_value=fake):
            self.assertEqual(ykt.getVideoDuration('https://example.test/video.mp4'),152.0)

    def test_missing_mvhd_returns_none(self):
        with patch.object(ykt.requests,'get',return_value=FakeResponse(chunks=[b'not a valid mp4'])):
            self.assertIsNone(ykt.getVideoDuration('https://example.test/video.mp4'))

if __name__ == '__main__':
    unittest.main(verbosity=2)
