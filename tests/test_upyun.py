#! /usr/bin/env python
# -*- coding: utf-8 -*-

import io
import os
import sys
import uuid

if sys.version_info >= (2, 7):
    import unittest
else:
    import unittest2 as unittest

curpath = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, curpath)

def b(s):
    PY3 = sys.version_info[0] == 3

    if PY3:
        return s.encode('utf-8')
    else:
        return s

import upyun

BUCKET = os.getenv('UPYUN_BUCKET')
USERNAME = os.getenv('UPYUN_USERNAME')
PASSWORD = os.getenv('UPYUN_PASSWORD')
API = os.getenv('UPYUN_API')
SOURCE = os.getenv('UPYUN_SOURCE') or 'F'
BUCKET_TYPE = os.getenv('UPYUN_BUCKET_TYPE') or 'F'


class DjangoFile(io.BytesIO):
    def __len__(self):
        return len(self.getvalue())

def rootpath():
    return "/pysdk-%s/" % uuid.uuid4().hex


class TestUpYun(unittest.TestCase):

    def setUp(self):
        self.up = upyun.UpYun(BUCKET, username=USERNAME, password=PASSWORD, timeout=100,
                              endpoint=upyun.ED_TELECOM, human=False, api=API, multipart=False)
        self.root = rootpath()
        self.up.mkdir(self.root)

    def tearDown(self):
        for item in ['test.png', 'test.txt', 'test/test.png', 'test', 'test_m.png', 'test/test_m.png']:
            try:
                self.up.delete(self.root + item)
            except upyun.UpYunServiceException:
                pass
        self.up.delete(self.root)
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getinfo(self.root)
        self.assertEqual(se.exception.status, 404)

    def test_auth_failed(self):
        with self.assertRaises(upyun.UpYunServiceException) as se:
            upyun.UpYun('bucket', 'username', 'password').getinfo('/')
        self.assertEqual(se.exception.status, 401)

    def test_client_exception(self):
        with self.assertRaises(upyun.UpYunClientException):
            e = upyun.UpYun('bucket', 'username', 'password', timeout=3)
            e.endpoint = 'e.api.upyun.com'
            e.getinfo('/')

    def test_root(self):
        res = self.up.getinfo('/')
        self.assertDictEqual(res, {'file-type': 'folder'})

    def test_usage(self):
        res = self.up.usage()
        self.assertGreaterEqual(int(res), 0)

    @unittest.skipUnless(BUCKET_TYPE == 'F', 'only support file bucket')
    def test_put_directly(self):
        self.up.put(self.root + 'test.txt', 'abcdefghijklmnopqrstuvwxyz\n')
        res = self.up.get(self.root + 'test.txt')
        self.assertEqual(res, 'abcdefghijklmnopqrstuvwxyz\n')
        self.up.delete(self.root + 'test.txt')
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getinfo(self.root + 'test.txt')
            self.assertEqual(se.exception.status, 404)

    def test_put(self):
        with open('tests/test.png', 'rb') as f:
            res = self.up.put(self.root + 'test.png', f, checksum=False)
        self.assertDictEqual(res, {'frames': '1', 'width': '1000',
                                   'file-type': 'PNG', 'height': '410'})

        res = self.up.getinfo(self.root + 'test.png')
        self.assertIsInstance(res, dict)
        self.assertEqual(res['file-size'], '13001')
        self.assertEqual(res['file-type'], 'file')
        self.up.delete(self.root + 'test.png')
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getinfo(self.root + 'test.png')
        self.assertEqual(se.exception.status, 404)
        self.assertEqual(len(se.exception.request_id), 66)

    def test_put_with_checksum(self):
        with open('tests/test.png', 'rb') as f:
            before = self.up._UpYun__make_content_md5(f)
            self.up.put(self.root + 'test.png', f, checksum=True)
        with open('tests/get.png', 'wb') as f:
            self.up.get(self.root + 'test.png', f)
        with open('tests/get.png', 'rb') as f:
            after = self.up._UpYun__make_content_md5(f)
        self.assertEqual(before, after)
        os.remove('tests/get.png')
        self.up.delete(self.root + 'test.png')
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getinfo(self.root + 'test.png')
        self.assertEqual(se.exception.status, 404)

    def test_mkdir(self):
        self.up.mkdir(self.root + 'test')
        res = self.up.getinfo(self.root + 'test')
        self.assertIsInstance(res, dict)
        self.assertEqual(res['file-type'], 'folder')
        self.up.delete(self.root + 'test')
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getinfo(self.root + 'test')
        self.assertEqual(se.exception.status, 404)

    def test_getlist(self):
        self.up.mkdir(self.root + 'test')
        with open('tests/test.png', 'rb') as f:
            self.up.put(self.root + 'test.png', f, checksum=False)
        res = self.up.getlist(self.root)
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 2)
        if res[0]['type'] == 'F':
            a, b = res[0], res[1]
        else:
            a, b = res[1], res[0]
        self.assertDictEqual(a, {'time': a['time'], 'type': 'F',
                                 'name': 'test', 'size': '0'})
        self.assertDictEqual(b, {'time': b['time'], 'type': 'N',
                                 'name': 'test.png', 'size': '13001'})
        self.up.delete(self.root + 'test')
        self.up.delete(self.root + 'test.png')
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getlist(self.root + 'test')
        self.assertEqual(se.exception.status, 404)

    def test_delete(self):
        with open('tests/test.png', 'rb') as f:
            self.up.put(self.root + 'test/test.png', f, checksum=False)
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.delete(self.root + 'test')
        self.assertIn(se.exception.status, [503, 403])
        self.up.delete(self.root + 'test/test.png')
        self.up.delete(self.root + 'test')
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getinfo(self.root + 'test')
        self.assertEqual(se.exception.status, 404)

    def test_put_with_gmkerl(self):
        headers = {'x-gmkerl-rotate': '90'}
        with open('tests/test.png', 'rb') as f:
            res = self.up.put(self.root + 'test.png', f, checksum=False,
                              headers=headers)
        self.assertDictEqual(res, {'frames': '1', 'width': '410',
                                   'file-type': 'PNG', 'height': '1000'})

        self.up.delete(self.root + 'test.png')
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getinfo(self.root + 'test.png')
        self.assertEqual(se.exception.status, 404)

    def test_handler_progressbar(self):
        class ProgressBarHandler(object):
            def __init__(self, totalsize, params):
                params.assertEqual(totalsize, 13001)
                self.params = params
                self.readtimes = 0
                self.totalsize = totalsize

            def update(self, readsofar):
                self.readtimes += 1
                self.params.assertLessEqual(readsofar, self.totalsize)

            def finish(self):
                self.params.assertEqual(self.readtimes, 3)

        self.up.chunksize = 4096

        with open('tests/test.png', 'rb') as f:
            self.up.put(self.root + 'test.png', f, handler=ProgressBarHandler,
                        params=self)
        with open('tests/get.png', 'wb') as f:
            self.up.get(self.root + 'test.png', f, handler=ProgressBarHandler,
                        params=self)

        self.up.delete(self.root + 'test.png')
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getinfo(self.root + 'test.png')
        self.assertEqual(se.exception.status, 404)

    def test_purge(self):
        res = self.up.purge('/test.png')
        self.assertListEqual(res, [])
        res = self.up.purge(['/test.png', 'test/test.png'])
        self.assertListEqual(res, [])
        res = self.up.purge('/test.png', 'invalid.upyun.com')
        self.assertListEqual(res, ['/test.png'])

    @unittest.skipUnless(BUCKET_TYPE == 'F', 'only support file bucket')
    def test_filelike_object_flask(self):
        class ProgressBarHandler(object):
            def __init__(self, totalsize, params):
                params.assertEqual(totalsize, 13)

            def finish(self):
                pass

        f = io.BytesIO(b('www.upyun.com'))
        res = self.up.put(self.root + 'test.txt', f, checksum=True,
                          handler=ProgressBarHandler, params=self)
        self.assertDictEqual(res, {})
        f.close()

    @unittest.skipUnless(BUCKET_TYPE == 'F', 'only support file bucket')
    def test_filelike_object_django(self):
        f = DjangoFile(b('www.upyun.com'))
        res = self.up.put(self.root + 'test.txt', f, checksum=False)
        self.assertDictEqual(res, {})
        f.close()

    @unittest.skipUnless(BUCKET_TYPE == 'F', 'only support file bucket')
    def test_put_multipart(self):
        self.up.open_multipart()
        with open('tests/test_m.png', 'rb') as f:
            res = self.up.put(self.root + 'test_m.png', f, checksum=False)
        self.assertDictEqual(res, {'frames': 1, 'width': 140, 'height': 25})

        res = self.up.getinfo(self.root + 'test_m.png')
        self.assertIsInstance(res, dict)
        self.assertEqual(res['file-size'], '2745')
        self.assertEqual(res['file-type'], 'file')
        self.up.delete(self.root + 'test_m.png')
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getinfo(self.root + 'test_m.png')
        self.assertEqual(se.exception.status, 404)
        self.assertEqual(len(se.exception.request_id), 66)
        self.up.close_multipart()

    @unittest.skipUnless(BUCKET_TYPE == 'F' or SOURCE == 'F', 'only support file bucket \
                        and you have to specify video source')
    def test_pretreat(self):
        tasks = [{'type': 'hls', 'hls_time': 6, 'bitrate': '500',}]
        source = SOURCE
        notify_url = ""
        ids = self.up.pretreat(tasks, source, notify_url)
        self.assertIsInstance(ids, list)
        tasks = self.up.status(ids)
        for taskid in ids:
            self.assertIn(taskid, tasks.keys())


class TestUpYunHumanMode(TestUpYun):

    def setUp(self):
        self.up = upyun.UpYun(BUCKET, username=USERNAME, password=PASSWORD, timeout=100,
                              endpoint=upyun.ED_TELECOM, human=True, api=API, multipart=False)
        self.root = rootpath()
        self.up.mkdir(self.root)

