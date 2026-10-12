from datetime import datetime
from sqlalchemy.orm import Session

from db.base import Base
from db.session import SessionLocal, engine
from models import IsotopicSignature, SignatureLike, User


def seed_database(db: Session | None = None):
    # Создаем таблицы, если их еще нет
    Base.metadata.create_all(bind=engine)

    close_after = False
    if db is None:
        db = SessionLocal()
        close_after = True

    try:
        # Проверяем, есть ли уже данные
        if db.query(User).count() == 0:
            user1 = User(
                id=1,
                username="archaeologist_main",
                full_name="Д-р Иванов А.С. (Лаборатория изотопного анализа)",
                email="ivanov@isoarch.org",
            )
            user2 = User(
                id=2,
                username="researcher_petrov",
                full_name="Петров В.В. (Институт археологии РАН)",
                email="petrov@archaeo.ru",
            )
            user3 = User(
                id=3,
                username="student_sidorov",
                full_name="Сидоров К.М. (Кафедра археологии)",
                email="sidorov@uni.edu",
            )
            db.add_all([user1, user2, user3])
            db.commit()

        if db.query(IsotopicSignature).count() == 0:
            signatures = [
                IsotopicSignature(
                    id=1,
                    title="Погребение №14 (Бронза)",
                    description=(
                        "Изотопный анализ δ¹⁵N и δ¹³C коллагена костных останков индивида "
                        "из кургана бронзового века. Соотношение изотопов указывает на смешанный "
                        "рацион с преобладанием мяса травоядных животных и умеренным потреблением злаков."
                    ),
                    status="опубликован",
                    delta_n15=9.4,
                    delta_c13=-18.2,
                    created_at=datetime(2024, 3, 12, 10, 0, 0),
                    formation_date=datetime(2024, 3, 12, 14, 30, 0),
                    image_url="metallography_bronze_artifact.png",
                    video_url="archaelogical_science_bone.mp4",
                    creator_id=1,
                ),
                IsotopicSignature(
                    id=2,
                    title="Погребение №7 (Железный век)",
                    description=(
                        "Анализ изотопных сигнатур указывает на высокую долю рыбы в рационе — "
                        "индивид, вероятно, проживал в прибрежном поселении. Значения δ¹³C близки "
                        "к эталонным для морских ресурсов."
                    ),
                    status="опубликован",
                    delta_n15=12.7,
                    delta_c13=-13.5,
                    created_at=datetime(2024, 5, 2, 9, 15, 0),
                    formation_date=datetime(2024, 5, 2, 11, 45, 0),
                    image_url="c14_bone_dating.png",
                    video_url="skull_bones.mp4",
                    creator_id=1,
                ),
                IsotopicSignature(
                    id=3,
                    title="Курган №2 (Скифы)",
                    description=(
                        "Соотношение δ¹⁵N/δ¹³C соответствует преимущественно растительному рациону "
                        "с высокой долей злаков (просо, ячмень) и минимальной долей мяса травоядных."
                    ),
                    status="опубликован",
                    delta_n15=6.1,
                    delta_c13=-21.8,
                    created_at=datetime(2023, 11, 20, 12, 0, 0),
                    formation_date=datetime(2023, 11, 20, 16, 20, 0),
                    image_url="archaeobotany_seed_specimen.png",
                    video_url="chemistry_lab_sample_preparation.mp4",
                    creator_id=2,
                ),
                IsotopicSignature(
                    id=4,
                    title="Погребение №21 (Неолит)",
                    description=(
                        "Ранний образец с преобладанием мяса травоядных и незначительной долей "
                        "растительного компонента. Изотопные значения близки к эталонной группе "
                        "«мясо травоядных»."
                    ),
                    status="опубликован",
                    delta_n15=8.9,
                    delta_c13=-19.5,
                    created_at=datetime(2024, 1, 9, 8, 30, 0),
                    formation_date=datetime(2024, 1, 9, 10, 15, 0),
                    image_url="strontium_tooth_enamel.png",
                    video_url="archaelogical_science_bone.mp4",
                    creator_id=1,
                ),
                IsotopicSignature(
                    id=5,
                    title="Погребение №3 (Средневековье)",
                    description=(
                        "Предварительный анализ образца костного коллагена. Требуется уточнение "
                        "лабораторных данных перед публикацией."
                    ),
                    status="черновик",
                    delta_n15=10.3,
                    delta_c13=-16.7,
                    created_at=datetime(2024, 6, 18, 14, 0, 0),
                    formation_date=datetime(2024, 6, 18, 15, 0, 0),
                    image_url="soil_core_stratigraphy.png",
                    video_url="bioarchaelogy_lab_analysis.mp4",
                    creator_id=1,
                ),
                IsotopicSignature(
                    id=6,
                    title="Погребение №9 (Античность)",
                    description="Услуга снята с публикации, данные архивированы.",
                    status="удален",
                    delta_n15=7.5,
                    delta_c13=-20.1,
                    created_at=datetime(2023, 8, 1, 11, 0, 0),
                    formation_date=datetime(2023, 8, 1, 13, 0, 0),
                    image_url="ceramics_isotope_analysis.png",
                    video_url="chemistry_lab_sample_preparation.mp4",
                    creator_id=1,
                ),
            ]
            db.add_all(signatures)
            db.commit()

        if db.query(SignatureLike).count() == 0:
            likes = [
                # Сигнатура 1: 3 лайка (пользователи 1, 2, 3)
                SignatureLike(user_id=1, signature_id=1),
                SignatureLike(user_id=2, signature_id=1),
                SignatureLike(user_id=3, signature_id=1),
                # Сигнатура 2: 2 лайка (пользователи 1, 3)
                SignatureLike(user_id=1, signature_id=2),
                SignatureLike(user_id=3, signature_id=2),
                # Сигнатура 3: 1 лайк (пользователь 2)
                SignatureLike(user_id=2, signature_id=3),
                # Сигнатура 4: 3 лайка (пользователи 1, 2, 3)
                SignatureLike(user_id=1, signature_id=4),
                SignatureLike(user_id=2, signature_id=4),
                SignatureLike(user_id=3, signature_id=4),
            ]
            db.add_all(likes)
            db.commit()

        # Синхронизируем последовательности (sequences) PostgreSQL с максимальными ID
        from sqlalchemy import text
        db.execute(text("SELECT setval(pg_get_serial_sequence('users', 'id'), coalesce(max(id), 1)) FROM users;"))
        db.execute(text("SELECT setval(pg_get_serial_sequence('isotopic_signatures', 'id'), coalesce(max(id), 1)) FROM isotopic_signatures;"))
        db.execute(text("SELECT setval(pg_get_serial_sequence('signature_likes', 'id'), coalesce(max(id), 1)) FROM signature_likes;"))
        db.commit()

    finally:
        if close_after:
            db.close()


if __name__ == "__main__":
    seed_database()
    print("Database seeded successfully!")
