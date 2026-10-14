-- Скриншот 11: черновик после создания / услуга после публикации и удаления.
SELECT id, title, status, creator_id, moderator_id, image_file, video_file,
       delta_n15, delta_c13, created_at, formed_at, completed_at, deleted_at
FROM isotopic_signatures ORDER BY id;

-- Скриншот 12: пользователь, зарегистрированный через API.
SELECT id, username, full_name, email, created_at FROM users ORDER BY id;

-- Скриншот 13: связь лайка и пользователей/услуг (лайк сохраняется при soft delete).
SELECT l.id, l.user_id, u.username, l.signature_id, s.title, s.status, l.created_at
FROM signature_likes AS l
JOIN users AS u ON u.id = l.user_id
JOIN isotopic_signatures AS s ON s.id = l.signature_id
ORDER BY l.id;
