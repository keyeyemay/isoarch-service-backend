-- Active sessions straight from Redis: every session is a HASH
-- isoarch:session:<SHA-256(cookie UUID)> = {user_id, username, created_at} with a TTL.
-- ARGV[1] — pattern of session keys, e.g. 'isoarch:session:*'.
-- Returns one entry per active session, sorted by login and remaining TTL.
local cursor = '0'
local sessions = {}
repeat
  local reply = redis.call('SCAN', cursor, 'MATCH', ARGV[1], 'COUNT', 100)
  cursor = reply[1]
  for _, key in ipairs(reply[2]) do
    if redis.call('TYPE', key).ok == 'hash' then
      local data = redis.call('HMGET', key, 'username', 'user_id', 'created_at')
      local ttl = redis.call('TTL', key)
      if data[1] and ttl ~= -2 then
        sessions[#sessions + 1] = {
          'login', data[1],
          'user_id', data[2],
          'session_key', key,
          'created_at', data[3] or '',
          'ttl', ttl,
        }
      end
    end
  end
until cursor == '0'

table.sort(sessions, function(a, b)
  if a[2] ~= b[2] then return a[2] < b[2] end
  return a[10] > b[10]
end)
return sessions
