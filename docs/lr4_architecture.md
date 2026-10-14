# Общая диаграмма классов бэкенда и SPA · ЛР4

Одна диаграмма: 3 предметные модели, Redis-сессия, PostgreSQL, Redis, MinIO,
4 основных экрана SPA, экран авторизации и редактирование публикации. APIRouter — входные точки
интерфейсов с ответвлениями к методам (12 методов API).

[Открыть готовую диаграмму SVG](lr4_architecture.svg).

```mermaid
classDiagram
    class SPA {
        +navigate(hash)
        +render()
        +api(path, options)
    }
    class CatalogPage {
        +filterAndList()
    }
    class FeedPage {
        +readNextAndLike()
    }
    class DraftPage {
        +uploadPublishDelete()
    }
    class UnavailablePage {
        +showUnavailable()
    }
    class AuthPage {
        +registerAndLogin()
    }
    SPA *-- CatalogPage
    SPA *-- FeedPage
    SPA *-- DraftPage
    SPA *-- UnavailablePage
    SPA *-- AuthPage
    class EditPage {
        +updatePublication()
    }
    SPA *-- EditPage
    EditPage ..> ServicesRouter : AJAX GET / PUT

    class AuthRouter {
        <<interface>>
        +entry /auth
        +POST register(data) UserResponse
        +POST login(data) UserResponse_SetCookie
        +POST logout() HTTP204
        +GET me() UserResponse
    }
    class ServicesRouter {
        <<interface>>
        +entry /services
        +GET list(c13_max, filter) ServiceResponseList
        +GET feed() ServiceResponse
        +GET feedById(id, next) ServiceResponse
        +GET draft() DraftResponse
        +POST create(title, image, video) DraftResponse
        +PUT publish(id, fields) ServiceResponse
        +DELETE remove(id) HTTP204
        +POST like(id, binary) LikeResponse
    }

    %% Явные ответвления методов от входных точек интерфейсов
    class RegisterEndpoint["POST /auth/register"]
    AuthRouter --> RegisterEndpoint : method
    class LoginEndpoint["POST /auth/login"]
    AuthRouter --> LoginEndpoint : method
    class LogoutEndpoint["POST /auth/logout"]
    AuthRouter --> LogoutEndpoint : method
    class MeEndpoint["GET /auth/me"]
    AuthRouter --> MeEndpoint : method
    class ListEndpoint["GET /services"]
    ServicesRouter --> ListEndpoint : method
    class FeedEndpoint["GET /services/feed"]
    ServicesRouter --> FeedEndpoint : method
    class FeedItemEndpoint["GET /services/feed/{id}"]
    ServicesRouter --> FeedItemEndpoint : method
    class DraftEndpoint["GET /services/draft"]
    ServicesRouter --> DraftEndpoint : method
    class CreateEndpoint["POST /services"]
    ServicesRouter --> CreateEndpoint : method
    class UpdateEndpoint["PUT /services/{id}"]
    ServicesRouter --> UpdateEndpoint : method
    class DeleteEndpoint["DELETE /services/{id}"]
    ServicesRouter --> DeleteEndpoint : method
    class LikeEndpoint["POST /services/{id}/like"]
    ServicesRouter --> LikeEndpoint : method

    CatalogPage ..> ServicesRouter : AJAX GET / DELETE
    FeedPage ..> ServicesRouter : AJAX GET / POST like
    DraftPage ..> ServicesRouter : AJAX GET / POST / PUT / DELETE
    UnavailablePage ..> ServicesRouter : 404 public data
    AuthPage ..> AuthRouter : AJAX register / login
    SPA ..> AuthRouter : me / logout

    class SessionDependency {
        +get_optional_user(request, db) UserOrNone
        +get_current_user(request, user) UserOr401
    }
    class AuthService {
        +hash_password(password)
        +verify_password(password, hash)
        +create_session(user_id, previous_token)
        +revoke_session(token)
        +session_user_id(token)
    }
    class SignatureService {
        +list_services(db, filters)
        +get_feed(db, id, next)
        +get_draft(db, user_id)
        +create_draft(db, user_id, title, image, video)
        +publish_draft(db, id, user_id, fields)
        +delete_service(db, id, user_id)
        +toggle_like(db, id, user_id, like)
    }
    class SignatureRepository {
        +search_published(db, filters)
        +first_published(db)
        +next_published(db, id)
        +draft_for_user(db, user_id)
        +by_id(db, id)
    }
    class MediaService {
        +read_media(file, kind)
    }
    class MinIO {
        +upload_file_to_minio(data)
    }
    AuthRouter ..> AuthService
    AuthRouter ..> SessionDependency
    ServicesRouter ..> SessionDependency
    ServicesRouter ..> SignatureService
    SignatureService ..> SignatureRepository
    SignatureService ..> MediaService
    SignatureService ..> MinIO

    class User {
        +int id
        +string username
        +string password
        +string full_name
        +string email
        +datetime created_at
    }
    class IsotopicSignature {
        +int id
        +string title
        +text description
        +string status
        +float delta_n15
        +float delta_c13
        +string image_file
        +string video_file
        +int creator_id
        +int moderator_id
        +datetime created_at
        +datetime formed_at
        +datetime completed_at
    }
    class SignatureLike {
        +int id
        +int user_id
        +int signature_id
        +datetime created_at
    }
    class RedisSession {
        +string token_hash
        +int user_id
        +int ttl_seconds
    }
    class Redis {
        <<database>>
        +GET session
        +SET session EX ttl
        +DEL session
        +MULTI_EXEC rotate
    }
    class PostgreSQL {
        <<database>>
        +users
        +isotopic_signatures
        +signature_likes
        +alembic_version
    }
    User "1" --> "0..*" IsotopicSignature : creator
    User "0..1" --> "0..*" IsotopicSignature : moderator
    User "1" --> "0..*" SignatureLike
    IsotopicSignature "1" --> "0..*" SignatureLike
    User "1" --> "0..*" RedisSession
    PostgreSQL o-- User
    PostgreSQL o-- IsotopicSignature
    PostgreSQL o-- SignatureLike
    Redis o-- RedisSession
    SignatureRepository ..> PostgreSQL : SQLAlchemy
    SignatureService ..> PostgreSQL : transactions
    AuthRouter ..> PostgreSQL : users
    AuthService ..> Redis : session digest and TTL
    SessionDependency ..> AuthService : resolve session
    SessionDependency ..> User
```

Входные точки — `AuthRouter` (`/auth`) и `ServicesRouter` (`/services`).
От каждой проведены отдельные стрелки к узлам всех 12 методов API.
Связь SPA → APIRouter использует fetch/JSON и multipart для медиа;
сессия передаётся в cookie, а объекты MinIO — бинарными файлами.
Все изменения авторства/состояния вычисляются на стороне сервера.
