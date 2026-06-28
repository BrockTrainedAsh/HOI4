-- healthcheck.lua : report which baseline signatures still resolve on the
-- currently-attached hoi4.exe. This is the FIRST thing to run after a patch:
-- it tells you exactly which cheats broke and which are merely ambiguous.
--
-- How to run (Cheat Engine -> Table menu -> "Lua Engine"):
--   TOOLKIT_DIR = [[C:\Users\Brock\Documents\My Cheat Tables\HOI4-Memory-Toolkit]]
--   dofile(TOOLKIT_DIR..[[\lua\healthcheck.lua]])
--
-- Attach CE to hoi4.exe first (load a save so the game is fully in memory).

local DIR = TOOLKIT_DIR or [[C:\Users\Brock\Documents\My Cheat Tables\HOI4-Memory-Toolkit]]
local aob = dofile(DIR .. [[\lua\lib\aoblib.lua]])
local cat = dofile(DIR .. [[\data\signatures.lua]])

if getOpenedProcessID() == 0 then
  print("[healthcheck] No process attached. Open hoi4.exe in Cheat Engine first")
  print("              (and load a save so all systems are in memory).")
  return
end

local line = string.rep("=", 72)
print(line)
print(string.format("HOI4 signature health check   baseline=%s   process=%s",
  cat.gameVersion, tostring(process)))
print(line)

local okc, missing, multi = 0, {}, {}
for _, s in ipairs(cat.signatures) do
  local hits = aob.scanInModule(s.pattern)
  local n = #hits
  local tag, detail
  if n == 1 then
    okc = okc + 1
    tag, detail = "[ ok ]", aob.fmt(hits[1])
  elseif n == 0 then
    missing[#missing + 1] = s
    tag, detail = "[FAIL]", "MISSING            -> " .. s.feature
  else
    multi[#multi + 1] = { s = s, n = n }
    tag, detail = "[warn]", "AMBIGUOUS x" .. n .. "       -> " .. s.feature
  end
  local anchor = s.isAnchor and " *ANCHOR*" or ""
  print(string.format("%-6s %s %s%s", s.symbol, tag, detail, anchor))
end

print(string.rep("-", 72))
print(string.format("Resolved %d/%d    Missing %d    Ambiguous %d",
  okc, #cat.signatures, #missing, #multi))

if #missing > 0 then
  print("\nBROKEN (relocate these):")
  for _, s in ipairs(missing) do
    print(string.format("  %-6s %s", s.symbol, s.feature))
  end
end
if #multi > 0 then
  print("\nAMBIGUOUS (pattern no longer unique - lengthen / add wildcards):")
  for _, e in ipairs(multi) do
    print(string.format("  %-6s x%d  %s", e.s.symbol, e.n, e.s.feature))
  end
end

print("\nNext: relocate the *ANCHOR* scans first (MOHP/MOSF/MOSR). Once the player")
print("struct is found, most dependent cheats re-point via the offsets in")
print("data/signatures.lua (M.knownOffsets). See docs/METHODOLOGY.md.")
