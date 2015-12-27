# -*- coding: utf-8 -*-
import io
import os
import sys
import uuid
import json

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
SECRET = os.getenv('UPYUN_SECRET')
FAST = False


def rootpath():
    return '/pysdk-%s/' % uuid.uuid4().hex


class DjangoFile(io.BytesIO):
    def __len__(self):
        return len(self.getvalue())


class TestUpYun(unittest.TestCase):
    def setUp(self):
        self.up = upyun.UpYun(BUCKET, USERNAME, PASSWORD, SECRET,
                              timeout=100, endpoint=upyun.ED_AUTO)
        self.root = rootpath()
        self.up.mkdir(self.root)
        with open('tests/bigfile.txt', 'w') as f:
            f.seek(10*1024*1024)
            f.write('abcdefghijklmnopqrstuvwxyz')

    def tearDown(self):
        for item in ['test.png', 'test.txt',
                     'test/test.png', 'test', 'test.mp4']:
            try:
                self.up.delete(self.root + item)
            except upyun.UpYunServiceException:
                pass
        self.up.delete(self.root)
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getinfo(self.root)
        self.assertEqual(se.exception.status, 404)
        os.remove('tests/bigfile.txt')

    def test_getenv_info(self):
        upyun.UpYun(None).getinfo('/')

    def test_debug_func(self):
        up = upyun.UpYun(BUCKET, USERNAME, PASSWORD, SECRET,
                         endpoint=upyun.ED_AUTO, debug=True)
        up.getinfo('/')
        os.remove('debug.log')

    def test_auth_failed(self):
        with self.assertRaises(upyun.UpYunServiceException) as se:
            upyun.UpYun('bucket', 'username', 'password').getinfo('/')
        self.assertEqual(se.exception.status, 401)

    def test_multipart_secret_failed(self):
        with self.assertRaises(upyun.UpYunServiceException) as se:
            e = upyun.UpYun(BUCKET, USERNAME, PASSWORD,
                            secret='secret', timeout=100)
            with open('tests/test.png', 'rb') as f:
                e.put(self.root + 'test.png', f,
                      checksum=False, multipart=True)
        self.assertEqual(se.exception.status, 401)

    def test_form_secret_failed(self):
        with self.assertRaises(upyun.UpYunServiceException) as se:
            e = upyun.UpYun(BUCKET, USERNAME, PASSWORD,
                            secret='secret', timeout=100)
            with open('tests/test.png', 'rb') as f:
                e.put(self.root + 'test.png', f, checksum=False, form=True)
        self.assertEqual(se.exception.status, 401)

    def test_client_exception(self):
        with self.assertRaises(upyun.UpYunClientException):
            e = upyun.UpYun('bucket', username='username',
                            password='password', timeout=100)
            e.up_rest.endpoint = 'e.api.upyun.com'
            e.getinfo('/')
        with self.assertRaises(upyun.UpYunClientException):
            e = upyun.UpYun('bucket', username='username',
                            password='password', timeout=100)
            e.secret = None
            with open('tests/test.png', 'rb') as f:
                e.put(self.root + 'test.png', f, checksum=False, form=True)

    def test_root(self):
        res = self.up.getinfo('/')
        self.assertDictEqual(res, {'file-type': 'folder'})

    def test_usage(self):
        res = self.up.usage()
        self.assertGreaterEqual(int(res), 0)

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
            before = upyun.make_content_md5(f)
            self.up.put(self.root + 'test.png', f, checksum=True)
        with open('tests/get.png', 'wb') as f:
            self.up.get(self.root + 'test.png', f)
        with open('tests/get.png', 'rb') as f:
            after = upyun.make_content_md5(f)
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

    def test_cd(self):
        with self.assertRaises(upyun.UpYunClientException) as se:
            self.up.cd('test//fail')
        res = self.up.cd(self.root + 'test')
        self.assertEqual(res, 0)

        res = self.up.usage()
        self.assertGreaterEqual(int(res), 0)
        self.up.mkdir('testcd')
        res = self.up.getinfo('testcd')
        self.assertIsInstance(res, dict)

        self.up.put('testcd/test.txt', 'abcdefghijklmnopqrstuvwxyz\n')
        res = self.up.get('testcd/test.txt')
        self.assertEqual(res, 'abcdefghijklmnopqrstuvwxyz\n')
        res = self.up.getlist('testcd')
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 1)

        self.up.delete('testcd/test.txt')
        self.up.delete('testcd')
        self.up.cd(self.root)
        self.up.delete('test')
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

    @unittest.skipUnless(FAST, 'The transmition speed must be fast')
    def test_getlargelist(self):
        ldir = self.root + 'largelist/'
        for i in range(1200):
            self.up.put('%s%s_test.txt' % (ldir, uuid.uuid4().hex), 'a')
        res = self.up.getlist(ldir, limit=500, order='asc')
        self.assertIsInstance(res, list)
        self.assertEqual(len(res), 1200)
        folder_list = [x['name'] for x in res]
        for item in folder_list:
            self.up.delete(ldir + item)
        self.up.delete(ldir)
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

        self.up.up_rest.chunksize = 4096

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
        self.assertListEqual(res, [u'/test.png'])

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

    def test_filelike_object_django(self):
        f = DjangoFile(b('www.upyun.com'))
        res = self.up.put(self.root + 'test.txt', f, checksum=False)
        self.assertDictEqual(res, {})
        f.close()

    @unittest.skipUnless(SECRET, 'you have to specify bucket secret')
    def test_put_form(self):
        def __put(up, multi, kwargs={}):
            with open('tests/test.png', 'rb') as f:
                res = self.up.put(self.root + 'test.png', f,
                                  checksum=False, form=True,
                                  multipart=multi, **kwargs)
                self.assertEqual(res['code'], 200)
                self.assertEqual(res['image-height'], 410)
                self.assertEqual(res['image-width'], 1000)
                self.assertEqual(res['image-frames'], 1)
                self.assertEqual(res['image-type'], 'PNG')

            res = self.up.getinfo(self.root + 'test.png')
            self.assertIsInstance(res, dict)
            self.assertEqual(res['file-size'], '13001')
            self.assertEqual(res['file-type'], 'file')
            self.up.delete(self.root + 'test.png')
            with self.assertRaises(upyun.UpYunServiceException) as se:
                self.up.getinfo(self.root + 'test.png')
            self.assertEqual(se.exception.status, 404)
            self.assertEqual(len(se.exception.request_id), 66)
        # - test conflict upload method
        up = upyun.UpYun(BUCKET, secret=SECRET,
                         timeout=100, endpoint=upyun.ED_AUTO)
        kwargs = {'allow-file-type': 'jpg,jpeg,png',
                  'notify-url': 'http://httpbin.org/post',
                  }
        __put(self.up, True)
        __put(self.up, False)
        __put(self.up, False, kwargs=kwargs)
        __put(up, True)

    @unittest.skipUnless(SECRET, 'you have to specify bucket secret')
    def test_put_multipart(self):
        def __put(up, kwargs={}):
            with open('tests/bigfile.txt', 'rb') as f:
                res = up.put(self.root + 'test_bigfile.txt', f,
                             checksum=False, multipart=True,
                             block_size=1024*1024, **kwargs)
                self.assertEqual(res['mimetype'], 'text/plain')

            res = up.getinfo(self.root + 'test_bigfile.txt')
            self.assertIsInstance(res, dict)
            self.assertEqual(res['file-size'], '10485786')
            self.assertEqual(res['file-type'], 'file')
            up.delete(self.root + 'test_bigfile.txt')
            with self.assertRaises(upyun.UpYunServiceException) as se:
                up.getinfo(self.root + 'test_bigfile.txt')
            self.assertEqual(se.exception.status, 404)
            self.assertEqual(len(se.exception.request_id), 66)
        kwargs = {'allow-file-type': 'txt',
                  'notify-url': 'http://httpbin.org/post',
                  }
        up = upyun.UpYun(BUCKET, secret=SECRET,
                         timeout=100, endpoint=upyun.ED_AUTO)
        up.up_multi.username = None
        up.up_multi.password = None
        __put(self.up)
        __put(self.up, kwargs=kwargs)
        __put(up)

    def test_pretreat(self):
        with open('/tmp/test.mp4', 'rb') as f:
            res = self.up.put(self.root + 'test.mp4', f, checksum=False)
        self.assertDictEqual(res, {})
        tasks = [{'type': 'probe', }, {'type': 'video', }]

        source = self.root + 'test.mp4'
        notify_url = 'http://httpbin.org/post'
        ids = self.up.pretreat(tasks, source, notify_url)
        self.assertIsInstance(ids, list)
        tasks = self.up.status(ids)
        for taskid in ids:
            self.assertIn(taskid, tasks.keys())
        self.up.delete(self.root + 'test.mp4')
        with self.assertRaises(upyun.UpYunServiceException) as se:
            self.up.getinfo(self.root + 'test.mp4')
        self.assertEqual(se.exception.status, 404)
        self.assertEqual(len(se.exception.request_id), 66)

    def test_put_sign(self):
        data = '{"code":200,' \
            '"message":"ok",' \
            '"url":"\/2015\/06\/17\/190623\/upload_QQ\u56fe\u7247201506' \
            '011111206f7c696f0920f097d7eefd750334003e.png",' \
            '"time":1434539183,' \
            '"image-width":1024,' \
            '"image-height":768,' \
            '"image-frames":1,' \
            '"image-type":"PNG",' \
            '"sign":"086c46cfedfc22bfa2e4971a77530a76"}'
        data = json.loads(data)
        secret = 'lGetaXubhGezKp89+6iuOb5IaS3='
        self.assertEqual(upyun.verify_put_sign(data, secret), True)
