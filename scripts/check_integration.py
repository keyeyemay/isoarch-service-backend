"""Run against an explicitly selected disposable PostgreSQL and MinIO instance."""
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


def main():
    if os.environ.get('LR3_INTEGRATION') != '1':
        raise SystemExit('Set LR3_INTEGRATION=1 and select a disposable DATABASE_URL/MINIO_ENDPOINT explicitly')
    if not os.environ.get('DATABASE_URL') or not os.environ.get('MINIO_ENDPOINT'):
        raise SystemExit('Explicit DATABASE_URL and MINIO_ENDPOINT are required')
    from db.session import engine
    from db.migrate import upgrade_database
    from models import IsotopicSignature, User, SignatureLike
    base=os.environ.get('LR3_BASE_URL','http://127.0.0.1:58000')
    image=Path('static/images/default_signature.png').read_bytes()
    video=Path('static/videos/default_signature.mp4').read_bytes()
    results=[]
    with httpx.Client(base_url=base, timeout=20, trust_env=False) as client:
        def call(name,method,path,expected=200,**kwargs):
            response=client.request(method,path,**kwargs)
            assert response.status_code == expected,(name,response.status_code,response.text)
            results.append({'check':name,'method':method,'path':path,'status':response.status_code})
            return response
        records=call('Published filtered list','GET','/api/services/?c13_max=-15').json()
        assert records and all(s['status']=='published' and s['delta_c13']<=-15 and s['is_creator'] in (0,1) for s in records)
        assert call('Current draft absent','GET','/api/services/draft').json() is None
        draft=call('Upload actual PNG and MP4','POST','/api/services/',201,data={'title':'LR3 integration'},files={
            'image':('фото.рус',image,'image/png'),'video':('видео.рус',video,'video/mp4')}).json()
        id=draft['id']
        assert call('Own draft without ID','GET','/api/services/draft').json()['id']==id
        published=call('Publish draft','PUT',f'/api/services/{id}/publish',json={
            'description':'Integration verification','delta_n15':9.4,'delta_c13':-18.2}).json()
        assert published['status']=='published' and published['formed_at'] and published['is_creator']==1
        for field,data in [('image_url',image),('video_url',video)]:
            response=client.get(published[field]);assert response.status_code==200 and response.content==data
            results.append({'check':'Actual MinIO '+field,'status':200,'bytes':len(data)})
        first=call('Feed without ID','GET','/api/services/feed').json()
        following=call('Next published ID','GET',f"/api/services/feed/{first['id']}?next=true").json()
        assert following['id']!=first['id']
        for value,count in [(1,1),(1,1),(0,0),(0,0),(1,1)]:
            response=call('Idempotent like/unlike','POST',f'/api/services/{id}/like',json={'like':value}).json()
            assert response=={'like':value,'likes_count':count}
        call('Reject foreign deletion','DELETE','/api/services/3',403)
        call('Reject deleted like','POST','/api/services/6/like',404,json={'like':1})
        call('Reject system fields','PUT',f'/api/services/{id}/publish',422,json={'description':'x','delta_n15':1,'delta_c13':1,'creator_id':2})
        call('Soft delete own service','DELETE',f'/api/services/{id}',204)
        call('Hidden deleted service','GET',f'/api/services/feed/{id}',404)
        suffix=uuid.uuid4().hex[:12]
        registration={'username':'check_'+suffix,'email':suffix+'@example.org','password':'StudyPassword123'}
        user=call('Register user','POST','/api/users/register',201,json=registration).json()
        assert 'password' not in user
        call('Duplicate email conflict','POST','/api/users/register',409,json={**registration,'username':'other_'+suffix})
        call('Login stub','POST','/api/users/login')
        call('Logout stub','POST','/api/users/logout')
        for page in ['list','feed/1','draft','unavailable']:
            response=call('HTML '+page,'GET','/api/pages/isotopic_signatures/'+page,404 if page=='unavailable' else 200)
            assert '<html' in response.text
        hidden=call('HTML never exposes deleted data','GET',f'/api/pages/isotopic_signatures/feed/{id}',404)
        assert 'LR3 integration' not in hidden.text
    with Session(engine) as db:
        record=db.get(IsotopicSignature,id)
        assert record.status=='deleted' and record.completed_at and record.image_file==draft['image_file']
        assert db.query(SignatureLike).filter_by(signature_id=id,user_id=1).count()==1
        assert db.get(User,user['id']).password.startswith('scrypt$')
        snapshots={
            'isotopic_signatures':[{'id':s.id,'title':s.title,'status':s.status,'creator_id':s.creator_id,'image_file':s.image_file,'video_file':s.video_file,'formed_at':str(s.formed_at),'completed_at':str(s.completed_at)} for s in db.query(IsotopicSignature).order_by(IsotopicSignature.id)],
            'users':[{'id':u.id,'username':u.username,'email':u.email} for u in db.query(User).order_by(User.id)],
            'signature_likes':[{'id':l.id,'user_id':l.user_id,'signature_id':l.signature_id} for l in db.query(SignatureLike).order_by(SignatureLike.id)]}
    # Check the actual PostgreSQL upgrade path using an isolated legacy schema.
    if engine.dialect.name=='postgresql':
        with engine.begin() as conn:conn.execute(text('CREATE SCHEMA lr3_legacy_check'))
        legacy=create_engine(os.environ['DATABASE_URL'],connect_args={'options':'-csearch_path=lr3_legacy_check'})
        try:
            with legacy.begin() as conn:
                conn.execute(text('CREATE TABLE users (id SERIAL PRIMARY KEY, username VARCHAR(100) NOT NULL UNIQUE, full_name VARCHAR(255), email VARCHAR(255) UNIQUE, created_at TIMESTAMP NOT NULL)'))
                conn.execute(text('CREATE TABLE isotopic_signatures (id SERIAL PRIMARY KEY, title VARCHAR(255) NOT NULL, description TEXT, status VARCHAR(50) NOT NULL, image_url VARCHAR(500), video_url VARCHAR(500), delta_n15 FLOAT, delta_c13 FLOAT, created_at TIMESTAMP NOT NULL, creator_id INTEGER NOT NULL REFERENCES users(id), formation_date TIMESTAMP)'))
                conn.execute(text('CREATE TABLE signature_likes (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), signature_id INTEGER NOT NULL REFERENCES isotopic_signatures(id), created_at TIMESTAMP NOT NULL, CONSTRAINT uq_user_signature_like UNIQUE (user_id,signature_id))'))
                conn.execute(text("CREATE UNIQUE INDEX uq_user_single_draft ON isotopic_signatures(creator_id) WHERE status='черновик'"))
                conn.execute(text("INSERT INTO users (id,username,created_at) VALUES (1,'legacy','2024-01-01')"))
                conn.execute(text("INSERT INTO isotopic_signatures (id,title,status,image_url,creator_id,created_at,formation_date) VALUES (1,'Preserved','опубликован','image.png',1,'2024-01-01','2024-02-01'),(2,'Draft','черновик',NULL,1,'2024-01-01','2024-01-01')"))
                conn.execute(text("INSERT INTO signature_likes (user_id,signature_id,created_at) VALUES (1,1,'2024-01-01')"))
            upgrade_database(legacy)
            with Session(legacy) as db:
                assert db.get(IsotopicSignature,1).title=='Preserved'
                assert db.get(IsotopicSignature,1).status=='published'
                assert len(db.get(IsotopicSignature,1).likes)==1
                assert db.get(IsotopicSignature,2).formed_at is None
            results.append({'check':'PostgreSQL legacy migration preserves records and likes','status':'passed'})
        finally:
            legacy.dispose()
            with engine.begin() as conn:conn.execute(text('DROP SCHEMA lr3_legacy_check CASCADE'))
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'database':'PostgreSQL','media':'real MinIO',
            'checks':results,'snapshots':snapshots}
    Path('docs/verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f'{len(results)} integration checks passed. Results: docs/verification.json')


if __name__=='__main__':main()
