local cursor = '0'
local counts = {}
repeat
  local reply = redis.call('SCAN', cursor, 'MATCH', ARGV[1], 'COUNT', 100)
  cursor = reply[1]
  for _, key in ipairs(reply[2]) do
    local user_id = redis.call('GET', key)
    if user_id then
      counts[user_id] = (counts[user_id] or 0) + 1
    end
  end
until cursor == '0'

local logins = {}
for user_id, count in pairs(counts) do
  local login = redis.call('HGET', KEYS[1], user_id) or ('user_id=' .. user_id)
  logins[#logins + 1] = {login, count}
end
table.sort(logins, function(a, b) return a[1] < b[1] end)
return logins
