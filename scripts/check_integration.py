"""Verify LR4 against explicitly selected disposable PostgreSQL/MinIO services."""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
import httpx
from sqlalchemy.orm import Session


def main():
    if os.environ.get('LR4_INTEGRATION') != '1':
        raise SystemExit('Set LR4_INTEGRATION=1 and explicit test DATABASE_URL/MINIO_ENDPOINT')
    if not all(os.environ.get(key) for key in ('DATABASE_URL', 'MINIO_ENDPOINT', 'REDIS_URL')):
        raise SystemExit('Explicit DATABASE_URL, MINIO_ENDPOINT and REDIS_URL are required')
    from db.session import engine
    from models import IsotopicSignature, User, SignatureLike
    from services.auth import session_key
    from core.redis_client import redis_client
    from core.config import SESSION_TTL_SECONDS
    base = os.environ.get('LR4_BASE_URL', 'http://127.0.0.1:58000')
    results = []
    image = Path('static/images/default_signature.png').read_bytes()
    video = Path('static/videos/default_signature.mp4').read_bytes()
    with httpx.Client(base_url=base, timeout=20, trust_env=False) as client:
        def call(name, method, path, expected=200, **kwargs):
            response = client.request(method, path, **kwargs)
            assert response.status_code == expected, (name, response.status_code, response.text)
            results.append({'check': name, 'method': method, 'path': path, 'http_code': response.status_code})
            return response

        records = call('Guest published list', 'GET', '/services?c13_max=-15').json()
        assert all(s['status'] == 'published' and s['delta_c13'] <= -15 and s['is_creator'] == 0 for s in records)
        call('Guest private draft rejected', 'GET', '/services/draft', 401)
        call('Guest write rejected', 'POST', '/services/1/like', 401, json={'like': 1})
        suffix = uuid.uuid4().hex[:12]
        registration = {'username': 'lr4_' + suffix, 'password': 'StudyPassword123', 'email': suffix + '@example.org'}
        owner = call('Register creator', 'POST', '/auth/register', 201, json=registration).json()
        assert 'password' not in owner
        call('Duplicate email rejected', 'POST', '/auth/register', 409, json={**registration, 'username': 'duplicate_' + suffix})
        call('Wrong password rejected', 'POST', '/auth/login', 401, json={'username': registration['username'], 'password': 'bad'})
        login = call('Login sets cookie', 'POST', '/auth/login', json={k: registration[k] for k in ('username','password')})
        assert 'HttpOnly' in login.headers['set-cookie']
        token = client.cookies.get('session_id')
        assert redis_client.get(session_key(token)) == str(owner['id'])
        assert 0 < redis_client.ttl(session_key(token)) <= SESSION_TTL_SECONDS
        results.append({'check': 'Real Redis session user and TTL', 'result': 'passed'})
        assert call('Session identity', 'GET', '/auth/me').json()['id'] == owner['id']
        assert call('Own draft absent', 'GET', '/services/draft').json() is None
        draft = call('Upload actual binary PNG/MP4', 'POST', '/services', 201, data={'title': 'LR4 integration'}, files={
            'image': ('фото.рус', image, 'image/png'), 'video': ('видео.рус', video, 'video/mp4')}).json()
        id = draft['id']
        assert call('Own draft without ID', 'GET', '/services/draft').json()['id'] == id
        call('Second draft rejected', 'POST', '/services', 409, data={'title': 'Duplicate'}, files={
            'image': ('a.png', image, 'image/png'), 'video': ('a.mp4', video, 'video/mp4')})
        published = call('Publish own draft', 'PUT', f'/services/{id}', json={
            'description': 'LR4 integration', 'delta_n15': 9.4, 'delta_c13': -18.2}).json()
        assert published['creator_id'] == owner['id'] and published['is_creator'] == 1 and published['formed_at']
        updated = call('Update published fields', 'PUT', f'/services/{id}', json={
            'title': 'LR4 updated', 'description': 'Updated research', 'delta_n15': 10.1, 'delta_c13': -19}).json()
        assert updated['title'] == 'LR4 updated' and updated['description'] == 'Updated research'
        assert updated['formed_at'] == published['formed_at'] and updated['creator_id'] == owner['id']
        assert call('Assignment cookie spelling', 'GET', '/auth/me', headers={'Cookie': 'session-id=' + token}).json()['id'] == owner['id']
        for field, expected in [('image_url', image), ('video_url', video)]:
            response = client.get(published[field])
            assert response.status_code == 200 and response.content == expected
            results.append({'check': 'Real MinIO ' + field, 'bytes': len(expected), 'http_code': 200})
        for value, count in [(1,1),(1,1),(0,0),(0,0),(1,1)]:
            assert call('Idempotent like/unlike', 'POST', f'/services/{id}/like', json={'like': value}).json() == {'like': value, 'likes_count': count}
        first = call('Public feed', 'GET', '/services/feed').json()
        call('Next feed', 'GET', f"/services/feed/{first['id']}?next=true")
        call('Reject creator injection', 'PUT', f'/services/{id}', 422, json={
            'description': 'x', 'delta_n15': 1, 'delta_c13': 1, 'creator_id': 2})
        # A second client must see personal flags for its own identity only.
        with httpx.Client(base_url=base, timeout=20, trust_env=False) as other:
            data = {'username': 'other_' + suffix, 'password': 'StudyPassword123'}
            assert other.post('/auth/register',json=data).status_code == 201
            assert other.post('/auth/login',json=data).status_code == 200
            assert other.get('/services/draft').json() is None
            assert other.delete(f'/services/{id}').status_code == 403
            assert other.put(f'/services/{id}', json={'description':'Forbidden', 'delta_n15':1, 'delta_c13':1}).status_code == 403
            assert other.get(f'/services/feed/{id}').json()['is_creator'] == 0
            assert other.get(f'/services/feed/{id}').json()['is_liked'] == 0
            assert other.post('/auth/logout').status_code == 204
            results.append({'check': 'Independent user session and ownership', 'result': 'passed'})
        call('Soft delete', 'DELETE', f'/services/{id}', 204)
        call('Deleted record hidden', 'GET', f'/services/feed/{id}', 404)
        call('Logout', 'POST', '/auth/logout', 204)
        call('Logged out denied', 'GET', '/services/draft', 401)
        call('Revoked cookie cannot be replayed', 'GET', '/auth/me', 401, headers={'Cookie': 'session_id=' + token})
        call('Swagger', 'GET', '/docs')
        schema = call('OpenAPI', 'GET', '/openapi.json').json()
        assert schema['components']['securitySchemes']['SessionCookie']['name'] == 'session_id'
        for path in ('/services', '/services/feed', '/services/feed/{id}'):
            assert schema['paths'][path]['get']['security'] == [{}, {'SessionCookie': []}]
    with Session(engine) as db:
        record = db.get(IsotopicSignature, id)
        assert record.status == 'deleted' and record.completed_at and record.creator_id == owner['id']
        assert db.query(SignatureLike).filter_by(signature_id=id, user_id=owner['id']).count() == 1
        assert db.get(User, owner['id']).password.startswith('scrypt$')
        assert redis_client.get(session_key(token)) is None
        results.append({'check': 'PostgreSQL soft delete, preserved like, password hash; Redis session revoked', 'result': 'passed'})
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'database': engine.dialect.name,
              'media': 'real MinIO', 'sessions': 'real Redis', 'result': 'passed', 'checks': results}
    Path('docs/lr4_integration_verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'{len(results)} LR4 integration checks passed')


if __name__ == '__main__':
    main()
