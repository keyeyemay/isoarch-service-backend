import unittest
import json
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

IMAGE = Path('static/images/default_signature.png').read_bytes()
VIDEO = Path('static/videos/default_signature.mp4').read_bytes()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        @event.listens_for(self.engine, 'connect')
        def foreign_keys(conn, record):
            conn.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all([User(id=1, username='current', password='p'), User(id=2, username='other', password='p')])
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
        self.put = patch('core.minio_client.minio_client.put_object').start()
        self.remove = patch('core.minio_client.minio_client.remove_object').start()

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        patch.stopall()
        self.engine.dispose()

    def create(self, data=None, image=IMAGE, video=VIDEO):
        return self.client.post('/api/services', data=data or {'title': 'New service'}, files={
            'image': ('фото.рус', image, 'image/png'), 'video': ('видео.рус', video, 'video/mp4')})

    def publish(self, id, **extra):
        return self.client.put(f'/api/services/{id}', json={
            'description':'Research', 'delta_n15':9.4, 'delta_c13':-18.2, **extra})

    def test_filtered_list_and_creator(self):
        data = self.client.get('/api/services').json()
        self.assertEqual([(s['id'],s['is_creator']) for s in data], [(1,1),(2,0)])
        self.assertEqual([s['id'] for s in self.client.get('/api/services?c13_max=-15').json()], [1])
        self.assertEqual(self.client.get('/api/services?filter=TITLE_2').json()[0]['id'], 2)
        self.assertEqual(self.client.get('/api/services?c13_max=bad').status_code, 422)

    def test_exact_lab_contract_and_postman(self):
        expected = {('GET', '/api/services'), ('POST', '/api/services'),
                    ('GET', '/api/services/feed'), ('GET', '/api/services/draft'),
                    ('PUT', '/api/services/{id}'), ('DELETE', '/api/services/{id}'),
                    ('POST', '/api/services/{id}/like'), ('POST', '/api/users/register'),
                    ('POST', '/api/users/login'), ('POST', '/api/users/logout')}
        actual = {(method.upper(), path) for path, operations in app.openapi()['paths'].items()
                  for method in operations}
        self.assertEqual(actual, expected)
        collection = json.loads(Path('postman_collection.json').read_text())
        requests = collection['item']
        self.assertEqual(len(requests), 10)
        actual = set()
        for item in requests:
            request = item['request']
            path = request['url'].replace('{{base_url}}', '').split('?')[0]
            path = path.replace('{{service_id}}', '{id}')
            actual.add((request['method'], path))
        self.assertEqual(actual, expected)
        self.assertEqual(self.client.get('/api/services', follow_redirects=False).status_code, 200)
        self.assertEqual(self.client.put('/api/services/1/publish', json={}).status_code, 404)

    def test_liked_flag_is_personal_and_visible(self):
        with Session(self.engine) as db:
            db.add(SignatureLike(user_id=2, signature_id=1))
            db.commit()
        data = self.client.get('/api/services/feed?id=1').json()
        self.assertEqual((data['is_liked'], data['likes_count']), (0, 1))
        page = self.client.get('/api/pages/isotopic_signatures/feed/1')
        self.assertIn('data-liked-message aria-live="polite"></span>', page.text)
        self.client.post('/api/services/1/like', json={'like': 1})
        self.assertEqual(self.client.get('/api/services/feed?id=1').json()['is_liked'], 1)
        self.assertIn('data-liked-message aria-live="polite">Вы поставили лайк</span>', self.client.get('/api/pages/isotopic_signatures/feed/1').text)

    def test_deleted_timestamp_excluded_at_query_level(self):
        from datetime import datetime
        from repositories.isotopic_signatures import by_id, published_by_id
        with Session(self.engine) as db:
            db.get(IsotopicSignature, 1).deleted_at = datetime.utcnow()
            db.commit()
            self.assertIsNone(by_id(db, 1))
            self.assertIsNone(published_by_id(db, 1))
            self.assertIsNone(by_id(db, 4))
        self.assertEqual(self.client.get('/api/services/feed?id=1').status_code, 404)
        self.assertEqual([s['id'] for s in self.client.get('/api/services').json()], [2])

    def test_feed_navigation_and_wrap(self):
        for url, id in [('/feed',1),('/feed?id=1',1),('/feed?id=1&next=true',2),('/feed?id=2&next=true',1)]:
            self.assertEqual(self.client.get('/api/services'+url).json()['id'], id)
        for id in (3,4,999):
            response = self.client.get(f'/api/services/feed?id={id}&next=true')
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
        self.assertEqual(self.publish(id).status_code,409)
        for value, count in [(1,1),(1,1),(0,0),(0,0),(1,1)]:
            response=self.client.post(f'/api/services/{id}/like',json={'like':value})
            self.assertEqual(response.json(),{'like':value,'likes_count':count})
        self.assertEqual(self.client.get(f'/api/services/feed?id={id}').json()['is_liked'],1)
        self.assertEqual(self.client.delete(f'/api/services/{id}').status_code,204)
        self.assertEqual(self.client.get(f'/api/services/feed?id={id}').status_code,404)
        self.assertEqual(self.publish(id).status_code,404)
        with Session(self.engine) as db:
            record=db.get(IsotopicSignature,id)
            self.assertEqual(record.status,'deleted');self.assertIsNotNone(record.completed_at)
            self.assertEqual(record.deleted_at, record.completed_at)
            self.assertEqual(db.query(SignatureLike).filter_by(signature_id=id).count(),1)

    def test_ownership(self):
        self.assertEqual(self.client.delete('/api/services/2').status_code,403)
        self.assertEqual(self.publish(3).status_code,403)
        with Session(self.engine) as db:self.assertEqual(db.get(IsotopicSignature,2).status,'published')

    def test_system_fields_rejected(self):
        for field,value in [('id',10),('status','published'),('creator_id',2),('moderator_id',2),('created_at','2000-01-01'),('formed_at','2000-01-01'),('completed_at','2000-01-01'),('deleted_at','2000-01-01')]:
            with self.subTest(field=field):
                self.assertEqual(self.create({'title':'Injected',field:str(value)}).status_code,422)
        id=self.create().json()['id']
        self.assertEqual(self.publish(id,status='deleted').status_code,422)
        self.assertEqual(self.publish(id,creator_id=2).status_code,422)
        self.assertEqual(self.publish(id,deleted_at='2000-01-01').status_code,422)
        self.assertEqual(self.client.put(f'/api/services/{id}', content='{"description":"x","delta_n15":Infinity,"delta_c13":-18}', headers={'Content-Type':'application/json'}).status_code,422)
        with Session(self.engine) as db:self.assertEqual(db.get(IsotopicSignature,id).status,'draft')

    def test_like_only_published_and_strict_binary(self):
        for id in (3,4,999):self.assertEqual(self.client.post(f'/api/services/{id}/like',json={'like':1}).status_code,404)
        for value in (-1,2,'1',True):
            self.assertEqual(self.client.post('/api/services/1/like',json={'like':value}).status_code,422)

    def test_files_required_and_validated_before_storage(self):
        self.assertEqual(self.client.post('/api/services',data={'title':'No files'}).status_code,422)
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

    def test_register_conflicts_and_stubs(self):
        data={'username':'new','email':'new@example.org','password':'my secret'}
        response=self.client.post('/api/users/register',json=data)
        self.assertEqual(response.status_code,201,response.text)
        self.assertNotIn('password',response.json())
        with Session(self.engine) as db:self.assertTrue(db.get(User,response.json()['id']).password.startswith('scrypt$'))
        self.assertEqual(self.client.post('/api/users/register',json=data).status_code,409)
        self.assertEqual(self.client.post('/api/users/register',json={**data,'username':'othernew'}).status_code,409)
        self.assertEqual(self.client.post('/api/users/register',json={**data,'id':50}).status_code,422)
        self.assertEqual(self.client.post('/api/users/login').status_code,200)
        self.assertEqual(self.client.post('/api/users/logout').status_code,200)

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

    def test_four_pages_and_api_actions(self):
        catalog=self.client.get('/api/pages/isotopic_signatures/list')
        self.assertEqual(catalog.status_code,200)
        self.assertIn('data-delete="1"',catalog.text);self.assertNotIn('data-delete="2"',catalog.text)
        draft=self.client.get('/api/pages/isotopic_signatures/draft')
        self.assertEqual(draft.status_code,200)
        self.assertIn('name="image"',draft.text);self.assertIn('name="video"',draft.text)
        id=self.create().json()['id']
        draft=self.client.get('/api/pages/isotopic_signatures/draft')
        self.assertIn(f'/api/services/{id}',draft.text)
        feed=self.client.get('/api/pages/isotopic_signatures/feed/1')
        self.assertEqual(feed.status_code,200);self.assertIn('data-like="1"',feed.text)
        next_page=self.client.get('/api/pages/isotopic_signatures/feed/1?next=true')
        self.assertIn('PRIVATE_TITLE_2',next_page.text)
        for path in ['/api/pages/isotopic_signatures/feed/4','/api/pages/isotopic_signatures/unavailable']:
            unavailable=self.client.get(path);self.assertEqual(unavailable.status_code,404)
            self.assertNotIn('PRIVATE_TITLE_4',unavailable.text)

    def test_all_routes_api_and_legacy_writes_removed(self):
        for route in app.routes:
            if hasattr(route,'methods'):self.assertTrue(route.path.startswith('/api'),route.path)
        self.assertEqual(self.client.post('/isotopic_signatures/2/delete').status_code,404)
        self.assertEqual(self.client.post('/api/pages/isotopic_signatures/draft').status_code,405)


if __name__ == '__main__':unittest.main()
