import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from main import app
from db.base import Base
from db.session import get_db
from models import IsotopicSignature, User, SignatureLike
from services.media import mp4_duration
from services.auth import hash_password, session_key
from fakeredis import FakeRedis
from redis.exceptions import ConnectionError as RedisConnectionError
from core.config import SESSION_TTL_SECONDS

IMAGE = Path('static/images/default_signature.png').read_bytes()
VIDEO = Path('static/videos/default_signature.mp4').read_bytes()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis(decode_responses=True)
        patch('services.auth.redis_client', self.redis).start()
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        @event.listens_for(self.engine, 'connect')
        def foreign_keys(conn, record):
            conn.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all([User(id=1, username='current', password=hash_password('p')), User(id=2, username='other', password=hash_password('p'))])
            db.flush()
            for id, owner, status, c13 in [(1,1,'published',-18.2),(2,2,'published',-13.5),(3,2,'draft',None),(4,1,'deleted',-20)]:
                db.add(IsotopicSignature(id=id, creator_id=owner, title=f'PRIVATE_TITLE_{id}', status=status,
                                        delta_c13=c13, image_file='default_signature.png', video_file='default_signature.mp4'))
            db.commit()
        def override_db():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        response = self.client.post('/auth/login', json={'username': 'current', 'password': 'p'})
        self.assertEqual(response.status_code, 200, response.text)
        self.put = patch('core.minio_client.minio_client.put_object').start()
        self.remove = patch('core.minio_client.minio_client.remove_object').start()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        patch.stopall()
        self.engine.dispose()

    def create(self, data=None, image=IMAGE, video=VIDEO):
        return self.client.post('/api/services/', data=data or {'title': 'New service'}, files={
            'image': ('фото.рус', image, 'image/png'), 'video': ('видео.рус', video, 'video/mp4')})

    def publish(self, id, **extra):
        return self.client.put(f'/api/services/{id}/publish', json={
            'description':'Research', 'delta_n15':9.4, 'delta_c13':-18.2, **extra})

    def test_filtered_list_and_creator(self):
        data = self.client.get('/api/services/').json()
        self.assertEqual([(s['id'],s['is_creator']) for s in data], [(1,1),(2,0)])
        self.assertEqual([s['id'] for s in self.client.get('/api/services/?c13_max=-15').json()], [1])
        self.assertEqual(self.client.get('/api/services/?filter=TITLE_2').json()[0]['id'], 2)
        self.assertEqual(self.client.get('/api/services/?c13_max=bad').status_code, 422)

    def test_feed_navigation_and_wrap(self):
        for url, id in [('/feed',1),('/feed/1',1),('/feed/1?next=true',2),('/feed/2?next=true',1)]:
            self.assertEqual(self.client.get('/api/services'+url).json()['id'], id)
        for id in (3,4,999):
            response = self.client.get(f'/api/services/feed/{id}?next=true')
            self.assertEqual(response.status_code, 404)
            self.assertNotIn('PRIVATE_TITLE',response.text)

    def test_empty_feed(self):
        with Session(self.engine) as db:
            db.query(IsotopicSignature).filter_by(status='published').update({'status':'deleted'});db.commit()
        self.assertEqual(self.client.get('/api/services/feed').status_code,404)

    def test_create_publish_like_delete_lifecycle(self):
        self.assertIsNone(self.client.get('/api/services/draft').json())
        response = self.create();self.assertEqual(response.status_code,201,response.text)
        id = response.json()['id']
        self.assertRegex(response.json()['image_file'],r'^[0-9a-f]{32}\.png$')
        self.assertRegex(response.json()['video_file'],r'^[0-9a-f]{32}\.mp4$')
        self.assertEqual(self.client.get('/api/services/draft').json()['id'],id)
        self.assertEqual(self.create().status_code,409)
        with Session(self.engine) as db:
            record = db.get(IsotopicSignature,id)
            self.assertIsNotNone(record.created_at);self.assertIsNone(record.formed_at)
        response=self.publish(id);self.assertEqual(response.status_code,200,response.text)
        self.assertIsNotNone(response.json()['formed_at'])
        self.assertIsNone(self.client.get('/api/services/draft').json())
        self.assertEqual(self.publish(id).status_code,200)
        for value, count in [(1,1),(1,1),(0,0),(0,0),(1,1)]:
            response=self.client.post(f'/api/services/{id}/like',json={'like':value})
            self.assertEqual(response.json(),{'like':value,'likes_count':count})
        self.assertEqual(self.client.get(f'/api/services/feed/{id}').json()['is_liked'],1)
        self.assertEqual(self.client.delete(f'/api/services/{id}').status_code,204)
        self.assertEqual(self.client.get(f'/api/services/feed/{id}').status_code,404)
        self.assertEqual(self.publish(id).status_code,404)
        with Session(self.engine) as db:
            record=db.get(IsotopicSignature,id)
            self.assertEqual(record.status,'deleted');self.assertIsNotNone(record.completed_at)
            self.assertEqual(db.query(SignatureLike).filter_by(signature_id=id).count(),1)

    def test_ownership(self):
        self.assertEqual(self.client.delete('/api/services/2').status_code,403)
        self.assertEqual(self.publish(3).status_code,403)
        self.assertEqual(self.publish(2).status_code,403)
        with Session(self.engine) as db:self.assertEqual(db.get(IsotopicSignature,2).status,'published')

    def test_system_fields_rejected(self):
        for field,value in [('id',10),('status','published'),('creator_id',2),('moderator_id',2),('created_at','2000-01-01'),('formed_at','2000-01-01'),('completed_at','2000-01-01')]:
            with self.subTest(field=field):
                self.assertEqual(self.create({'title':'Injected',field:str(value)}).status_code,422)
        id=self.create().json()['id']
        self.assertEqual(self.publish(id,status='deleted').status_code,422)
        self.assertEqual(self.publish(id,creator_id=2).status_code,422)
        self.assertEqual(self.client.put(f'/api/services/{id}/publish', content='{"description":"x","delta_n15":Infinity,"delta_c13":-18}', headers={'Content-Type':'application/json'}).status_code,422)
        with Session(self.engine) as db:self.assertEqual(db.get(IsotopicSignature,id).status,'draft')

    def test_like_only_published_and_strict_binary(self):
        for id in (3,4,999):self.assertEqual(self.client.post(f'/api/services/{id}/like',json={'like':1}).status_code,404)
        for value in (-1,2,'1',True):
            self.assertEqual(self.client.post('/api/services/1/like',json={'like':value}).status_code,422)

    def test_files_required_and_validated_before_storage(self):
        self.assertEqual(self.client.post('/api/services/',data={'title':'No files'}).status_code,422)
        self.assertEqual(self.create(image=b'not an image').status_code,422)
        self.assertEqual(self.create(video=b'not a video').status_code,422)
        self.put.assert_not_called()
        self.assertIsNone(self.client.get('/api/services/draft').json())

    def test_short_video_duration(self):
        import struct
        long_video = bytearray(VIDEO)
        offset=long_video.index(b'mvhd')+4
        scale=struct.unpack_from('>I',long_video,offset+12)[0]
        struct.pack_into('>I',long_video,offset+16,scale*61)
        self.assertEqual(mp4_duration(long_video),61)
        self.assertEqual(self.create(video=bytes(long_video)).status_code,422)
        self.put.assert_not_called()

    def test_storage_failure_does_not_persist_draft(self):
        self.put.side_effect=RuntimeError('unavailable')
        self.assertEqual(self.create().status_code,503)
        self.assertIsNone(self.client.get('/api/services/draft').json())

    def test_second_upload_failure_cleans_first(self):
        self.put.side_effect=[None,RuntimeError('second upload failed')]
        self.assertEqual(self.create().status_code,503)
        self.assertGreaterEqual(self.remove.call_count,2)
        self.assertIsNone(self.client.get('/api/services/draft').json())

    def test_database_failure_cleans_both_files(self):
        # Simulate a concurrent draft insertion winning at commit.
        with patch('services.isotopic_signatures.Session.commit',side_effect=IntegrityError('insert',{},Exception('race'))):
            self.assertEqual(self.create().status_code,409)
        self.assertEqual(self.remove.call_count,2)
        self.assertIsNone(self.client.get('/api/services/draft').json())

    def test_register_conflicts_and_auth(self):
        data={'username':'new','email':'new@example.org','password':'my secret'}
        response=self.client.post('/api/users/register',json=data)
        self.assertEqual(response.status_code,201,response.text)
        self.assertNotIn('password',response.json())
        with Session(self.engine) as db:self.assertTrue(db.get(User,response.json()['id']).password.startswith('scrypt$'))
        self.assertEqual(self.client.post('/api/users/register',json=data).status_code,409)
        self.assertEqual(self.client.post('/api/users/register',json={**data,'username':'othernew'}).status_code,409)
        self.assertEqual(self.client.post('/api/users/register',json={**data,'id':50}).status_code,422)
        self.assertEqual(self.client.post('/api/users/login',json={'username':'new','password':'my secret'}).status_code,200)
        self.assertEqual(self.client.post('/api/users/logout').status_code,204)

    def test_database_constraints(self):
        with Session(self.engine) as db:
            db.add(IsotopicSignature(title='Duplicate',creator_id=2,status='draft'))
            with self.assertRaises(IntegrityError):db.commit()
            db.rollback()
            db.add(IsotopicSignature(title='Invalid',creator_id=1,status='unknown'))
            with self.assertRaises(IntegrityError):db.commit()
            db.rollback()
            db.delete(db.get(User,1))
            with self.assertRaises(IntegrityError):db.commit()

    def test_spa_shell_and_legacy_pages(self):
        for path in ['/', '/login', '/api/pages/isotopic_signatures/list',
                     '/api/pages/isotopic_signatures/feed/1', '/api/pages/isotopic_signatures/draft',
                     '/api/pages/isotopic_signatures/unavailable']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn('/static/js/spa.js', response.text)
            self.assertNotIn('PRIVATE_TITLE', response.text)
        self.assertEqual(self.client.post('/isotopic_signatures/2/delete').status_code,404)
        self.assertEqual(self.client.post('/api/pages/isotopic_signatures/draft').status_code,405)

    def test_guest_read_and_rejected_writes(self):
        self.client.cookies.clear()
        for base in ('/services', '/api/services'):
            records = self.client.get(base).json()
            self.assertEqual([(s['is_creator'], s['is_liked']) for s in records], [(0,0),(0,0)])
            self.assertEqual(self.client.get(base+'/feed').status_code,200)
            self.assertEqual(self.client.get(base+'/draft').status_code,401)
            for method, path, kwargs in [
                ('POST', base, {'data':{'title':'Guest'}, 'files':{'image':('a.png',IMAGE,'image/png'),'video':('a.mp4',VIDEO,'video/mp4')}}),
                ('PUT',base+'/1',{'json':{'description':'x','delta_n15':1,'delta_c13':1}}),
                ('DELETE',base+'/1',{}), ('POST',base+'/1/like',{'json':{'like':1}})]:
                self.assertEqual(self.client.request(method,path,**kwargs).status_code,401)
        self.assertEqual(self.client.get('/auth/me').status_code,401)
        self.put.assert_not_called()

    def test_login_logout_and_session_replay(self):
        token = self.client.cookies.get('session_id')
        self.assertEqual(self.redis.get(session_key(token)), '1')
        self.assertNotIn(token, session_key(token))
        self.assertGreater(self.redis.ttl(session_key(token)), 0)
        self.assertLessEqual(self.redis.ttl(session_key(token)), SESSION_TTL_SECONDS)
        # A fresh HTTP client uses the same Redis session store.
        other_client = TestClient(app)
        other_client.cookies.set('session_id',token)
        self.assertEqual(other_client.get('/auth/me').json()['id'],1)
        other_client.close()
        response = self.client.post('/auth/logout')
        self.assertEqual(response.status_code,204)
        self.assertEqual(response.content,b'')
        self.assertIn('Max-Age=0',response.headers['set-cookie'])
        self.assertIsNone(self.redis.get(session_key(token)))
        self.client.cookies.set('session_id',token)
        self.assertEqual(self.client.get('/auth/me').status_code,401)
        self.assertEqual(self.client.post('/auth/logout').status_code,204)

    def test_session_rotation_expiry_and_invalid_cookie(self):
        previous = self.client.cookies.get('session_id')
        response = self.client.post('/auth/login',json={'username':'current','password':'p'})
        self.assertEqual(response.status_code,200)
        self.assertIn('HttpOnly',response.headers['set-cookie'])
        self.assertIn('SameSite=lax',response.headers['set-cookie'])
        self.assertIn('Max-Age=',response.headers['set-cookie'])
        token = self.client.cookies.get('session_id')
        self.assertNotEqual(previous,token)
        self.assertIsNone(self.redis.get(session_key(previous)))
        self.redis.expire(session_key(token), 0)
        self.assertEqual(self.client.get('/services/draft').status_code,401)
        for bad in ('invalid-token', 'x'*129, previous):
            self.client.cookies.clear()
            self.client.cookies.set('session_id',bad)
            self.assertEqual(self.client.get('/auth/me').status_code,401)
            self.assertEqual(self.client.get('/services').status_code,200)

    def test_redis_failure_does_not_grant_access_or_fake_logout(self):
        token = self.client.cookies.get('session_id')
        with patch('services.auth.redis_client.get', side_effect=RedisConnectionError):
            self.assertEqual(self.client.get('/services/draft').status_code, 503)
        with patch('services.auth.redis_client.delete', side_effect=RedisConnectionError):
            self.assertEqual(self.client.post('/auth/logout').status_code, 503)
            self.assertEqual(self.client.cookies.get('session_id'), token)
        with patch('services.auth.redis_client.pipeline', side_effect=RedisConnectionError):
            self.assertEqual(self.client.post('/auth/login', json={'username':'current','password':'p'}).status_code, 503)
        self.assertEqual(self.client.get('/auth/me').status_code, 200)

    def test_wrong_password_unknown_and_legacy_accounts(self):
        self.client.cookies.clear()
        with Session(self.engine) as db:
            db.add(User(username='legacy',password='legacy-account')); db.commit()
        for name, password in [('current','bad'),('missing','p'),('legacy','legacy-account')]:
            response = self.client.post('/auth/login',json={'username':name,'password':password})
            self.assertEqual(response.status_code,401)
            self.assertEqual(response.json(),{'detail':'Invalid username or password'})
            self.assertNotIn('session_id',self.client.cookies)
        self.assertEqual(self.client.post('/auth/login',json={'username':'current','password':'p','user_id':2}).status_code,422)

    def test_two_users_isolation_and_session_author(self):
        first = self.create().json()['id']
        self.client.post('/auth/login',json={'username':'other','password':'p'})
        self.assertEqual(self.client.get('/services/draft').json()['id'],3)
        self.assertEqual(self.client.delete(f'/services/{first}').status_code,403)
        self.assertEqual(self.publish(first).status_code,403)
        self.client.delete('/services/3')
        second = self.create().json()['id']
        with Session(self.engine) as db:
            self.assertEqual(db.get(IsotopicSignature,first).creator_id,1)
            self.assertEqual(db.get(IsotopicSignature,second).creator_id,2)
        self.client.post('/services/1/like',json={'like':1})
        self.assertEqual(self.client.get('/services/feed/1').json()['is_liked'],1)
        self.client.post('/auth/login',json={'username':'current','password':'p'})
        self.assertEqual(self.client.get('/services/draft').json()['id'],first)
        self.assertEqual(self.client.get('/services/feed/1').json()['is_liked'],0)

    def test_password_whitespace_preserved(self):
        data = {'username':'spaces','password':' p '}
        self.assertEqual(self.client.post('/auth/register',json=data).status_code,201)
        self.assertEqual(self.client.post('/auth/login',json={**data,'password':'p'}).status_code,401)
        self.assertEqual(self.client.post('/auth/login',json=data).status_code,200)

    def test_openapi_and_canonical_publish(self):
        schema = self.client.get('/openapi.json').json()
        self.assertEqual(schema['components']['securitySchemes']['SessionCookie']['in'],'cookie')
        for path in ('/auth/register','/auth/login','/auth/logout','/services','/services/feed','/services/draft','/services/{id}','/services/{id}/like'):
            self.assertIn(path,schema['paths'])
        self.assertEqual(schema['paths']['/services/draft']['get']['security'],[{'SessionCookie':[]}])
        for path in ('/services', '/services/feed', '/services/feed/{id}'):
            self.assertEqual(schema['paths'][path]['get']['security'], [{}, {'SessionCookie':[]}])
        for path, method in (('/services', 'post'), ('/services/{id}', 'put'),
                             ('/services/{id}', 'delete'), ('/services/{id}/like', 'post')):
            self.assertEqual(schema['paths'][path][method]['security'], [{'SessionCookie':[]}])
        self.assertEqual(self.client.get('/docs').status_code,200)
        id = self.create().json()['id']
        response = self.client.put(f'/services/{id}',json={'description':'Research','delta_n15':9.4,'delta_c13':-18.2})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['status'],'published')
        self.assertNotIn('success',response.json().values())
        self.assertEqual(self.client.get('/services').headers['cache-control'],'no-store')

    def test_update_publication_preserves_author_date_and_likes(self):
        id = self.create().json()['id']
        original = self.publish(id).json()
        self.client.post(f'/services/{id}/like', json={'like':1})
        payload = {'title':'Updated title', 'description':'Updated research', 'delta_n15':10.5, 'delta_c13':-16}
        for _ in range(2):
            response = self.client.put(f'/services/{id}', json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            data = response.json()
            for key, value in payload.items():
                self.assertEqual(data[key], value)
            self.assertEqual(data['formed_at'], original['formed_at'])
            self.assertEqual(data['creator_id'], original['creator_id'])
            self.assertEqual(data['status'], 'published')
            self.assertEqual(data['likes_count'], 1)
        self.assertIsNone(self.client.get('/services/draft').json())
        self.assertEqual(self.client.put(f'/services/{id}', json={**payload, 'title':'   '}).status_code,422)
        self.assertEqual(self.create().status_code,201)

    def test_cookie_spelling_from_assignment_and_revocation(self):
        token = self.client.cookies.get('session_id')
        self.client.cookies.clear()
        headers = {'Cookie': 'session-id=' + token}
        self.assertEqual(self.client.get('/auth/me', headers=headers).status_code,200)
        self.assertEqual(self.client.get('/services/draft', headers=headers).status_code,200)
        response = self.client.post('/auth/logout', headers=headers)
        self.assertEqual(response.status_code,204)
        self.assertIn('session-id=', '\n'.join(response.headers.get_list('set-cookie')))
        self.assertEqual(self.client.get('/auth/me', headers=headers).status_code,401)
        self.assertIsNone(self.redis.get(session_key(token)))


if __name__ == '__main__':unittest.main()
