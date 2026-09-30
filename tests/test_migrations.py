import unittest
from sqlalchemy import create_engine,text,inspect
from sqlalchemy.orm import Session
from db.migrate import upgrade_database
from db.seed import seed_database
from models import User, IsotopicSignature


class MigrationTests(unittest.TestCase):
    def test_fresh_schema_and_repeat_upgrade(self):
        engine=create_engine('sqlite://')
        upgrade_database(engine);upgrade_database(engine)
        with Session(engine) as db:
            seed_database(db)
            self.assertEqual(db.query(IsotopicSignature).count(),6)
            self.assertIsNone(db.query(IsotopicSignature).filter_by(creator_id=1,status='draft').first())
            seed_database(db)
            self.assertEqual(db.query(User).count(),3)
        engine.dispose()

    def test_lr2_upgrade_preserves_records_and_columns(self):
        engine=create_engine('sqlite://')
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(100) NOT NULL UNIQUE, full_name VARCHAR(255), email VARCHAR(255) UNIQUE, created_at DATETIME NOT NULL)'))
            conn.execute(text('CREATE TABLE isotopic_signatures (id INTEGER PRIMARY KEY, title VARCHAR(255) NOT NULL, description TEXT, status VARCHAR(50) NOT NULL, image_url VARCHAR(500), video_url VARCHAR(500), delta_n15 FLOAT, delta_c13 FLOAT, created_at DATETIME NOT NULL, creator_id INTEGER NOT NULL REFERENCES users(id), formation_date DATETIME)'))
            conn.execute(text('CREATE TABLE signature_likes (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), signature_id INTEGER NOT NULL REFERENCES isotopic_signatures(id), created_at DATETIME NOT NULL, CONSTRAINT uq_user_signature_like UNIQUE (user_id,signature_id))'))
            conn.execute(text("CREATE UNIQUE INDEX uq_user_single_draft ON isotopic_signatures(creator_id) WHERE status='черновик'"))
            conn.execute(text("INSERT INTO users VALUES (1,'legacy','Name','legacy@example.org','2024-01-01')"))
            conn.execute(text("INSERT INTO isotopic_signatures (id,title,status,image_url,video_url,creator_id,created_at,formation_date) VALUES (1,'Preserved','опубликован','http://localhost:9000/isoarchservice/image.png','video.mp4',1,'2024-01-01','2024-02-01'),(2,'Draft','черновик',NULL,NULL,1,'2024-01-01','2024-01-01')"))
            conn.execute(text("INSERT INTO signature_likes VALUES (1,1,1,'2024-01-01')"))
        upgrade_database(engine)
        with Session(engine) as db:
            self.assertEqual(db.get(IsotopicSignature,1).title,'Preserved')
            self.assertEqual(db.get(IsotopicSignature,1).status,'published')
            self.assertEqual(db.get(IsotopicSignature,1).image_file,'image.png')
            self.assertEqual(len(db.get(IsotopicSignature,1).likes),1)
            self.assertIsNone(db.get(IsotopicSignature,2).formed_at)
            db.add(User(username='new',password='hash'));db.commit()
        self.assertIn('moderator_id',[col['name'] for col in inspect(engine).get_columns('isotopic_signatures')])
        engine.dispose()
