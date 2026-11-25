-- Every active session stored in Redis, one row per session:
--   {login, user_id, redis_key, ttl_seconds}
-- KEYS[1] — hash user_id → username, ARGV[1] — SCAN pattern for session keys.
-- The cookie UUID itself is never stored: the key holds only its SHA-256.
local cursor = '0'
local sessions = {}
repeat
  local reply = redis.call('SCAN', cursor, 'MATCH', ARGV[1], 'COUNT', 100)
  cursor = reply[1]
  for _, key in ipairs(reply[2]) do
    local user_id = redis.call('GET', key)
    if user_id then
      local login = redis.call('HGET', KEYS[1], user_id) or ('user_id=' .. user_id)
      sessions[#sessions + 1] = {login, user_id, key, redis.call('TTL', key)}
    end
  end
until cursor == '0'

table.sort(sessions, function(a, b)
  if a[1] ~= b[1] then return a[1] < b[1] end
  return a[3] < b[3]
end)
return sessions
