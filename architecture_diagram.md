# Диаграмма классов ЛР3

Редактируемая версия по образцу `diagramexample.png`: [architecture_diagram.drawio](architecture_diagram.drawio).
Файл содержит два листа: архитектуру и подробные поля моделей/схем.

Имена таблиц указаны у ORM-моделей. Стрелки от страниц показывают фактические
зависимости: GET формирует HTML через общий сервис, JS вызывает REST API.

```mermaid
classDiagram
    class User {
        <<ORM users>>
        +int id
        +string username
        +string password
        +string full_name
        +string email
        +datetime created_at
    }
    class IsotopicSignature {
        <<ORM isotopic_signatures>>
        +int id
        +string title
        +string description
        +string status
        +string image_file
        +string video_file
        +float delta_n15
        +float delta_c13
        +int creator_id
        +int moderator_id
        +datetime created_at
        +datetime formed_at
        +datetime completed_at
        +datetime deleted_at
    }
    class SignatureLike {
        <<ORM signature_likes>>
        +int id
        +int user_id
        +int signature_id
        +datetime created_at
    }
    class AlembicVersion {
        <<table alembic_version>>
        +string version_num
    }
    User "1" -- "0..*" IsotopicSignature : creator
    User "0..1" -- "0..*" IsotopicSignature : moderator
    User "1" -- "0..*" SignatureLike
    IsotopicSignature "1" -- "0..*" SignatureLike
    class ServicesAPI {
        <<interface>>
        +GET /api/services
        +GET /api/services/feed?id=id&next=true
        +GET /api/services/draft
        +POST /api/services
        +PUT /api/services/id
        +DELETE /api/services/id
        +POST /api/services/id/like
    }
    class UsersAPI {
        <<interface>>
        +POST /api/users/register
        +POST /api/users/login
        +POST /api/users/logout
    }
    class PagesDomain {
        <<interface>>
        +GET /api/pages/isotopic_signatures/list
        +GET /api/pages/isotopic_signatures/feed/id?next=true
        +GET /api/pages/isotopic_signatures/draft
        +GET /api/pages/isotopic_signatures/unavailable
    }
    class SignatureService {
        +list_services()
        +get_feed()
        +get_draft()
        +create_draft()
        +publish_draft()
        +delete_service()
        +toggle_like()
    }
    class CurrentUser {
        +get_current_user()
        +CURRENT_USER_ID = 1
    }
    class MinIO {
        +image objects
        +video objects
    }
    ServicesAPI ..> SignatureService
    ServicesAPI ..> CurrentUser
    PagesDomain ..> SignatureService
    PagesDomain ..> CurrentUser
    CurrentUser ..> User
    SignatureService ..> IsotopicSignature
    SignatureService ..> SignatureLike
    SignatureService ..> MinIO
    UsersAPI ..> User
    class CatalogPage {
        <<tiles.html>>
    }
    class FeedPage {
        <<feed.html>>
    }
    class DraftPage {
        <<add.html>>
    }
    class UnavailablePage {
        <<deleted.html>>
    }
    CatalogPage ..> PagesDomain : HTML GET
    CatalogPage ..> ServicesAPI : DELETE own service
    FeedPage ..> PagesDomain : HTML GET
    FeedPage ..> ServicesAPI : GET next and POST like
    DraftPage ..> PagesDomain : HTML GET
    DraftPage ..> ServicesAPI : POST files PUT publish DELETE
    UnavailablePage ..> PagesDomain : HTML GET and catalog link
```

`id` в URL диаграммы означает параметр пути `{id}`. Сериализаторы Pydantic:
`ServiceResponse`, `ServiceDraftResponse`, `PublishRequest`, `LikeRequest`,
`UserRegister`, `UserResponse` (`api/schemas.py`). Дополнительные входные поля
запрещены. Отдельной страницы авторизации в ЛР3 нет; login/logout — заглушки API.
Служебные маршруты Swagger/OpenAPI и статика описаны в README.

Лента без query-параметров возвращает первую запись; `id` выбирает запись,
`next=true` — следующую. Это одна из 10 операций JSON API.
`deleted_at` — маркер soft delete; `is_liked` — SQL EXISTS по текущему пользователю.
