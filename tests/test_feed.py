import unittest
from unittest.mock import patch
from fastapi import HTTPException, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from starlette.requests import Request
from api.handlers import router, get_isotopic_signature_feed, get_isotopic_signature_draft, get_isotopic_signatures
from db.base import Base
from models import User, IsotopicSignature
from services import isotopic_signatures as service


class Lab2Tests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(User(id=1, username='current'))
        for record_id, status in [(2,'опубликован'), (7,'черновик'), (11,'удален'), (19,'опубликован')]:
            self.db.add(User(id=record_id, username=f'user{record_id}'))
            self.db.flush()
            self.db.add(IsotopicSignature(id=record_id,creator_id=record_id,title=f'Образец {record_id}',status=status))
        self.db.commit()
        self.queries=[]
        event.listen(self.engine,'before_cursor_execute',lambda conn,cursor,sql,params,ctx,many:self.queries.append((sql,params)))
        app=FastAPI()
        app.mount('/static',StaticFiles(directory='static'),name='static')
        app.include_router(router)
        self.app=app
        self.request=Request({'type':'http','method':'GET','path':'/isotopic_signatures/feed/2','scheme':'http','server':('testserver',80),'headers':[],'root_path':'','router':app.router})

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def feed(self, record_id):
        with patch('api.handlers.templates.TemplateResponse', side_effect=lambda **kwargs:kwargs):
            return get_isotopic_signature_feed(self.request,record_id,db=self.db)

    def test_navigation(self):
        for requested,current,following in [(2,2,19),(19,19,2),(999,2,19),(7,2,19)]:
            response=self.feed(requested)
            self.assertEqual(response['context']['isotopic_signature']['id'],current)
            self.assertEqual(response['context']['next_isotopic_signature_id'],following)

    def test_deleted(self):
        self.assertEqual(self.feed(11)['status_code'],404)

    def test_single_row_queries(self):
        self.feed(2)
        queries=[(sql,params) for sql,params in self.queries if 'FROM isotopic_signatures' in sql]
        self.assertTrue(queries)
        for sql,params in queries:
            self.assertIn('LIMIT',sql.upper())
            self.assertEqual(params[-2:],(1,0))

    def test_create_and_publish(self):
        service.create_draft(self.db,'Новый образец')
        service.create_draft(self.db,'Второй')
        draft=self.db.query(IsotopicSignature).filter_by(creator_id=1).one()
        created_at=draft.created_at
        self.assertIsNotNone(created_at)
        self.assertIsNone(draft.image_url)
        self.assertIsNone(draft.delta_n15)
        service.publish_draft(self.db,'Описание',9.4,-18.2)
        self.db.refresh(draft)
        self.assertEqual(draft.status,'опубликован')
        self.assertEqual(draft.created_at,created_at)
        self.assertGreaterEqual(draft.formation_date,created_at)

    def test_form_stages_and_links(self):
        html=get_isotopic_signature_draft(self.request,db=self.db).body.decode()
        self.assertIn('type="file"',html)
        self.assertNotIn('name="photo_file"',html)
        self.assertNotIn('type="date"',html)
        self.assertLess(html.index('id="photo_file"'),html.index('id="title"'))
        service.create_draft(self.db,'Черновик')
        html=get_isotopic_signature_draft(self.request,db=self.db).body.decode()
        self.assertNotIn('type="file"',html)
        self.assertNotIn('type="date"',html)
        self.assertNotIn('readonly',html)
        self.assertIn('id="delta_n15"',html)
        self.assertIn('id="delta_c13"',html)
        feed_html=get_isotopic_signature_feed(self.request,2,db=self.db).body.decode()
        self.assertIn('/isotopic_signatures/feed/19',feed_html)
        self.assertNotIn('?next=',feed_html)
        catalog_html=get_isotopic_signatures(self.request,db=self.db).body.decode()
        self.assertIn('/isotopic_signatures/2/delete',catalog_html)

    def test_six_routes(self):
        paths=self.app.openapi()['paths']
        self.assertEqual(sum(len(methods) for methods in paths.values()),6)
        self.assertTrue(all(path.startswith('/isotopic_signatures/') for path in paths))

    def test_empty_feed(self):
        self.db.query(IsotopicSignature).filter_by(status='опубликован').update({'status':'удален'})
        self.db.commit()
        with self.assertRaises(HTTPException) as error:self.feed(999)
        self.assertEqual(error.exception.status_code,404)
        self.assertEqual(get_isotopic_signatures(self.request,db=self.db).status_code,200)

    def test_single_record_wrap(self):
        self.db.get(IsotopicSignature,19).status='удален'
        self.db.commit()
        self.assertEqual(self.feed(2)['context']['next_isotopic_signature_id'],2)


if __name__=='__main__':
    unittest.main()
