-- aoblib.lua : shared helpers for the HOI4 memory toolkit.
-- Loaded by the other scripts via: local aob = dofile(DIR..[[\lua\lib\aoblib.lua]])
-- Pure Cheat Engine Lua (7.x). No external dependencies.

local M = {}

-- Return base, size, name for the opened process's main module (hoi4.exe).
-- Falls back gracefully if enumModules is unavailable on this CE build.
function M.mainModule()
  local pname = process
  local ok, mods = pcall(enumModules)
  if ok and mods ~= nil then
    for i = 1, #mods do
      local m = mods[i]
      if pname ~= nil and m.Name ~= nil
         and string.lower(m.Name) == string.lower(pname) then
        return m.Address, m.Size, m.Name
      end
    end
    if #mods > 0 then
      return mods[1].Address, mods[1].Size, mods[1].Name
    end
  end
  local base = getAddress(pname or "")
  return base, 0x6000000, pname           -- generous fallback size
end

-- Run an AOB scan across the whole process. Returns an array of integer addrs.
function M.scan(signature)
  local out = {}
  local res = AOBScan(signature)
  if res == nil then return out end
  for i = 0, res.Count - 1 do
    local a = tonumber(res[i], 16)
    if a ~= nil then out[#out + 1] = a end
  end
  res.destroy()
  return out
end

-- Scan but keep only hits inside the main module. Filters out unrelated DLLs
-- and stale allocations so the match count reflects the real game code.
function M.scanInModule(signature)
  local base, size = M.mainModule()
  local lo, hi = base, base + size
  local out = {}
  for _, a in ipairs(M.scan(signature)) do
    if a >= lo and a < hi then out[#out + 1] = a end
  end
  return out
end

-- Read `len` bytes at addr -> uppercase space-separated hex string (or nil).
function M.readHex(addr, len)
  local b = readBytes(addr, len, true)
  if b == nil then return nil end
  local parts = {}
  for i = 1, #b do parts[i] = string.format("%02X", b[i]) end
  return table.concat(parts, " ")
end

-- Pretty "hoi4.exe+OFFSET (0xABS)" for an absolute address.
function M.fmt(addr)
  local base, _, name = M.mainModule()
  if addr >= base then
    return string.format("%s+%X (0x%X)", name or "module", addr - base, addr)
  end
  return string.format("0x%X", addr)
end

return M
