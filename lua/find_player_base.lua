-- find_player_base.lua : guided helper for relocating the player struct, which
-- is the anchor most cheats depend on. It wraps Cheat Engine's value scanner so
-- you can lock onto a known in-game number (e.g. Political Power) and narrow to
-- the address, then use "Find out what accesses this address" to read the base
-- register -> that register is pPlayer.
--
-- NOTE: This automates the scan/narrow loop. The final "what accesses" step is
-- done in the CE GUI (Memory View). See docs/METHODOLOGY.md for the full walk.
--
-- How to run (Cheat Engine -> Table menu -> "Lua Engine"):
--   TOOLKIT_DIR = [[C:\Users\Brock\Documents\My Cheat Tables\HOI4-Memory-Toolkit]]
--   dofile(TOOLKIT_DIR..[[\lua\find_player_base.lua]])
-- Then in the same Lua Engine console:
--   pbFirst(700000)     -- value the game currently holds (PP shows x1000)
--   -- change the value in-game (spend/gain PP), then:
--   pbNext(712000)      -- new value; repeat until pbList() shows a few addrs
--   pbList()

local DIR = TOOLKIT_DIR or [[C:\Users\Brock\Documents\My Cheat Tables\HOI4-Memory-Toolkit]]
local aob = dofile(DIR .. [[\lua\lib\aoblib.lua]])

local _ms, _fl

local function teardown()
  if _fl ~= nil then pcall(function() _fl.destroy() end); _fl = nil end
  if _ms ~= nil then pcall(function() _ms.destroy() end); _ms = nil end
end

function pbFirst(value)
  teardown()
  _ms = createMemScan()
  local ok, err = pcall(function()
    _ms.firstScan(
      soExactValue, vtDword, rtRounded,
      tostring(value), nil,
      0, 0x7fffffffffffffff,
      "+W-C", fsmNotAligned, "",
      false, false, false, false)
    _ms.waitTillDone()
  end)
  if not ok then
    print("[find_player_base] scan failed on this CE build: " .. tostring(err))
    print("Use the manual GUI scan instead (see docs/METHODOLOGY.md).")
    teardown(); return
  end
  _fl = createFoundList(_ms)
  _fl.initialize()
  print(string.format("[pbFirst] value=%s  ->  %d candidates", tostring(value), _fl.Count))
  print("Now change the value in-game and call pbNext(<newValue>).")
end

function pbNext(value)
  if _ms == nil then print("[pbNext] call pbFirst(value) first."); return end
  if _fl ~= nil then _fl.destroy(); _fl = nil end
  local ok, err = pcall(function()
    _ms.nextScan(soExactValue, vtDword, rtRounded, tostring(value), nil,
      "+W-C", fsmNotAligned, "", false, false, false, false)
    _ms.waitTillDone()
  end)
  if not ok then print("[pbNext] failed: " .. tostring(err)); return end
  _fl = createFoundList(_ms)
  _fl.initialize()
  print(string.format("[pbNext] value=%s  ->  %d candidates", tostring(value), _fl.Count))
  if _fl.Count <= 8 then pbList() end
end

function pbList()
  if _fl == nil then print("[pbList] no active scan."); return end
  local n = math.min(_fl.Count, 20)
  print(string.format("---- %d candidate address(es) (showing %d) ----", _fl.Count, n))
  for i = 0, n - 1 do
    local a = tonumber(_fl.Address[i], 16) or tonumber(_fl.Address[i])
    print(string.format("  %2d  %s", i, _fl.Address[i]))
  end
  print("Right-click one in CE -> 'Find out what accesses this address',")
  print("trigger it in-game, and read the base register in the access list.")
  print("That register (minus the field offset) is pPlayer. Cross-check the")
  print("offsets in data/signatures.lua (M.knownOffsets), e.g. PP = [[base+EA0]+C8].")
end

print("[find_player_base] loaded. Commands: pbFirst(v), pbNext(v), pbList()")
print("Tip: Political Power is stored x1000 (700 PP -> scan 700000).")
